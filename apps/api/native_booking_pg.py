"""Native hotel inventory, enabled only after operator approval of inventory authority."""
from datetime import date
from uuid import UUID
from typing import Literal
from fastapi import Header,Depends,HTTPException
from pydantic import BaseModel,Field,StrictBool
from guest_quota import enforce_guest_quota
from guest_records_pg import proof
from operations_pg import actor,command,encrypt

class BookableRate(BaseModel):
    room_type_id:UUID
    code:str=Field(min_length=2,max_length=40,pattern=r"^[A-Za-z0-9_-]+$")
    currency:str=Field(pattern=r"^[A-Z]{3}$")
    nightly_total_minor:int=Field(ge=1,le=1000000000000)
    start_date:date
    end_date:date
    policy_reference:str=Field(min_length=8,max_length=240)
    active:StrictBool=True
    revision:int=Field(ge=0)

class Hold(BaseModel):
    intent_id:UUID
    room_type_id:UUID
    rate_id:UUID
    request_key:str=Field(min_length=8,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")

class Confirm(BaseModel):
    expected_total_minor:int=Field(ge=1,le=900000000000000)
    payment_method:Literal["pay_at_property"]
    accept_terms:Literal[True]

class Change(BaseModel):
    revision:int=Field(ge=1)
    arrival:date
    departure:date
    rate_id:UUID
    expected_total_minor:int=Field(ge=1,le=900000000000000)
    expected_currency:str=Field(pattern=r"^[A-Z]{3}$")
    policy_reference:str=Field(min_length=8,max_length=240)
    accept_terms:Literal[True]

class Cancel(BaseModel):
    revision:int=Field(ge=1)
    reason:str=Field(min_length=8,max_length=240)

class StayTransition(BaseModel):
    action:Literal["check_in","check_out","no_show"]
    revision:int=Field(ge=0)
    note:str|None=Field(default=None,min_length=8,max_length=1500)

def install_native_booking_routes(app):
    base="/api/v1/properties/{slug}"
    staff=base+"/staff/native-bookings"
    guest=base+"/guest/cases/{case_id}/native-bookings"

    @app.put(base+"/staff/bookable-rates")
    def rate(slug:str,body:BookableRate,authorization:str|None=Header(None)):
        if body.end_date<=body.start_date:
            raise HTTPException(422,"Invalid rate dates")
        r=command("SELECT * FROM worthkind_flow.save_bookable_rate(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (actor(authorization),slug,body.room_type_id,body.code,body.currency,body.nightly_total_minor,body.start_date,body.end_date,body.policy_reference,body.active,body.revision))
        return {"id":str(r[0]),"revision":r[1]}

    @app.post(staff+"/holds",status_code=201)
    def hold(slug:str,body:Hold,authorization:str|None=Header(None)):
        return command("SELECT worthkind_flow.hold_native_booking(%s,%s,%s,%s,%s,%s)",
        (actor(authorization),slug,body.intent_id,body.room_type_id,body.rate_id,body.request_key))[0]

    @app.get(staff)
    def list_staff(slug:str,authorization:str|None=Header(None)):
        return {"bookings":command("SELECT worthkind_flow.staff_native_bookings(%s,%s)",(actor(authorization),slug))[0],"source":"native_inventory"}

    @app.get(guest,dependencies=[Depends(enforce_guest_quota)])
    def list_guest(slug:str,case_id:UUID,x_receipt_token:str|None=Header(None)):
        return {"bookings":command("SELECT worthkind_flow.guest_native_bookings(%s,%s,%s)",(slug,case_id,proof(x_receipt_token)),guest=True)[0],"source":"native_inventory"}

    @app.post(guest+"/{booking_id}/confirm",dependencies=[Depends(enforce_guest_quota)])
    def confirm(slug:str,case_id:UUID,booking_id:UUID,body:Confirm,x_receipt_token:str|None=Header(None)):
        r=command("SELECT worthkind_flow.confirm_native_booking(%s,%s,%s,%s,%s)",
        (slug,case_id,proof(x_receipt_token),booking_id,body.expected_total_minor),guest=True)[0]
        return {"booking":r,"booking_confirmed":r["state"]=="confirmed","payment_confirmed":False,"payment_method":"pay_at_property","source":"native_inventory"}

    @app.post(staff+"/{booking_id}/cancel")
    def cancel(slug:str,booking_id:UUID,body:Cancel,authorization:str|None=Header(None)):
        return command("SELECT worthkind_flow.cancel_native_booking(%s,%s,%s,%s,%s)",
        (actor(authorization),slug,booking_id,body.revision,body.reason))[0]


    @app.get(base+"/native-availability",dependencies=[Depends(enforce_guest_quota)])
    def availability(slug:str,arrival:date,departure:date):
        if not 1<=(departure-arrival).days<=90:
            raise HTTPException(422,"Invalid stay range")
        rows=command("SELECT worthkind_flow.native_availability(%s,%s,%s)",(slug,arrival,departure),public=True)[0]
        return {"room_types":rows,"source":"native_inventory","inventory_held":False}

    @app.post(guest+"/{booking_id}/change-dates",dependencies=[Depends(enforce_guest_quota)])
    def change(slug:str,case_id:UUID,booking_id:UUID,body:Change,x_receipt_token:str|None=Header(None)):
        if not 1<=(body.departure-body.arrival).days<=90:
            raise HTTPException(422,"Invalid stay range")
        r=command("SELECT worthkind_flow.change_native_booking(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (slug,case_id,proof(x_receipt_token),booking_id,body.revision,body.arrival,body.departure,body.rate_id,body.expected_total_minor,body.expected_currency,body.policy_reference),guest=True)[0]
        return {"booking":r,"source":"native_inventory","payment_method":"pay_at_property"}


    @app.post(staff+"/{booking_id}/stay")
    def transition_stay(slug:str,booking_id:UUID,body:StayTransition,authorization:str|None=Header(None)):
        subject=actor(authorization)
        note=encrypt({"note":body.note},f"wf:stay:{slug}:{booking_id}") if body.note else None
        return {"stay":command("SELECT worthkind_flow.transition_native_stay(%s,%s,%s,%s,%s,%s)",
        (subject,slug,booking_id,body.action,body.revision,note))[0]}

    @app.get(staff+"/{booking_id}/folio")
    def folio(slug:str,booking_id:UUID,authorization:str|None=Header(None)):
        return command("SELECT worthkind_flow.native_stay_folio(%s,%s,%s)",(actor(authorization),slug,booking_id))[0]
