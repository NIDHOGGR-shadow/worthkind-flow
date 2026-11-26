"""Versioned operational ticket API using encrypted PostgreSQL records."""
import hashlib
import json
import os
from typing import Literal
from datetime import date
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


def command(query,params,*,many=False,public=False,guest=False):
    dsn=os.getenv("WF_GUEST_POSTGRES_DSN" if guest else "WF_PUBLIC_CONTENT_POSTGRES_DSN" if public else "WF_OPERATIONS_POSTGRES_DSN")
    if not dsn:
        raise HTTPException(503,"Operations database unavailable")
    try:
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_guest_api" if guest else "SET LOCAL ROLE wf_public_content" if public else "SET LOCAL ROLE wf_operations")
                cursor=conn.execute(query,params)
                return cursor.fetchall() if many else cursor.fetchone()
    except errors.InsufficientPrivilege:
        raise HTTPException(403,"Operations access denied") from None
    except errors.NoDataFound:
        raise HTTPException(404,"Record unavailable") from None
    except (errors.UniqueViolation,errors.CheckViolation,errors.SerializationFailure):
        raise HTTPException(409,"Operation conflicts with current state") from None
    except errors.InvalidParameterValue:
        raise HTTPException(422,"Invalid operational command") from None
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
    @app.get("/api/v1/properties/{slug}/staff/platform-subscription")
    def platform_subscription(slug:str,authorization:str|None=Header(None)):
        return command("SELECT worthkind_flow.read_platform_subscription(%s,%s)",(actor(authorization),slug))[0]

    @app.get("/api/v1/properties/{slug}/staff/reports/operations")
    def management_report(slug:str,authorization:str|None=Header(None)):
        return command("SELECT worthkind_flow.management_snapshot(%s,%s)",(actor(authorization),slug))[0]

    @app.get("/api/v1/properties/{slug}/staff/reports/payment-evidence")
    def payment_report(slug:str,authorization:str|None=Header(None)):
        return command("SELECT worthkind_flow.payment_evidence_summary(%s,%s)",(actor(authorization),slug))[0]

    @app.get("/api/v1/staff/properties")
    def staff_properties(after: str | None = Query(None,pattern=r"^[a-z0-9][a-z0-9-]{1,79}$"),
                         limit: int = Query(50,ge=1,le=100),authorization: str | None = Header(None)):
        rows=command("SELECT * FROM worthkind_flow.list_staff_properties(%s,%s,%s)",
                     (actor(authorization),after,limit+1),many=True)
        return {"properties":[{"id":str(r[0]),"slug":r[1],"display_name":r[2],"time_zone":r[3],
                               "role":r[4],"membership_state":r[5]} for r in rows[:limit]],
                "next_cursor":rows[limit-1][1] if len(rows)>limit else None}

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

    @app.get("/api/v1/properties/{slug}/staff/tickets/{ticket_id}")
    def ticket_detail(slug:str,ticket_id:UUID,authorization:str|None=Header(None)):
        subject=actor(authorization)
        r=command("SELECT * FROM worthkind_flow.ticket_detail(%s,%s,%s)",(subject,slug,ticket_id))
        history=command("SELECT * FROM worthkind_flow.ticket_history(%s,%s,%s)",(subject,slug,ticket_id),many=True)
        return {"id":str(r[0]),"category":r[2],"priority":r[3],"status":r[4],
                "assignee":str(r[5]) if r[5] else None,"due_at":r[6].isoformat(),
                "origin_case_id":str(r[8]) if r[8] else None,
                **decrypt(r[7],f"wf:ticket:{slug}:{r[1]}"),
                "history":[{"actor":str(h[0]) if h[0] else None,"action":h[1],
                            "note":decrypt(h[2],f"wf:ticket-note:{slug}:{ticket_id}").get("note") if h[2] else None,
                            "created_at":h[3].isoformat()} for h in history]}

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


class RoomTypeSave(BaseModel):
    code:str=Field(min_length=2,max_length=40,pattern=r"^[A-Za-z0-9_-]+$")
    name:str=Field(min_length=2,max_length=100)
    description:str=Field(default="",max_length=2000)
    max_guests:int=Field(ge=1,le=30)
    published:bool=False
    revision:int=Field(ge=0)

class RoomCreate(BaseModel):
    room_type_id:UUID
    label:str=Field(min_length=1,max_length=40)

class RoomState(BaseModel):
    state:Literal["unknown","clean","dirty","inspecting","out_of_service"]
    revision:int=Field(ge=1)

class DisplayRate(BaseModel):
    room_type_id:UUID
    code:str=Field(min_length=2,max_length=40,pattern=r"^[A-Za-z0-9_-]+$")
    currency:str=Field(pattern=r"^[A-Z]{3}$")
    amount_minor:int=Field(ge=0,le=1000000000000)
    start_date:date
    end_date:date
    revision:int=Field(ge=0)


def install_room_pg_routes(app):
    @app.get("/api/v1/properties/{slug}/rooms")
    def catalog(slug:str):
        rows=command("SELECT * FROM worthkind_flow.list_room_catalog(%s)",(slug,),many=True,public=True)
        return {"rooms":[{"id":str(r[0]),"code":r[1],"name":r[2],"description":r[3],"max_guests":r[4],"display_rates":r[5]} for r in rows],
                "live_availability":False,"rates_binding":False}

    @app.put("/api/v1/properties/{slug}/staff/room-types")
    def save_type(slug:str,body:RoomTypeSave,authorization:str|None=Header(None)):
        r=command("SELECT * FROM worthkind_flow.manage_room_type(%s,%s,%s,%s,%s,%s,%s,%s)",
                  (actor(authorization),slug,body.code,body.name,body.description,body.max_guests,body.published,body.revision))
        return {"id":str(r[0]),"revision":r[1]}

    @app.post("/api/v1/properties/{slug}/staff/rooms",status_code=201)
    def create_room(slug:str,body:RoomCreate,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.create_room(%s,%s,%s,%s)",(actor(authorization),slug,body.room_type_id,body.label))
        return {"id":str(r[0]),"operational_state":"unknown"}

    @app.get("/api/v1/properties/{slug}/staff/rooms")
    def list_rooms(slug:str,authorization:str|None=Header(None)):
        rows=command("SELECT * FROM worthkind_flow.list_internal_rooms(%s,%s)",(actor(authorization),slug),many=True)
        return {"rooms":[{"id":str(r[0]),"label":r[1],"room_type_id":str(r[2]),"operational_state":r[3],"revision":r[4]} for r in rows],"occupancy_verified":False}

    @app.put("/api/v1/properties/{slug}/staff/rooms/{room_id}/state")
    def update_room(slug:str,room_id:UUID,body:RoomState,authorization:str|None=Header(None)):
        r=command("SELECT worthkind_flow.change_room_state(%s,%s,%s,%s,%s)",(actor(authorization),slug,room_id,body.state,body.revision))
        return {"id":str(room_id),"operational_state":body.state,"revision":r[0]}

    @app.put("/api/v1/properties/{slug}/staff/display-rates")
    def rate(slug:str,body:DisplayRate,authorization:str|None=Header(None)):
        if body.end_date<=body.start_date:
            raise HTTPException(422,"Invalid rate date range")
        r=command("SELECT * FROM worthkind_flow.save_display_rate(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (actor(authorization),slug,body.room_type_id,body.code,body.currency,body.amount_minor,body.start_date,body.end_date,body.revision))
        return {"id":str(r[0]),"revision":r[1],"rates_binding":False}


class CaseControl(BaseModel):
    action:Literal["transfer","escalate","resolve"]
    target_membership_id:UUID|None=None
    reason:str=Field(min_length=8,max_length=1500)


def install_reception_controls(app):
    @app.post("/api/v1/properties/{slug}/staff/cases/{case_id}/control")
    def control(slug:str,case_id:UUID,body:CaseControl,authorization:str|None=Header(None)):
        subject=actor(authorization)
        reason=encrypt({"reason":body.reason},f"wf:case-control:{slug}:{case_id}")
        r=command("SELECT worthkind_flow.control_reception_case(%s,%s,%s,%s,%s,%s)",
                  (subject,slug,case_id,body.action,body.target_membership_id,reason))
        return {"case_id":str(case_id),"state":r[0],"notifications_live":False}
