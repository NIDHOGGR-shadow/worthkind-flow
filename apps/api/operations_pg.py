"""Versioned operational ticket API using encrypted PostgreSQL records."""
import hashlib
import json
import os
from typing import Literal
from uuid import UUID
import psycopg
from psycopg import errors
from psycopg.types.json import Jsonb
from fastapi import Header, HTTPException, Query
from pydantic import BaseModel, Field
from guest_postgres import encrypt_json,decrypt_json,GuestStorageNotConfigured,GuestStorageError
from staff_oidc import verified_provider_subject,StaffTokenRejected,StaffAuthConfigurationError


class TicketCreate(BaseModel):
    request_key:str=Field(min_length=8,max_length=100,pattern=r"^[A-Za-z0-9_-]+$")
    category:Literal["it","reception","housekeeping","maintenance","kitchen","billing","general"]
    priority:Literal["low","normal","high","urgent"]="normal"
    subject:str=Field(min_length=4,max_length=160)
    description:str=Field(min_length=8,max_length=3000)
    origin_case_id:UUID|None=None

class TicketChange(BaseModel):
    action:Literal["claim","start","resolve","reopen","note"]
    note:str|None=Field(default=None,min_length=4,max_length=1500)


def actor(authorization):
    try:
        return verified_provider_subject(authorization)
    except StaffTokenRejected:
        raise HTTPException(401,"Bearer token rejected",headers={"WWW-Authenticate":"Bearer"}) from None
    except StaffAuthConfigurationError:
        raise HTTPException(503,"Identity unavailable") from None


def command(query,params,*,many=False,public=False):
    dsn=os.getenv("WF_PUBLIC_CONTENT_POSTGRES_DSN" if public else "WF_OPERATIONS_POSTGRES_DSN")
    if not dsn:
        raise HTTPException(503,"Operations database unavailable")
    try:
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_public_content" if public else "SET LOCAL ROLE wf_operations")
                cursor=conn.execute(query,params)
                return cursor.fetchall() if many else cursor.fetchone()
    except errors.InsufficientPrivilege:
        raise HTTPException(403,"Operations access denied") from None
    except errors.NoDataFound:
        raise HTTPException(404,"Record unavailable") from None
    except (errors.UniqueViolation,errors.CheckViolation):
        raise HTTPException(409,"Operation conflicts with current state") from None
    except psycopg.Error:
        raise HTTPException(503,"Operations database unavailable") from None


def encrypt(value,aad):
    try:
        return encrypt_json(value,associated_data=aad)
    except GuestStorageNotConfigured:
        raise HTTPException(503,"Encryption unavailable") from None


def decrypt(value,aad):
    try:
        return decrypt_json(value,associated_data=aad)
    except (GuestStorageNotConfigured,GuestStorageError):
        raise HTTPException(503,"Encrypted record unavailable") from None


def install_operations_pg_routes(app):
    @app.post("/api/v1/properties/{slug}/staff/tickets",status_code=201)
    def create(slug:str,body:TicketCreate,authorization:str|None=Header(None)):
        subject=actor(authorization)
        data=body.model_dump(mode="json",exclude={"request_key"})
        digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
        cipher=encrypt({"subject":body.subject,"description":body.description},f"wf:ticket:{slug}:{body.request_key}")
        row=command("SELECT * FROM worthkind_flow.create_ticket(%s,%s,%s,%s,%s,%s,%s,%s)",
            (subject,slug,body.request_key,digest,body.category,body.priority,cipher,body.origin_case_id))
        return {"ticket_id":str(row[0]),"status":row[1],"duplicate":row[2]}

    @app.get("/api/v1/properties/{slug}/staff/tickets")
    def list_tickets(slug:str,limit:int=Query(100,ge=1,le=100),authorization:str|None=Header(None)):
        rows=command("SELECT * FROM worthkind_flow.list_tickets(%s,%s,%s)",(actor(authorization),slug,limit),many=True)
        return {"tickets":[{"id":str(r[0]),"category":r[2],"priority":r[3],"status":r[4],
            "assignee":str(r[5]) if r[5] else None,"due_at":r[6].isoformat(),"overdue":r[8],
            **decrypt(r[7],f"wf:ticket:{slug}:{r[1]}")} for r in rows]}

    @app.post("/api/v1/properties/{slug}/staff/tickets/{ticket_id}/transition")
    def transition(slug:str,ticket_id:UUID,body:TicketChange,authorization:str|None=Header(None)):
        subject=actor(authorization)
        note=encrypt({"note":body.note},f"wf:ticket-note:{slug}:{ticket_id}") if body.note else None
        row=command("SELECT worthkind_flow.transition_ticket(%s,%s,%s,%s,%s)",(subject,slug,ticket_id,body.action,note))
        return {"ticket_id":str(ticket_id),"status":row[0],"notifications_live":False}


class ContentDraft(BaseModel):
    key:str=Field(min_length=2,max_length=80,pattern=r"^[a-z0-9][a-z0-9_-]+$")
    title:str=Field(min_length=2,max_length=160)
    body:str=Field(min_length=8,max_length=3500)
    source_reference:str=Field(min_length=8,max_length=240)

class ContentDecision(BaseModel):
    action:Literal["publish","reject","withdraw"]


def install_content_pg_routes(app):
    @app.get("/api/v1/properties/{slug}/content")
    def public_content(slug:str):
        rows=command("SELECT * FROM worthkind_flow.read_public_content(%s)",(slug,),many=True,public=True)
        return {"content":[{"key":r[0],"version":r[1],"content":r[2]} for r in rows],
                "live_inventory":False,"live_price":False}

    @app.get("/api/v1/properties/{slug}/staff/content")
    def list_content(slug:str,authorization:str|None=Header(None)):
        rows=command("SELECT * FROM worthkind_flow.list_content(%s,%s)",(actor(authorization),slug),many=True)
        return {"content":[{"id":str(r[0]),"key":r[1],"version":r[2],"content":r[3],"state":r[4],"source_reference":r[5]} for r in rows]}

    @app.post("/api/v1/properties/{slug}/staff/content",status_code=201)
    def draft(slug:str,body:ContentDraft,authorization:str|None=Header(None)):
        row=command("SELECT worthkind_flow.draft_content(%s,%s,%s,%s,%s)",(actor(authorization),slug,body.key,Jsonb({"title":body.title,"body":body.body}),body.source_reference))
        return {"id":str(row[0]),"state":"draft"}

    @app.post("/api/v1/properties/{slug}/staff/content/{content_id}/decision")
    def decide(slug:str,content_id:UUID,body:ContentDecision,authorization:str|None=Header(None)):
        row=command("SELECT worthkind_flow.decide_content(%s,%s,%s,%s)",(actor(authorization),slug,content_id,body.action))
        return {"id":str(content_id),"state":row[0]}
