"""Database-backed quota for versioned guest endpoints."""
import hashlib
import hmac
import os
import psycopg
from psycopg import errors
from fastapi import HTTPException, Request


def enforce_guest_quota(slug: str, request: Request):
    dsn=os.getenv("WF_GUEST_QUOTA_POSTGRES_DSN")
    secret=os.getenv("WF_GUEST_QUOTA_SECRET")
    if not dsn or not secret or len(secret)<32:
        raise HTTPException(503,"Guest quota service unavailable")
    # ASGI peer address only. Configure trusted reverse proxies at the server;
    # never trust arbitrary X-Forwarded-For headers from clients.
    peer=request.client.host if request.client else "unknown"
    bucket=hmac.new(secret.encode(),peer.encode(),hashlib.sha256).hexdigest()
    try:
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_guest_quota")
                allowed=conn.execute("SELECT worthkind_flow.consume_guest_quota(%s,%s)",(slug,bucket)).fetchone()[0]
    except errors.NoDataFound:
        raise HTTPException(404,"Hotel unavailable") from None
    except psycopg.Error:
        raise HTTPException(503,"Guest quota service unavailable") from None
    if not allowed:
        raise HTTPException(429,"Guest request limit reached",headers={"Retry-After":"60"})
