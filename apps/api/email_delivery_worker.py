"""Transactional Resend delivery with a bounded retry window and provider readback."""
import json
import logging
import os
import re
import signal
import time
from uuid import UUID
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
import psycopg
from guest_postgres import decrypt_json,GuestStorageError,GuestStorageNotConfigured
from supabase_identity import NoRedirect

log=logging.getLogger("wf.email_delivery")
running=True
def stop(*_):
    global running
    running=False

def db(query,params=()):
    with psycopg.connect(os.environ["WF_EMAIL_DELIVERY_POSTGRES_DSN"],connect_timeout=5) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE wf_email_delivery")
            conn.execute("SET LOCAL statement_timeout='10s'")
            return conn.execute(query,params).fetchone()

def valid_email(value):
    return isinstance(value,str) and value.isascii() and len(value)<=254 and bool(re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:[.][A-Za-z0-9-]+)+",value))

def request_json(path,key,payload=None,idempotency=None):
    headers={"Authorization":"Bearer "+key,"Accept":"application/json"}
    if payload is not None:
        headers["Content-Type"]="application/json"
        headers["Idempotency-Key"]=idempotency
    req=Request("https://api.resend.com"+path,data=json.dumps(payload,separators=(",",":")).encode() if payload is not None else None,
                headers=headers,method="POST" if payload is not None else "GET")
    with build_opener(NoRedirect()).open(req,timeout=15) as response:
        raw=response.read(131073)
    if len(raw)>131072:
        raise ValueError("Invalid provider response")
    result=json.loads(raw)
    if not isinstance(result,dict):
        raise ValueError("Invalid provider response")
    return result

def send_email(job,sender,recipient,key):
    if not valid_email(sender) or not valid_email(recipient):
        raise ValueError("Invalid email address")
    result=request_json("/emails",key,{"from":sender,"to":[recipient],"subject":"An update from your hotel",
        "text":"Your hotel has updated your service request. Open the hotel service page and use your original receipt to check its status. Do not reply with private information."},"wf-service-"+str(job))
    return UUID(result["id"])

def read_delivery(provider_id,key):
    result=request_json("/emails/"+str(UUID(str(provider_id))),key)
    if UUID(result["id"])!=provider_id:
        raise ValueError("Provider reference mismatch")
    state=result.get("last_event")
    if state=="delivered":
        return "delivered"
    if state in ("bounced","failed","suppressed","complained"):
        return "failed"
    return "retry"

def run_once():
    job=db("SELECT * FROM worthkind_flow.lease_email_notification()")
    if not job:
        return False
    jid,lease,state,alias,sender,provider_id=job
    outcome="retry"
    try:
        cfg=json.loads(os.environ["WF_RESEND_ACCOUNTS_JSON"])[alias]
        if not isinstance(cfg,dict):
            raise ValueError("Invalid configuration")
        key=cfg["send_key" if state=="pending" else "read_key"]
        if not isinstance(key,str) or not key.startswith("re_"):
            raise ValueError("Invalid configuration")
        if state=="pending":
            payload=db("SELECT * FROM worthkind_flow.email_notification_payload(%s,%s)",(jid,lease))
            if not payload:
                outcome="suppressed"
            else:
                slug,request_key,cipher=payload
                recipient=decrypt_json(cipher,associated_data=f"wf:guest:{slug}:{request_key}").get("contact")
                if not valid_email(recipient):
                    outcome="suppressed"
                else:
                    provider_id=send_email(jid,sender,recipient,key)
                    outcome="accepted"
        else:
            outcome=read_delivery(provider_id,key)
    except HTTPError as e:
        if state=="pending" and e.code in (400,401,403,422):
            outcome="failed"
    except (URLError,TimeoutError,OSError,ValueError,TypeError,KeyError,AttributeError,GuestStorageError,GuestStorageNotConfigured):
        pass
    db("SELECT worthkind_flow.complete_email_notification(%s,%s,%s,%s)",(jid,lease,outcome,provider_id))
    return True

def main():
    if os.getenv("WF_EMAIL_DELIVERY_ENABLED")!="1" or not os.getenv("WF_EMAIL_DELIVERY_POSTGRES_DSN") or not os.getenv("WF_RESEND_ACCOUNTS_JSON"):
        raise SystemExit("Email delivery is not configured or enabled")
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    while running:
        try:
            run_once()
        except psycopg.Error:
            log.warning("Email delivery database unavailable")
        for _ in range(5):
            if not running:
                break
            time.sleep(1)

if __name__=="__main__":
    main()
