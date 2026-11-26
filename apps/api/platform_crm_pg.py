"""Platform-owned B2B prospect pipeline. Not a hotel staff permission."""
import hashlib
import json
import os
from typing import Literal
from uuid import UUID
import psycopg
from psycopg import errors
from fastapi import Header,HTTPException,Query
from pydantic import BaseModel,Field
from operations_pg import actor,encrypt,decrypt

class Prospect(BaseModel):
    account_key:str=Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,99}$")
    hotel_name:str=Field(min_length=2,max_length=200)
    source_reference:str=Field(min_length=3,max_length=240)
    contact:str|None=Field(default=None,min_length=3,max_length=1000)

class Change(BaseModel):
    request_key:UUID
    revision:int=Field(ge=1)
    action:Literal["stage","consent"]
    value:Literal["discovery","consented_waitlist","written_pilot_interest","closed","granted","revoked"]
    evidence_reference:str=Field(min_length=8,max_length=240)

def crm_command(query,params,many=False):
    dsn=os.getenv("WF_PLATFORM_CRM_POSTGRES_DSN")
    if not dsn:
        raise HTTPException(503,"CRM unavailable")
    try:
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_platform_crm")
                c=conn.execute(query,params)
                return c.fetchall() if many else c.fetchone()[0]
    except errors.InsufficientPrivilege:
        raise HTTPException(403,"CRM access denied") from None
    except errors.NoDataFound:
        raise HTTPException(404,"Prospect unavailable") from None
    except (errors.UniqueViolation,errors.CheckViolation,errors.SerializationFailure):
        raise HTTPException(409,"CRM state conflict") from None
    except errors.InvalidParameterValue:
        raise HTTPException(422,"Invalid CRM operation") from None
    except psycopg.Error:
        raise HTTPException(503,"CRM unavailable") from None

def install_platform_crm(app):
    base="/api/v1/platform/crm/prospects"
    @app.post(base,status_code=201)
    def create(body:Prospect,authorization:str|None=Header(None)):
        subject=actor(authorization)
        digest=hashlib.sha256(json.dumps(body.model_dump(),sort_keys=True).encode()).hexdigest()
        cipher=encrypt({"contact":body.contact},f"wf:crm:{body.account_key}") if body.contact is not None else None
        return crm_command("SELECT worthkind_flow.create_crm_prospect(%s,%s,%s,%s,%s,%s)",
                           (subject,body.account_key,body.hotel_name,body.source_reference,cipher,digest))

    @app.get(base)
    def list_prospects(after:UUID|None=None,limit:int=Query(50,ge=1,le=100),authorization:str|None=Header(None)):
        rows=crm_command("SELECT * FROM worthkind_flow.list_crm_prospects(%s,%s,%s)",(actor(authorization),after,limit+1),many=True)
        return {"prospects":[{"id":str(r[0]),"account_key":r[1],"hotel_name":r[2],"source_reference":r[3],
                "contact":decrypt(r[4],f"wf:crm:{r[1]}")["contact"] if r[4] else None,"stage":r[5],
                "outreach_allowed":r[6],"revision":r[7],"created_at":r[8].isoformat()} for r in rows[:limit]],
                "next_cursor":str(rows[limit-1][0]) if len(rows)>limit else None}

    @app.post(base+"/{prospect_id}/change")
    def change(prospect_id:UUID,body:Change,authorization:str|None=Header(None)):
        return crm_command("SELECT worthkind_flow.change_crm_prospect(%s,%s,%s,%s,%s,%s,%s)",
                           (actor(authorization),prospect_id,body.request_key,body.revision,body.action,body.value,body.evidence_reference))
