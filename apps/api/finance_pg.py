"""Hotel service invoicing and verified Paystack payments, separate from platform billing."""
import json
import os
import re
from typing import Literal
from uuid import UUID
from decimal import Decimal
import psycopg
from psycopg import errors
from fastapi import Header,HTTPException,Request
from pydantic import BaseModel,Field
from starlette.concurrency import run_in_threadpool
from operations_pg import actor,command
from paystack_provider import account,initialize,verify,create_refund,fetch_refund,webhook_valid,ProviderUnavailable

class Invoice(BaseModel):
    dining_order_id:UUID

class Checkout(BaseModel):
    email:str=Field(min_length=5,max_length=254,pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

class Refund(BaseModel):
    payment_id:UUID
    reason:str=Field(min_length=8,max_length=240)
    amount_minor:int|None=Field(default=None,gt=0,le=900000000000000)
    request_key:str|None=Field(default=None,min_length=8,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")

class Decision(BaseModel):
    action:Literal["approve","decline"]


def provider_command(query,params):
    dsn=os.getenv("WF_PAYMENT_PROVIDER_POSTGRES_DSN")
    if not dsn:
        raise HTTPException(503,"Payment provider database unavailable")
    try:
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_payment_provider")
                return conn.execute(query,params).fetchone()
    except errors.NoDataFound:
        raise HTTPException(404,"Payment unavailable") from None
    except psycopg.Error:
        raise HTTPException(503,"Payment reconciliation unavailable") from None


def configured(slug,alias=None,mode=None):
    try:
        cfg=account(slug)
        if alias is not None and (cfg["alias"]!=alias or cfg["mode"]!=mode):
            raise ProviderUnavailable("Payment account mismatch")
        if not os.getenv("WF_PAYMENT_PROVIDER_POSTGRES_DSN"):
            raise ProviderUnavailable("Provider database unavailable")
        return cfg
    except ProviderUnavailable:
        raise HTTPException(503,"Hotel payment integration unavailable") from None


def verify_and_record(slug,reference,cfg):
    expected=provider_command("SELECT * FROM worthkind_flow.provider_payment_lookup(%s,%s)",(slug,reference))
    if expected is None:
        return "unknown_reference"
    if expected[0]!=cfg["alias"] or expected[1]!=cfg["mode"]:
        raise HTTPException(503,"Payment account mismatch")
    try:
        result=verify(cfg,reference)
    except ProviderUnavailable:
        raise HTTPException(503,"Payment verification unavailable") from None
    if result.get("status")!="success":
        return "not_verified"
    transaction=result.get("id")
    amount=result.get("amount")
    if type(transaction) is not int or type(amount) is not int:
        raise HTTPException(502,"Invalid provider transaction response")
    return provider_command("SELECT worthkind_flow.record_verified_payment(%s,%s,%s,%s,%s,%s,%s)",
        (slug,reference,cfg["alias"],result.get("domain"),transaction,amount,result.get("currency")))[0]


def refund_record(slug,refund_id,data):
    txn=data.get("transaction")
    if isinstance(txn,dict):
        txn=txn.get("id")
    values=(data.get("id"),txn,data.get("amount"))
    if any(type(v) is not int for v in values):
        raise HTTPException(502,"Invalid provider refund response")
    return provider_command("SELECT worthkind_flow.record_refund_result(%s,%s,%s,%s,%s,%s,%s,%s)",
        (slug,refund_id,values[0],txn,data.get("domain"),values[2],data.get("currency"),data.get("status")))[0]


def install_finance_routes(app):
    base="/api/v1/properties/{slug}/staff/finance"

    @app.get(base)
    def overview(slug:str,authorization:str|None=Header(None)):
        return command("SELECT worthkind_flow.finance_overview(%s,%s)",(actor(authorization),slug))[0]

    @app.post(base+"/invoices",status_code=201)
    def invoice(slug:str,body:Invoice,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.issue_dining_invoice(%s,%s,%s)",(actor(authorization),slug,body.dining_order_id))
        return {"id":str(r[0]),"source":"hotel_dining_order"}

    @app.post(base+"/invoices/{invoice_id}/checkout")
    def checkout(slug:str,invoice_id:UUID,body:Checkout,authorization:str|None=Header(None)):
        subject=actor(authorization)
        cfg=configured(slug)
        r=command("SELECT * FROM worthkind_flow.begin_hotel_payment(%s,%s,%s)",(subject,slug,invoice_id))
        pid,ref,alias,mode,amount,currency,state,url,submit=r
        if alias!=cfg["alias"] or mode!=cfg["mode"]:
            if submit:
                provider_command("SELECT worthkind_flow.payment_checkout_result(%s,%s,%s,%s)",(slug,ref,None,False))
            raise HTTPException(503,"Hotel payment account mismatch")
        if submit:
            try:
                url=initialize(cfg,ref,amount,currency,body.email)
                state=provider_command("SELECT worthkind_flow.payment_checkout_result(%s,%s,%s,%s)",(slug,ref,url,True))[0]
            except ProviderUnavailable:
                provider_command("SELECT worthkind_flow.payment_checkout_result(%s,%s,%s,%s)",(slug,ref,None,False))
                raise HTTPException(503,"Checkout outcome unknown; reconcile the existing reference before retrying") from None
        return {"id":str(pid),"reference":ref,"state":state,"checkout_url":url if state=="pending" else None,"mode":mode,"payment_confirmed":state=="verified" and mode=="live"}

    @app.post(base+"/payments/{payment_id}/verify")
    def reconcile(slug:str,payment_id:UUID,authorization:str|None=Header(None)):
        r=command("SELECT * FROM worthkind_flow.staff_payment_lookup(%s,%s,%s)",(actor(authorization),slug,payment_id))
        state=verify_and_record(slug,r[0],configured(slug,r[1],r[2]))
        return {"id":str(payment_id),"state":state,"mode":r[2],"payment_confirmed":state=="verified" and r[2]=="live"}

    @app.post(base+"/refunds",status_code=201)
    def request_refund(slug:str,body:Refund,authorization:str|None=Header(None)):
        subject=actor(authorization)
        if body.amount_minor is not None and body.request_key is None:
            raise HTTPException(422,"Idempotency key required for partial refund")
        if body.request_key is None:
            r=command("SELECT worthkind_flow.request_hotel_refund(%s,%s,%s,%s)",(subject,slug,body.payment_id,body.reason))
        else:
            r=command("SELECT worthkind_flow.request_partial_hotel_refund(%s,%s,%s,%s,%s,%s)",(subject,slug,body.payment_id,body.reason,body.amount_minor,body.request_key))
        return {"id":str(r[0]),"state":"requested"}

    @app.post(base+"/refunds/{refund_id}/decision")
    def decide(slug:str,refund_id:UUID,body:Decision,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.decide_hotel_refund(%s,%s,%s,%s)",(actor(authorization),slug,refund_id,body.action))
        return {"id":str(refund_id),"state":r[0]}

    @app.post(base+"/refunds/{refund_id}/submit")
    def submit(slug:str,refund_id:UUID,authorization:str|None=Header(None)):
        subject=actor(authorization)
        info=command("SELECT * FROM worthkind_flow.staff_refund_lookup(%s,%s,%s)",(subject,slug,refund_id))
        cfg=configured(slug,info[0],info[1])
        r=command("SELECT * FROM worthkind_flow.begin_refund_submission(%s,%s,%s)",(subject,slug,refund_id))
        if r[1]!=cfg["alias"] or r[2]!=cfg["mode"]:
            raise HTTPException(503,"Refund account mismatch")
        try:
            result=create_refund(cfg,r[0],r[3],r[4])
        except ProviderUnavailable:
            provider_command("SELECT worthkind_flow.record_refund_result(%s,%s,%s,%s,%s,%s,%s,%s)",(slug,refund_id,None,None,None,None,None,"unknown"))
            raise HTTPException(503,"Refund outcome unknown; do not resubmit before provider reconciliation") from None
        return {"id":str(refund_id),"state":refund_record(slug,refund_id,result),"mode":r[2]}

    @app.post(base+"/refunds/{refund_id}/verify")
    def refund_verify(slug:str,refund_id:UUID,authorization:str|None=Header(None)):
        r=command("SELECT * FROM worthkind_flow.staff_refund_lookup(%s,%s,%s)",(actor(authorization),slug,refund_id))
        cfg=configured(slug,r[0],r[1])
        if r[2] is None:
            raise HTTPException(409,"Provider refund ID unknown; reconcile using provider dashboard")
        try:
            data=fetch_refund(cfg,int(r[2]))
        except ProviderUnavailable:
            raise HTTPException(503,"Refund verification unavailable") from None
        return {"id":str(refund_id),"state":refund_record(slug,refund_id,data),"mode":r[1]}

    @app.post("/api/v1/properties/{slug}/webhooks/paystack")
    async def webhook(slug:str,request:Request):
        cfg=configured(slug)
        raw=bytearray()
        async for chunk in request.stream():
            if len(raw)+len(chunk)>262144:
                raise HTTPException(413,"Webhook too large")
            raw.extend(chunk)
        if not webhook_valid(cfg,bytes(raw),request.headers.get("paystack-signature"),request.headers.get("x-paystack-signature")):
            raise HTTPException(401,"Webhook signature rejected")
        try:
            event=json.loads(raw)
        except ValueError:
            raise HTTPException(400,"Invalid webhook") from None
        if not isinstance(event,dict):
            raise HTTPException(400,"Invalid webhook")
        if event.get("event")!="charge.success":
            return {"accepted":True,"handled":False}
        data=event.get("data")
        ref=data.get("reference") if isinstance(data,dict) else None
        if not isinstance(ref,str) or not re.fullmatch(r"wf-[0-9a-f-]{36}",ref):
            return {"accepted":True,"handled":False}
        state=await run_in_threadpool(verify_and_record,slug,ref,cfg)
        return {"accepted":True,"state":state}
