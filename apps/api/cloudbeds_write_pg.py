"""Explicit manager-authorized PMS writes. Never automatically retry ambiguous writes."""
import hashlib
import hmac
import json
import os
from datetime import date
from decimal import Decimal
from typing import Literal
from urllib.parse import urlencode
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
from uuid import UUID
import psycopg
from fastapi import Header,HTTPException
from pydantic import BaseModel,Field,StrictBool
from psycopg.types.json import Jsonb
from supabase_identity import NoRedirect
from operations_pg import actor,command
from cloudbeds_pg import config,get,reservation_view,record_evidence,identifier

class Creation(BaseModel):
    intent_id:UUID
    request_key:str=Field(min_length=8,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")
    first_name:str=Field(min_length=1,max_length=100)
    last_name:str=Field(min_length=1,max_length=100)
    country:str=Field(pattern=r"^[A-Z]{2}$")
    postal_code:str=Field(min_length=1,max_length=30)
    email:str=Field(min_length=5,max_length=254,pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    guest_authorized:Literal[True]

class Mutation(BaseModel):
    request_key:str=Field(min_length=8,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")
    action:Literal["cancel","change_checkout"]
    checkout_date:date|None=None
    guest_authorized:Literal[True]

class RateUpdate(BaseModel):
    request_key:str=Field(min_length=8,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")
    rate_id:str=Field(min_length=1,max_length=80,pattern=r"^[A-Za-z0-9_-]+$")
    start:date
    end:date
    nightly_minor:int=Field(ge=1,le=1000000000000)

def enabled(subject,slug,*,rate=False):
    cfg=config(subject,slug)
    if os.getenv("WF_CLOUDBEDS_WRITES_ENABLED")!="1" or cfg.get("allow_writes") is not True:
        raise HTTPException(503,"PMS writes not activated")
    if rate and cfg.get("allow_rate_updates") is not True:
        raise HTTPException(503,"PMS rate updates not activated")
    if not os.getenv("WF_PMS_PROVIDER_POSTGRES_DSN"):
        raise HTTPException(503,"PMS evidence unavailable")
    return cfg

def digest(body):
    key=os.getenv("WF_GUEST_QUOTA_SECRET","")
    if len(key)<32:
        raise HTTPException(503,"Idempotency configuration unavailable")
    return hmac.new(key.encode(),body.model_dump_json().encode(),hashlib.sha256).hexdigest()

def write(cfg,operation,payload):
    if operation not in ("postReservation","putReservation","patchRate"):
        raise ValueError("Unsupported write")
    is_rate=operation=="patchRate"
    data=json.dumps(payload,separators=(",",":")).encode() if is_rate else urlencode(payload).encode()
    req=Request("https://api.cloudbeds.com/api/v1.3/"+operation,data=data,
        method="PUT" if operation=="putReservation" else "POST",headers={
        "x-api-key":cfg["api_key"],"Accept":"application/json",
        "Content-Type":"application/json" if is_rate else "application/x-www-form-urlencoded"})
    try:
        with build_opener(NoRedirect()).open(req,timeout=20) as response:
            raw=response.read(1048577)
        if len(raw)>1048576:
            raise ValueError()
        result=json.loads(raw)
        if not isinstance(result,dict) or result.get("success") is not True:
            raise ValueError()
        return result
    except (HTTPError,URLError,TimeoutError,OSError,ValueError):
        raise HTTPException(503,"PMS write outcome uncertain; reconcile before further action") from None

def finish(subject,slug,job,state,external=None,provider_job=None,result=None):
    try:
        with psycopg.connect(os.environ["WF_PMS_PROVIDER_POSTGRES_DSN"],connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_pms_provider")
                return conn.execute("SELECT worthkind_flow.finish_pms_command(%s,%s,%s,%s,%s,%s,%s)",
                    (subject,slug,job["id"],state,external,provider_job,Jsonb(result or {}))).fetchone()[0]
    except (psycopg.Error,KeyError):
        raise HTTPException(503,"PMS command result could not be persisted; do not retry write") from None

def begin(subject,slug,cfg,op,body,intent=None,external=None):
    job=command("SELECT worthkind_flow.begin_pms_command(%s,%s,%s,%s,%s,%s,%s)",
    (subject,slug,op,body.request_key,digest(body),intent,external))[0]
    if job["account_alias"]!=cfg["alias"] or job["external_property_id"]!=cfg["property_id"]:
        raise HTTPException(409,"PMS command account mismatch")
    return job

def readback(cfg,rid):
    return reservation_view(cfg,get(cfg,"getReservation",{"propertyID":cfg["property_id"],"reservationID":rid,"includeGuestRequirements":"false"}),rid)

def reservation_id(response):
    data=response.get("data")
    return identifier(response.get("reservationID") or (data.get("reservationID") if isinstance(data,dict) else None))

def create_payload(cfg,intent,body):
    mapping=cfg.get("room_types",{})
    rt=mapping.get(intent["room_type_id"]) if isinstance(mapping,dict) else None
    if not isinstance(rt,str) or not rt:
        raise HTTPException(409,"Room type mapping unavailable")
    return {"propertyID":cfg["property_id"],"startDate":intent["arrival"],"endDate":intent["departure"],
      "guestFirstName":body.first_name,"guestLastName":body.last_name,"guestCountry":body.country,"guestZip":body.postal_code,
      "guestEmail":body.email,"rooms[0][roomTypeID]":rt,"rooms[0][quantity]":1,
      "adults[0][roomTypeID]":rt,"adults[0][quantity]":intent["adults"],
      "children[0][roomTypeID]":rt,"children[0][quantity]":intent["children"],"paymentMethod":"cash",
      "sendEmailConfirmation":"false"}

def install_pms_write_routes(app):
    base="/api/v1/properties/{slug}/staff/pms"

    @app.get(base+"/commands")
    def list_commands(slug:str,authorization:str|None=Header(None)):
        return {"commands":command("SELECT worthkind_flow.staff_pms_commands(%s,%s)",(actor(authorization),slug))[0]}

    @app.post(base+"/commands/create")
    def create(slug:str,body:Creation,authorization:str|None=Header(None)):
        subject=actor(authorization)
        cfg=enabled(subject,slug)
        job=begin(subject,slug,cfg,"create",body,body.intent_id)
        if not job["submit"]:
            return {"command":job,"replayed":True}
        rid=None
        try:
            payload=create_payload(cfg,job["intent"],body)
            response=write(cfg,"postReservation",payload)
            rid=reservation_id(response)
            job=finish(subject,slug,job,"accepted",rid)
            view=readback(cfg,rid)
            if (view["arrival"],view["departure"])!=(payload["startDate"],payload["endDate"]):
                raise HTTPException(502,"Reservation dates do not match")
            evidence=record_evidence(subject,slug,cfg,view,body.intent_id)
            return {"command":finish(subject,slug,job,"verified",rid,result={"provider_state":view["state"],"evidence_id":evidence["id"]}),
                    "reservation":view,"payment_confirmed":False}
        except HTTPException:
            finish(subject,slug,job,"unknown",rid,result={"requires_provider_review":True})
            raise

    @app.post(base+"/reservations/{rid}/commands")
    def mutate(slug:str,rid:str,body:Mutation,authorization:str|None=Header(None)):
        subject=actor(authorization)
        cfg=enabled(subject,slug)
        if body.action=="change_checkout" and body.checkout_date is None or body.action=="cancel" and body.checkout_date is not None:
            raise HTTPException(422,"Invalid reservation change")
        current=readback(cfg,rid)
        if current["state"] not in ("confirmed","not_confirmed"):
            raise HTTPException(409,"Provider reservation not eligible")
        if body.checkout_date and not 1<=(body.checkout_date-date.fromisoformat(current["arrival"])).days<=90:
            raise HTTPException(422,"Invalid checkout date")
        job=begin(subject,slug,cfg,body.action,body,external=rid)
        if not job["submit"]:
            return {"command":job,"replayed":True}
        payload={"propertyID":cfg["property_id"],"reservationID":rid,"sendStatusChangeEmail":"false"}
        if body.action=="cancel":
            payload.update(status="canceled",canceledByGuest="true")
        else:
            payload.update(checkoutDate=body.checkout_date.isoformat(),modifiedByGuest="true")
        try:
            write(cfg,"putReservation",payload)
            view=readback(cfg,rid)
            if body.action=="cancel" and view["state"]!="canceled" or body.checkout_date and view["departure"]!=body.checkout_date.isoformat():
                raise HTTPException(502,"Provider change not confirmed")
            evidence=record_evidence(subject,slug,cfg,view,None)
            return {"command":finish(subject,slug,job,"verified",rid,result={"provider_state":view["state"],"evidence_id":evidence["id"]}),"reservation":view}
        except HTTPException:
            finish(subject,slug,job,"unknown",rid,result={"requires_provider_review":True})
            raise

    @app.post(base+"/rate-commands")
    def rate(slug:str,body:RateUpdate,authorization:str|None=Header(None)):
        subject=actor(authorization)
        cfg=enabled(subject,slug,rate=True)
        if not isinstance(cfg.get("allowed_rate_ids"),list) or body.rate_id not in cfg["allowed_rate_ids"] or not 0<=(body.end-body.start).days<=90 or body.start<date.today():
            raise HTTPException(422,"Rate or interval unavailable")
        digits=cfg.get("minor_digits")
        if type(digits) is not int or not 0<=digits<=3:
            raise HTTPException(503,"Currency precision unavailable")
        job=begin(subject,slug,cfg,"rate_update",body)
        if not job["submit"]:
            return {"command":job,"replayed":True}
        amount=format(Decimal(body.nightly_minor)/10**digits,"f")
        provider_job=None
        try:
            response=write(cfg,"patchRate",{"rates":[{"rateID":body.rate_id,"interval":[{"startDate":body.start.isoformat(),"endDate":body.end.isoformat(),"rate":amount}]}]})
            data=response.get("data")
            provider_job=identifier(response.get("jobReferenceID") or (data.get("jobReferenceID") if isinstance(data,dict) else None))
            return {"command":finish(subject,slug,job,"accepted",provider_job=provider_job),"ota_delivery_verified":False}
        except HTTPException:
            finish(subject,slug,job,"unknown",provider_job=provider_job,result={"requires_provider_review":True})
            raise


    @app.post(base+"/rate-commands/{command_id}/verify")
    def verify_rate(slug:str,command_id:UUID,authorization:str|None=Header(None)):
        subject=actor(authorization)
        cfg=config(subject,slug)
        job=command("SELECT worthkind_flow.get_pms_command(%s,%s,%s)",(subject,slug,command_id))[0]
        if job["operation"]!="rate_update" or job["account_alias"]!=cfg["alias"] or job["external_property_id"]!=cfg["property_id"]:
            raise HTTPException(409,"Rate job account mismatch")
        provider_id=job["provider_job_id"]
        if not provider_id:
            raise HTTPException(409,"Provider job ID unknown; investigate before resubmission")
        if job["state"] in ("verified","error"):
            return {"command":job,"ota_delivery_verified":False}
        rows=get(cfg,"getRateJobs",{"jobReferenceID":provider_id})
        if not isinstance(rows,list):
            raise HTTPException(502,"Unsupported rate job response")
        matching=[r for r in rows if isinstance(r,dict) and str(r.get("jobReferenceID"))==provider_id]
        if len(matching)!=1:
            raise HTTPException(503,"Rate job status unavailable")
        status=matching[0].get("status")
        if status not in ("completed","error","in_progress"):
            raise HTTPException(502,"Unknown rate job state")
        state={"completed":"verified","error":"error","in_progress":"accepted"}[status]
        return {"command":finish(subject,slug,job,state,provider_job=provider_id,result={"provider_job_status":status}),"ota_delivery_verified":False}
