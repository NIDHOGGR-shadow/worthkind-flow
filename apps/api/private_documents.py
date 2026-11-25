"""Bounded encrypted document storage. Download as attachment only."""
import base64
import binascii
import os
from uuid import UUID, uuid4
import psycopg
from psycopg import errors
from fastapi import Header, HTTPException, Response, Request
from guest_postgres import encrypt_json,decrypt_json,GuestStorageError,GuestStorageNotConfigured
from staff_oidc import verified_provider_subject,StaffTokenRejected,StaffAuthConfigurationError

MAX_BYTES=2_000_000


def subject_and_dsn(authorization):
    try:
        subject=verified_provider_subject(authorization)
    except StaffTokenRejected:
        raise HTTPException(401,"Bearer token rejected",headers={"WWW-Authenticate":"Bearer"}) from None
    except StaffAuthConfigurationError:
        raise HTTPException(503,"Staff identity unavailable") from None
    dsn=os.getenv("WF_DOCUMENT_POSTGRES_DSN")
    if not dsn:
        raise HTTPException(503,"Document storage unavailable")
    return subject,dsn


def store_command(dsn,query,params):
    try:
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_document_store")
                return conn.execute(query,params).fetchone()[0]
    except errors.InsufficientPrivilege:
        raise HTTPException(403,"Document access denied") from None
    except errors.NoDataFound:
        raise HTTPException(404,"Document unavailable") from None
    except psycopg.Error:
        raise HTTPException(503,"Document storage unavailable") from None


def install_document_routes(app):
    @app.post("/api/v1/properties/{slug}/staff/documents",status_code=201)
    async def upload(slug:str,request:Request,authorization:str|None=Header(None)):
        subject,dsn=subject_and_dsn(authorization)
        data=bytearray()
        async for chunk in request.stream():
            if len(data)+len(chunk)>MAX_BYTES:
                raise HTTPException(413,"Document exceeds size limit")
            data.extend(chunk)
        if not data:
            raise HTTPException(422,"Document is empty")
        doc_id=uuid4()
        try:
            cipher=encrypt_json({"data":base64.b64encode(data).decode("ascii")},associated_data=f"wf:doc:{slug}:{doc_id}")
        except GuestStorageNotConfigured:
            raise HTTPException(503,"Encryption unavailable") from None
        from starlette.concurrency import run_in_threadpool
        await run_in_threadpool(store_command,dsn,"SELECT worthkind_flow.write_private_document(%s,%s,%s,%s)",(subject,slug,doc_id,cipher))
        return {"document_id":str(doc_id),"size":len(data)}

    @app.get("/api/v1/properties/{slug}/staff/documents/{doc_id}")
    def download(slug:str,doc_id:UUID,authorization:str|None=Header(None)):
        subject,dsn=subject_and_dsn(authorization)
        cipher=store_command(dsn,"SELECT worthkind_flow.read_private_document(%s,%s,%s)",(subject,slug,doc_id))
        try:
            data=base64.b64decode(decrypt_json(cipher,associated_data=f"wf:doc:{slug}:{doc_id}")["data"],validate=True)
        except (GuestStorageError,GuestStorageNotConfigured,KeyError,TypeError,binascii.Error):
            raise HTTPException(503,"Document unavailable") from None
        return Response(data,media_type="application/octet-stream",headers={"Content-Disposition":"attachment","X-Content-Type-Options":"nosniff","Cache-Control":"no-store"})
