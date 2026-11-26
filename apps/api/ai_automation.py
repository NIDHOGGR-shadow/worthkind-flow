"""Restricted staff augmentation and explicit human approval, no model tools."""
import hashlib
import json
from typing import Literal
from uuid import UUID
from fastapi import Header
from pydantic import BaseModel,Field,StrictBool
from operations_pg import actor,encrypt,decrypt
from ai_gateway import db

class TicketProposal(BaseModel):
    request_key:str=Field(min_length=8,max_length=90,pattern=r"^[A-Za-z0-9_-]+$")
    category:Literal["it","reception","housekeeping","maintenance","kitchen","general"]
    priority:Literal["low","normal","high"]="normal"
    subject:str=Field(min_length=4,max_length=160)
    description:str=Field(min_length=8,max_length=3000)

class Approval(BaseModel):
    approve:StrictBool

def install_ai_automation_routes(app):
    base="/api/v1/properties/{slug}/staff/ai"
    @app.get(base+"/insights")
    def insights(slug:str,authorization:str|None=Header(None)):
        return db("SELECT worthkind_flow.staff_ai_insights(%s,%s)",(actor(authorization),slug),policy=True)[0]

    @app.post(base+"/alerts/{alert_id}/acknowledge")
    def acknowledge(slug:str,alert_id:UUID,authorization:str|None=Header(None)):
        return {"acknowledged":db("SELECT worthkind_flow.ack_ai_alert(%s,%s,%s)",(actor(authorization),slug,alert_id),policy=True)[0]}

    @app.post(base+"/ticket-proposals",status_code=201)
    def propose(slug:str,body:TicketProposal,authorization:str|None=Header(None)):
        subject=actor(authorization)
        key="ai-"+body.request_key
        payload={"subject":body.subject,"description":body.description}
        digest=hashlib.sha256(json.dumps(body.model_dump(mode="json",exclude={"request_key"}),sort_keys=True).encode()).hexdigest()
        cipher=encrypt(payload,f"wf:ticket:{slug}:{key}")
        pid=db("SELECT worthkind_flow.propose_ai_ticket(%s,%s,%s,%s,%s,%s,%s)",(subject,slug,key,digest,body.category,body.priority,cipher),policy=True)[0]
        return {"id":str(pid),"approval_required":True}

    @app.get(base+"/ticket-proposals")
    def proposals(slug:str,authorization:str|None=Header(None)):
        rows=db("SELECT * FROM worthkind_flow.list_ai_proposals(%s,%s)",(actor(authorization),slug),policy=True,many=True)
        return {"proposals":[{"id":str(r[0]),"category":r[2],"priority":r[3],"state":r[4],
            **decrypt(r[5],f"wf:ticket:{slug}:{r[1]}"),"expires_at":r[6].isoformat(),"ticket_id":str(r[7]) if r[7] else None} for r in rows]}

    @app.post(base+"/ticket-proposals/{proposal_id}/decision")
    def decide(slug:str,proposal_id:UUID,body:Approval,authorization:str|None=Header(None)):
        return db("SELECT worthkind_flow.decide_ai_ticket(%s,%s,%s,%s)",(actor(authorization),slug,proposal_id,body.approve),policy=True)[0]
