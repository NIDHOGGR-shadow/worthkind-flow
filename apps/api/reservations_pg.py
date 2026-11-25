"""Guest stay requests and reception review; PMS confirmation is separate."""
from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import Header,Depends,HTTPException
from pydantic import BaseModel,Field
from guest_quota import enforce_guest_quota
from guest_records_pg import proof
from operations_pg import actor,command

class StayRequest(BaseModel):
    request_key:str=Field(min_length=8,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")
    room_type_id:UUID|None=None
    arrival:date
    departure:date
    adults:int=Field(ge=1,le=30)
    children:int=Field(default=0,ge=0,le=30)
    room_count:int=Field(default=1,ge=1,le=10)

class ReviewIntent(BaseModel):
    action:Literal["review","decline"]


def install_reservation_routes(app):
    base="/api/v1/properties/{slug}"
    g=base+"/guest/cases/{case_id}/reservation-intents"
    @app.post(g,status_code=201,dependencies=[Depends(enforce_guest_quota)])
    def request(slug:str,case_id:UUID,body:StayRequest,x_receipt_token:str|None=Header(None)):
        if not 1<=(body.departure-body.arrival).days<=90:
            raise HTTPException(422,"Invalid stay length")
        r=command("SELECT * FROM worthkind_flow.request_reservation(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (slug,case_id,proof(x_receipt_token),body.room_type_id,body.arrival,body.departure,body.adults,body.children,body.room_count,body.request_key),guest=True)
        return {"id":str(r[0]),"state":r[1],"duplicate":r[2],"booking_confirmed":False,"inventory_held":False}

    @app.post(g+"/{intent_id}/withdraw",dependencies=[Depends(enforce_guest_quota)])
    def withdraw(slug:str,case_id:UUID,intent_id:UUID,x_receipt_token:str|None=Header(None)):
        r=command("SELECT worthkind_flow.withdraw_reservation(%s,%s,%s,%s)",(slug,case_id,proof(x_receipt_token),intent_id),guest=True)
        return {"id":str(intent_id),"state":r[0],"booking_confirmed":False}

    @app.get(base+"/staff/reservation-intents")
    def queue(slug:str,authorization:str|None=Header(None)):
        return {"intents":command("SELECT worthkind_flow.reservation_queue(%s,%s)",(actor(authorization),slug))[0],"pms_confirmed":False}

    @app.post(base+"/staff/reservation-intents/{intent_id}/review")
    def review(slug:str,intent_id:UUID,body:ReviewIntent,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.review_reservation_intent(%s,%s,%s,%s)",(actor(authorization),slug,intent_id,body.action))
        return {"id":str(intent_id),"state":r[0],"booking_confirmed":False}
