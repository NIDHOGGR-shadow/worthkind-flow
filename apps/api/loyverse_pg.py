"""Read-only Loyverse receipt reconciliation; not payment settlement."""
import json
import os
import re
from decimal import Decimal,InvalidOperation
from datetime import datetime
from uuid import UUID
from urllib.parse import quote
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
import psycopg
from psycopg import errors
from fastapi import Header,HTTPException
from pydantic import BaseModel,Field
from supabase_identity import NoRedirect
from operations_pg import actor,command

class Receipt(BaseModel):
    receipt_number:str=Field(min_length=1,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")


def account(slug,expected):
    try:
        accounts=json.loads(os.environ["WF_LOYVERSE_ACCOUNTS_JSON"])
        cfg=accounts[slug]
        if (cfg["store_id"],cfg["alias"],cfg["currency"],cfg["minor_digits"])!=tuple(expected):
            raise ValueError()
        if not isinstance(cfg["access_token"],str) or not cfg["access_token"]:
            raise ValueError()
        if any(k!=slug and v.get("access_token")==cfg["access_token"] for k,v in accounts.items()):
            raise ValueError()
        return cfg
    except (KeyError,ValueError,TypeError,AttributeError):
        raise HTTPException(503,"POS account unavailable") from None


def fetch(cfg,number):
    req=Request("https://api.loyverse.com/v1.0/receipts/"+quote(number,safe=""),headers={"Authorization":"Bearer "+cfg["access_token"],"Accept":"application/json"})
    try:
        with build_opener(NoRedirect()).open(req,timeout=15) as response:
            raw=response.read(524289)
        if len(raw)>524288:
            raise ValueError()
        return json.loads(raw,parse_float=Decimal)
    except (HTTPError,URLError,TimeoutError,OSError,ValueError):
        raise HTTPException(503,"POS receipt unavailable") from None


def receipt_view(cfg,number,data):
    if not isinstance(data,dict) or data.get("receipt_number")!=number or data.get("store_id")!=cfg["store_id"]:
        raise HTTPException(502,"POS receipt or store mismatch")
    if data.get("receipt_type") not in ("SALE","REFUND"):
        raise HTTPException(502,"Unsupported receipt type")
    try:
        amount=data["total_money"]
        if type(amount) not in (int,Decimal,str):
            raise ValueError()
        minor=Decimal(amount)*10**cfg["minor_digits"]
        if not minor.is_finite() or minor!=minor.to_integral_value() or not 0<=minor<=10**15:
            raise ValueError()
        created=datetime.fromisoformat(data["created_at"].replace("Z","+00:00"))
        updated=datetime.fromisoformat(data["updated_at"].replace("Z","+00:00"))
        if created.tzinfo is None or updated.tzinfo is None or updated<created:
            raise ValueError()
        return int(minor),data["receipt_type"],created,updated
    except (KeyError,TypeError,ValueError,InvalidOperation,AttributeError):
        raise HTTPException(502,"Invalid POS receipt fields") from None


def record(subject,slug,order_id,cfg,number,view):
    dsn=os.getenv("WF_POS_PROVIDER_POSTGRES_DSN")
    if not dsn:
        raise HTTPException(503,"POS evidence database unavailable")
    amount,kind,created,updated=view
    try:
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_pos_provider")
                return conn.execute("SELECT worthkind_flow.record_pos_receipt(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (subject,slug,order_id,cfg["alias"],cfg["store_id"],number,amount,cfg["currency"],kind,created,updated)).fetchone()[0]
    except errors.InsufficientPrivilege:
        raise HTTPException(403,"POS account access denied") from None
    except errors.NoDataFound:
        raise HTTPException(404,"Order unavailable") from None
    except errors.UniqueViolation:
        raise HTTPException(409,"Receipt already assigned") from None
    except psycopg.Error:
        raise HTTPException(503,"POS evidence unavailable") from None


def install_pos_routes(app):
    base="/api/v1/properties/{slug}/staff/pos"
    @app.post(base+"/orders/{order_id}/reconcile")
    def reconcile(slug:str,order_id:UUID,body:Receipt,authorization:str|None=Header(None)):
        subject=actor(authorization)
        expected=command("SELECT * FROM worthkind_flow.staff_pos_account(%s,%s,%s)",(subject,slug,order_id))
        cfg=account(slug,expected)
        raw=fetch(cfg,body.receipt_number)
        if isinstance(raw,dict) and raw.get('cancelled_at') is not None:
            raise HTTPException(409,'Cancelled receipt cannot be linked; refresh existing evidence instead')
        view=receipt_view(cfg,body.receipt_number,raw)
        evidence=record(subject,slug,order_id,cfg,body.receipt_number,view)
        return {"evidence":evidence,"payment_settled_by_this_action":False,"source":"loyverse"}

    @app.get(base+"/reconciliation")
    def overview(slug:str,authorization:str|None=Header(None)):
        return {"receipts":command("SELECT worthkind_flow.pos_reconciliation(%s,%s)",(actor(authorization),slug))[0],"source":"loyverse"}
