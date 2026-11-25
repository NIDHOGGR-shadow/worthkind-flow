"""Real Paystack HTTP adapter. No provider secrets, live calls or customer PII in logs."""
import hashlib
import hmac
import json
import os
import re
import time
from urllib.parse import quote,urlsplit
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
from supabase_identity import NoRedirect

class ProviderUnavailable(RuntimeError):
    pass

def account(slug):
    try:
        entries=json.loads(os.environ["WF_PAYSTACK_ACCOUNTS_JSON"])
        if not isinstance(entries,dict):
            raise ValueError()
        cfg=entries[slug]
        if not isinstance(cfg,dict) or cfg["mode"] not in ("test","live"):
            raise ValueError()
        if cfg["mode"]=="live" and os.getenv("WF_PAYSTACK_LIVE_ENABLED")!="1":
            raise ValueError()
        key=cfg["secret_key"]
        if not isinstance(key,str) or not key.startswith("sk_"+cfg["mode"]+"_") or len(key)<16:
            raise ValueError()
        if not isinstance(cfg["alias"],str) or not re.fullmatch(r"[A-Za-z0-9_-]{3,80}",cfg["alias"]):
            raise ValueError()
        if any(other!=slug and isinstance(v,dict) and (v.get("alias")==cfg["alias"] or v.get("secret_key")==key) for other,v in entries.items()):
            raise ValueError()
        return cfg
    except (KeyError,TypeError,ValueError):
        raise ProviderUnavailable("Hotel payment account unavailable") from None

def call(cfg,method,path,payload=None,*,list_response=False):
    if not path.startswith("/") or path.startswith("//"):
        raise ProviderUnavailable("Invalid provider path")
    body=json.dumps(payload,separators=(",",":")).encode() if payload is not None else None
    req=Request("https://api.paystack.co"+path,data=body,method=method,headers={
        "Authorization":"Bearer "+cfg["secret_key"],"Accept":"application/json","Content-Type":"application/json"})
    try:
        with build_opener(NoRedirect()).open(req,timeout=15) as response:
            raw=response.read(524289)
        if len(raw)>524288:
            raise ValueError()
        result=json.loads(raw)
        if not isinstance(result,dict) or result.get("status") is not True or not isinstance(result.get("data"),list if list_response else dict):
            raise ValueError()
        return {"data":result["data"],"meta":result.get("meta")} if list_response else result["data"]
    except (HTTPError,URLError,TimeoutError,OSError,ValueError):
        raise ProviderUnavailable("Paystack response unavailable or rejected") from None

def initialize(cfg,reference,amount,currency,email):
    result=call(cfg,"POST","/transaction/initialize",{"reference":reference,"amount":amount,"currency":currency,"email":email})
    url=result.get("authorization_url")
    if result.get("reference")!=reference or not isinstance(url,str):
        raise ProviderUnavailable("Unexpected checkout reference")
    parsed=urlsplit(url)
    if parsed.scheme!="https" or parsed.netloc!="checkout.paystack.com" or not parsed.path or parsed.username or parsed.password:
        raise ProviderUnavailable("Unexpected checkout URL")
    return url

def verify(cfg,reference):
    result=call(cfg,"GET","/transaction/verify/"+quote(reference,safe=""))
    if result.get("reference")!=reference:
        raise ProviderUnavailable("Unexpected verification reference")
    return result

def create_refund(cfg,reference,amount,currency):
    return call(cfg,"POST","/refund",{"transaction":reference,"amount":amount,"currency":currency})

def fetch_refund(cfg,refund_id):
    return call(cfg,"GET","/refund/"+quote(str(refund_id),safe=""))

def webhook_valid(cfg,body,new_header,legacy_header,now=None):
    if new_header:
        if len(new_header)>4096:
            return False
        parts=[p.strip().split("=",1) for p in new_header.split(",")]
        timestamps=[p[1] for p in parts if len(p)==2 and p[0]=="t"]
        if len(timestamps)!=1 or not re.fullmatch(r"[0-9]{1,12}",timestamps[0]):
            return False
        timestamp=timestamps[0]
        if abs((time.time() if now is None else now)-int(timestamp))>300:
            return False
        secrets=cfg.get("webhook_secrets",{})
        if not isinstance(secrets,dict):
            return False
        for p in parts:
            if len(p)!=2 or p[0]!="v1" or ":" not in p[1]:
                continue
            kid,signature=p[1].split(":",1)
            secret=secrets.get(kid)
            if not isinstance(secret,str) or not secret.startswith("whsec_") or not re.fullmatch(r"[0-9a-f]{128}",signature):
                continue
            expected=hmac.new(secret.encode(),timestamp.encode()+b"."+body,hashlib.sha512).hexdigest()
            if hmac.compare_digest(expected,signature):
                return True
        return False
    if cfg.get("allow_legacy_webhook") is not True or not isinstance(legacy_header,str) or not re.fullmatch(r"[0-9a-f]{128}",legacy_header):
        return False
    return hmac.compare_digest(hmac.new(cfg["secret_key"].encode(),body,hashlib.sha512).hexdigest(),legacy_header)


def settlements(cfg,page=1):
    return call(cfg,"GET",f"/settlement?perPage=50&page={page}",list_response=True)

def settlement_transactions(cfg,settlement_id,page=1):
    if type(settlement_id) is not int or not 0<settlement_id<2**64:
        raise ProviderUnavailable("Invalid settlement identifier")
    return call(cfg,"GET",f"/settlement/{settlement_id}/transactions?perPage=50&page={page}",list_response=True)
