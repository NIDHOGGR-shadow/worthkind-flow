"""Read-only Cloudbeds PMS adapter. Never exposes raw guest/provider payloads."""
import json
import os
from datetime import date,datetime,timezone
from urllib.parse import urlencode
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
from fastapi import Header,HTTPException,Query
from pydantic import BaseModel,Field
from uuid import UUID
import psycopg
from psycopg import errors
from supabase_identity import NoRedirect
from operations_pg import actor,command

def config(subject,slug):
    row=command("SELECT * FROM worthkind_flow.staff_pms_account(%s,%s)",(subject,slug))
    try:
        entries=json.loads(os.environ["WF_CLOUDBEDS_ACCOUNTS_JSON"])
        cfg=entries[slug]
        if cfg["property_id"]!=row[0] or cfg["alias"]!=row[1] or not isinstance(cfg["api_key"],str) or not cfg["api_key"]:
            raise ValueError()
        if any(k!=slug and v.get("api_key")==cfg["api_key"] for k,v in entries.items()):
            raise ValueError()
        return cfg
    except (KeyError,ValueError,TypeError,AttributeError):
        raise HTTPException(503,"Hotel PMS credentials unavailable") from None

def get(cfg,operation,params):
    if operation not in ("getAvailableRoomTypes","getReservation","getReservations"):
        raise ValueError("Unsupported operation")
    url="https://api.cloudbeds.com/api/v1.3/"+operation+"?"+urlencode(params)
    req=Request(url,headers={"x-api-key":cfg["api_key"],"Accept":"application/json"})
    try:
        with build_opener(NoRedirect()).open(req,timeout=15) as response:
            raw=response.read(1048577)
        if len(raw)>1048576:
            raise ValueError()
        result=json.loads(raw)
        if not isinstance(result,dict) or result.get("success") is not True:
            raise ValueError()
        return result["data"]
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,KeyError):
        raise HTTPException(503,"PMS response unavailable or unsupported") from None

def identifier(value):
    if isinstance(value,(str,int)) and not isinstance(value,bool) and 1<=len(str(value))<=100:
        return str(value)
    raise HTTPException(502,"PMS identifier missing")

def reservation_view(cfg,row,expected=None):
    if not isinstance(row,dict) or identifier(row.get("propertyID"))!=cfg["property_id"]:
        raise HTTPException(502,"PMS property mismatch")
    rid=identifier(row.get("reservationID"))
    if expected is not None and rid!=expected:
        raise HTTPException(502,"PMS reservation mismatch")
    state=row.get("status")
    if state not in ("confirmed","not_confirmed","canceled","checked_in","checked_out","no_show","in_progress"):
        raise HTTPException(502,"Unsupported PMS reservation state")
    try:
        start=date.fromisoformat(row["startDate"])
        end=date.fromisoformat(row["endDate"])
        if end<=start:
            raise ValueError()
    except (KeyError,ValueError,TypeError):
        raise HTTPException(502,"PMS stay dates unavailable") from None
    # Deliberately omit contact, guest names, payment details and arbitrary raw JSON.
    result={"reservation_id":rid,"state":state,"arrival":start.isoformat(),"departure":end.isoformat()}
    for src,dst in (("sourceID","source_id"),("sourceName","source_name"),("thirdPartyIdentifier","channel_reservation_id")):
        val=row.get(src)
        if isinstance(val,(str,int)) and not isinstance(val,bool):
            result[dst]=str(val)[:160]
    return result

def install_pms_routes(app):
    base="/api/v1/properties/{slug}/staff/pms"
    @app.get(base+"/reservations/{reservation_id}")
    def reservation(slug:str,reservation_id:str,authorization:str|None=Header(None)):
        cfg=config(actor(authorization),slug)
        data=get(cfg,"getReservation",{"propertyID":cfg["property_id"],"reservationID":reservation_id,"includeGuestRequirements":"false"})
        return {"provider":"cloudbeds","retrieved_at":datetime.now(timezone.utc).isoformat(),"reservation":reservation_view(cfg,data,reservation_id)}

    @app.get(base+"/channel-reservations")
    def channel_list(slug:str,start:date,end:date,page:int=Query(1,ge=1,le=1000),authorization:str|None=Header(None)):
        if not 0<=(end-start).days<=90:
            raise HTTPException(422,"Invalid reservation date range")
        cfg=config(actor(authorization),slug)
        data=get(cfg,"getReservations",{"propertyID":cfg["property_id"],"checkInFrom":start.isoformat(),"checkInTo":end.isoformat(),"pageNumber":page,"pageSize":100,"includeGuestsDetails":"false"})
        if not isinstance(data,list) or len(data)>100:
            raise HTTPException(502,"Unsupported PMS reservation response")
        return {"provider":"cloudbeds","page":page,"reservations":[reservation_view(cfg,row) for row in data],"retrieved_at":datetime.now(timezone.utc).isoformat()}

    @app.get(base+"/availability")
    def availability(slug:str,start:date,end:date,rooms:int=Query(1,ge=1,le=10),adults:int=Query(1,ge=1,le=30),children:int=Query(0,ge=0,le=30),authorization:str|None=Header(None)):
        if not 1<=(end-start).days<=90:
            raise HTTPException(422,"Invalid stay range")
        cfg=config(actor(authorization),slug)
        data=get(cfg,"getAvailableRoomTypes",{"propertyIDs":cfg["property_id"],"startDate":start.isoformat(),"endDate":end.isoformat(),"rooms":rooms,"adults":adults,"children":children,"detailedRates":"false"})
        # Accept a documented flat result or a property-scoped roomTypes collection.
        if not isinstance(data,list):
            raise HTTPException(502,"Unsupported PMS availability response")
        rows=[]
        for value in data:
            if not isinstance(value,dict) or identifier(value.get("propertyID"))!=cfg["property_id"]:
                raise HTTPException(502,"PMS property mismatch")
            if isinstance(value.get("roomTypes"),list):
                rows.extend(value["roomTypes"])
            else:
                rows.append(value)
        result=[]
        for row in rows:
            if not isinstance(row,dict) or ("propertyID" in row and identifier(row["propertyID"])!=cfg["property_id"]):
                raise HTTPException(502,"PMS property mismatch")
            available=row.get("roomsAvailable")
            if type(available) is not int or available<0:
                raise HTTPException(502,"Unsupported room availability")
            result.append({"room_type_id":identifier(row.get("roomTypeID")),"rooms_available":available})
        return {"provider":"cloudbeds","room_types":result,"retrieved_at":datetime.now(timezone.utc).isoformat(),"inventory_held":False,"rates_binding":False}


class EvidenceRequest(BaseModel):
    reservation_id:str=Field(min_length=1,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")
    intent_id:UUID|None=None

def record_evidence(subject,slug,cfg,view,intent_id):
    dsn=os.getenv("WF_PMS_PROVIDER_POSTGRES_DSN")
    if not dsn:
        raise HTTPException(503,"PMS evidence database unavailable")
    try:
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_pms_provider")
                return conn.execute("SELECT worthkind_flow.record_pms_reservation(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (subject,slug,cfg["property_id"],cfg["alias"],view["reservation_id"],view["state"],date.fromisoformat(view["arrival"]),date.fromisoformat(view["departure"]),view.get("source_id"),view.get("source_name"),view.get("channel_reservation_id"),intent_id)).fetchone()[0]
    except errors.InsufficientPrivilege:
        raise HTTPException(403,"PMS account access denied") from None
    except (errors.CheckViolation,errors.UniqueViolation):
        raise HTTPException(409,"PMS reservation evidence conflict") from None
    except psycopg.Error:
        raise HTTPException(503,"PMS evidence unavailable") from None

def install_pms_evidence_routes(app):
    base="/api/v1/properties/{slug}/staff/pms"
    @app.post(base+"/reservation-evidence")
    def sync(slug:str,body:EvidenceRequest,authorization:str|None=Header(None)):
        subject=actor(authorization)
        cfg=config(subject,slug)
        data=get(cfg,"getReservation",{"propertyID":cfg["property_id"],"reservationID":body.reservation_id,"includeGuestRequirements":"false"})
        view=reservation_view(cfg,data,body.reservation_id)
        evidence=record_evidence(subject,slug,cfg,view,body.intent_id)
        return {"evidence":evidence,"source":"cloudbeds","guest_identity_link_independently_verified":False}

    @app.get(base+"/reservation-evidence")
    def list_evidence(slug:str,authorization:str|None=Header(None)):
        return {"reservations":command("SELECT worthkind_flow.list_pms_evidence(%s,%s)",(actor(authorization),slug))[0],"source":"last_verified_cloudbeds_readback"}
