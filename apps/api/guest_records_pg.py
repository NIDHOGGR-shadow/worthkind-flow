"""Guest case preferences, consent and feedback. Receipt proof is required."""
from hashlib import sha256
from typing import Literal
from uuid import UUID
from fastapi import Header,HTTPException,Depends
from pydantic import BaseModel,Field,StrictBool
from guest_quota import enforce_guest_quota
from operations_pg import actor,command,encrypt,decrypt

class Preferences(BaseModel):
    language:str=Field(default="",max_length=40)
    accessibility_requests:str=Field(default="",max_length=1000)
    service_preferences:str=Field(default="",max_length=1000)
    revision:int=Field(ge=0)

class Consent(BaseModel):
    purpose:Literal["service_followup","marketing"]
    granted:StrictBool
    policy_version:str=Field(min_length=1,max_length=80)

class Feedback(BaseModel):
    rating:int=Field(ge=1,le=5)
    comment:str=Field(default="",max_length=2000)

class Review(BaseModel):
    action:Literal["review","resolve"]

def proof(token):
    if not token or not 32<=len(token)<=128 or not token.isascii() or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in token):
        raise HTTPException(404,"Case unavailable")
    return sha256(token.encode()).hexdigest()


def install_guest_records(app):
    base="/api/v1/properties/{slug}"
    g=base+"/guest/cases/{case_id}"
    @app.put(g+"/preferences",dependencies=[Depends(enforce_guest_quota)])
    def save(slug:str,case_id:UUID,body:Preferences,x_receipt_token:str|None=Header(None)):
        h=proof(x_receipt_token)
        cipher=encrypt(body.model_dump(exclude={"revision"}),f"wf:preferences:{slug}:{case_id}")
        r=command("SELECT worthkind_flow.save_guest_preferences(%s,%s,%s,%s,%s)",(slug,case_id,h,cipher,body.revision),guest=True)
        return {"revision":r[0]}

    @app.get(g+"/preferences",dependencies=[Depends(enforce_guest_quota)])
    def read(slug:str,case_id:UUID,x_receipt_token:str|None=Header(None)):
        r=command("SELECT * FROM worthkind_flow.read_guest_preferences(%s,%s,%s)",(slug,case_id,proof(x_receipt_token)),guest=True)
        return {"preferences":decrypt(r[0],f"wf:preferences:{slug}:{case_id}"),"revision":r[1]} if r else {"preferences":None,"revision":0}

    @app.post(g+"/consent",status_code=201,dependencies=[Depends(enforce_guest_quota)])
    def consent(slug:str,case_id:UUID,body:Consent,x_receipt_token:str|None=Header(None)):
        r=command("SELECT worthkind_flow.record_guest_consent(%s,%s,%s,%s,%s,%s)",(slug,case_id,proof(x_receipt_token),body.purpose,body.granted,body.policy_version),guest=True)
        return {"id":str(r[0]),"purpose":body.purpose,"granted":body.granted}

    @app.post(g+"/feedback",status_code=201,dependencies=[Depends(enforce_guest_quota)])
    def feedback(slug:str,case_id:UUID,body:Feedback,x_receipt_token:str|None=Header(None)):
        h=proof(x_receipt_token)
        cipher=encrypt({"comment":body.comment},f"wf:feedback:{slug}:{case_id}")
        r=command("SELECT worthkind_flow.submit_feedback(%s,%s,%s,%s,%s)",(slug,case_id,h,body.rating,cipher),guest=True)
        return {"id":str(r[0]),"state":"new"}

    @app.get(base+"/staff/feedback")
    def queue(slug:str,authorization:str|None=Header(None)):
        rows=command("SELECT * FROM worthkind_flow.list_feedback(%s,%s)",(actor(authorization),slug),many=True)
        return {"feedback":[{"id":str(r[0]),"case_id":str(r[1]),"rating":r[2],"state":r[3],**decrypt(r[4],f"wf:feedback:{slug}:{r[1]}"),"created_at":r[5].isoformat()} for r in rows]}

    @app.post(base+"/staff/feedback/{feedback_id}/review")
    def review(slug:str,feedback_id:UUID,body:Review,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.review_feedback(%s,%s,%s,%s)",(actor(authorization),slug,feedback_id,body.action))
        return {"id":str(feedback_id),"state":r[0]}
