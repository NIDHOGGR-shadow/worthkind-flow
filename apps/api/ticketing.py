"""Worthkind Flow non-AI staff/IT ticketing service.

A strictly development-only reference. Uses existing property-scoped dev staff
credential; NO production RBAC, staff directory, notifications or PMS integration.
Every ticket state change and local outbox event is committed atomically.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
from uuid import uuid4
from typing import Literal

from fastapi import Header, HTTPException, Query
from pydantic import BaseModel, Field


Category = Literal["it", "reception", "housekeeping", "maintenance", "kitchen", "billing", "general"]
Priority = Literal["low", "normal", "high", "urgent"]
Status = Literal["open", "assigned", "in_progress", "resolved", "reopened"]
SLA_HOURS = {"urgent": 1, "high": 4, "normal": 24, "low": 72}


def utc_now():
    return datetime.now(timezone.utc)


def create_ticket_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS service_tickets (
        id TEXT PRIMARY KEY,
        property_id TEXT NOT NULL,
        request_key TEXT NOT NULL,
        payload_hash TEXT NOT NULL,
        origin_case_id TEXT,
        category TEXT NOT NULL,
        priority TEXT NOT NULL,
        subject TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','assigned','in_progress','resolved','reopened')),
        assigned_to TEXT,
        resolution TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        due_at TEXT NOT NULL,
        UNIQUE(property_id, request_key),
        UNIQUE(property_id, origin_case_id),
        FOREIGN KEY(property_id) REFERENCES properties(id),
        FOREIGN KEY(origin_case_id) REFERENCES cases(id)
    );
    CREATE INDEX IF NOT EXISTS idx_tickets_property_state ON service_tickets(property_id,status,due_at);
    CREATE TABLE IF NOT EXISTS ticket_history (
        id TEXT PRIMARY KEY,
        property_id TEXT NOT NULL,
        ticket_id TEXT NOT NULL,
        actor TEXT NOT NULL,
        event TEXT NOT NULL,
        details TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(property_id) REFERENCES properties(id),
        FOREIGN KEY(ticket_id) REFERENCES service_tickets(id)
    );
    CREATE INDEX IF NOT EXISTS idx_ticket_history ON ticket_history(property_id,ticket_id,created_at);
    CREATE TABLE IF NOT EXISTS ticket_outbox (
        id TEXT PRIMARY KEY,
        property_id TEXT NOT NULL,
        ticket_id TEXT NOT NULL,
        event TEXT NOT NULL,
        created_at TEXT NOT NULL,
        processed_at TEXT,
        FOREIGN KEY(property_id) REFERENCES properties(id),
        FOREIGN KEY(ticket_id) REFERENCES service_tickets(id)
    );
    CREATE INDEX IF NOT EXISTS idx_ticket_outbox_pending ON ticket_outbox(processed_at,created_at);
    """)


def record_ticket_change(conn, property_key: str, ticket_id: str, actor: str, event: str, details: str | None = None):
    """History and pending event are in the SAME SQLite transaction as domain write.

    There is NO outbound sender; an outbox event is not a delivered notification.
    """
    stamp = utc_now().isoformat()
    conn.execute(
        "INSERT INTO ticket_history(id,property_id,ticket_id,actor,event,details,created_at) VALUES(?,?,?,?,?,?,?)",
        (str(uuid4()), property_key, ticket_id, actor, event, details, stamp),
    )
    conn.execute(
        "INSERT INTO ticket_outbox(id,property_id,ticket_id,event,created_at) VALUES(?,?,?,?,?)",
        (str(uuid4()), property_key, ticket_id, event, stamp),
    )


class NewTicket(BaseModel):
    request_key: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    category: Category
    priority: Priority = "normal"
    subject: str = Field(min_length=4, max_length=160)
    description: str = Field(min_length=8, max_length=3000)
    origin_case_id: str | None = Field(default=None, min_length=1, max_length=100)


class Resolution(BaseModel):
    summary: str = Field(min_length=8, max_length=1500)


class Note(BaseModel):
    text: str = Field(min_length=4, max_length=1200)


def present_ticket(row, *, now=None):
    data = dict(row)
    data["overdue"] = data["status"] != "resolved" and datetime.fromisoformat(data["due_at"]) < (now or utc_now())
    return data


def install_ticket_routes(app, database, property_id, require_staff):
    """Install staff-only routes in main.py after shared auth/database helpers exist."""

    def staff_auth(slug, staff_key):
        return require_staff(slug, staff_key)

    def scoped_ticket(conn, pid, ticket_id):
        row = conn.execute(
            "SELECT * FROM service_tickets WHERE property_id=? AND id=?",
            (pid, ticket_id),
        ).fetchone()
        if row is None:
            # Uniform 404 for an unknown id and an id from another property.
            raise HTTPException(404, "Ticket not found")
        return row

    @app.get("/api/properties/{slug}/staff/tickets/metrics")
    def ticket_metrics(slug: str, x_staff_key: str | None = Header(None)):
        staff_auth(slug, x_staff_key)
        with database() as conn:
            pid = property_id(conn, slug)
            records = conn.execute(
                "SELECT status, priority, due_at FROM service_tickets WHERE property_id=?",
                (pid,),
            ).fetchall()
        now = utc_now()
        states = {s: 0 for s in ("open", "assigned", "in_progress", "resolved", "reopened")}
        for rec in records:
            states[rec["status"]] += 1
        return {
            "total": len(records),
            "by_status": states,
            "unresolved": sum(v for k,v in states.items() if k != "resolved"),
            "overdue": sum(1 for rec in records if rec["status"] != "resolved" and datetime.fromisoformat(rec["due_at"]) < now),
            "notifications_live": False,
            "source": "property_scoped_local_development_database",
        }

    @app.get("/api/properties/{slug}/staff/tickets")
    def list_tickets(
        slug: str,
        status: Status | None = None,
        category: Category | None = None,
        limit: int = Query(default=100, ge=1, le=100),
        x_staff_key: str | None = Header(None),
    ):
        staff_auth(slug, x_staff_key)
        with database() as conn:
            pid = property_id(conn, slug)
            query = "SELECT * FROM service_tickets WHERE property_id=?"
            args: list = [pid]
            if status is not None:
                query += " AND status=?"
                args.append(status)
            if category is not None:
                query += " AND category=?"
                args.append(category)
            query += " ORDER BY CASE WHEN status='resolved' THEN 1 ELSE 0 END, due_at ASC, created_at DESC LIMIT ?"
            args.append(limit)
            rows = conn.execute(query, args).fetchall()
        return {"tickets": [present_ticket(r) for r in rows], "notifications_live": False}

    @app.post("/api/properties/{slug}/staff/tickets", status_code=201)
    def create_ticket(slug: str, body: NewTicket, x_staff_key: str | None = Header(None)):
        actor = staff_auth(slug, x_staff_key)
        serialized = body.model_dump(exclude={"request_key"})
        fingerprint = sha256(json.dumps(serialized, sort_keys=True).encode()).hexdigest()
        with database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pid = property_id(conn, slug)
            existing = conn.execute(
                "SELECT id,status,payload_hash FROM service_tickets WHERE property_id=? AND request_key=?",
                (pid, body.request_key),
            ).fetchone()
            if existing:
                if not hmac.compare_digest(existing["payload_hash"], fingerprint):
                    raise HTTPException(409, "Ticket idempotency key reused with different details")
                return {"ticket_id": existing["id"], "status": existing["status"], "duplicate": True}
            if body.origin_case_id:
                case = conn.execute(
                    "SELECT status FROM cases WHERE property_id=? AND id=?",
                    (pid, body.origin_case_id),
                ).fetchone()
                if not case:
                    raise HTTPException(404, "Source enquiry not found")
                # Require an acknowledged staff case before creating linked work.
                if case["status"] not in ("claimed", "responded"):
                    raise HTTPException(409, "Reception must claim the source enquiry first")
                linked = conn.execute(
                    "SELECT id FROM service_tickets WHERE property_id=? AND origin_case_id=?",
                    (pid, body.origin_case_id),
                ).fetchone()
                if linked:
                    raise HTTPException(409, "A service ticket already exists for this enquiry")
            now = utc_now()
            tid = str(uuid4())
            conn.execute(
                "INSERT INTO service_tickets "
                "(id,property_id,request_key,payload_hash,origin_case_id,category,priority,subject,"
                "description,status,created_at,updated_at,due_at) VALUES(?,?,?,?,?,?,?,?,?,'open',?,?,?)",
                (tid,pid,body.request_key,fingerprint,body.origin_case_id,body.category,body.priority,
                 body.subject,body.description,now.isoformat(),now.isoformat(),
                 (now+timedelta(hours=SLA_HOURS[body.priority])).isoformat()),
            )
            record_ticket_change(conn,pid,tid,actor,"ticket_created")
        return {"ticket_id":tid,"status":"open","duplicate":False,
                "message":"Internal staff ticket recorded; not yet assigned or completed."}

    @app.get("/api/properties/{slug}/staff/tickets/{ticket_id}")
    def ticket_detail(slug: str, ticket_id: str, x_staff_key: str | None = Header(None)):
        staff_auth(slug, x_staff_key)
        with database() as conn:
            pid = property_id(conn, slug)
            row = scoped_ticket(conn,pid,ticket_id)
            history = conn.execute(
                "SELECT actor,event,details,created_at FROM ticket_history "
                "WHERE property_id=? AND ticket_id=? ORDER BY created_at,id",
                (pid,ticket_id),
            ).fetchall()
        return {"ticket":present_ticket(row),"history":[dict(h) for h in history]}

    def transition(slug,ticket_id,staff_key,from_states,to_state,event,*,resolution=None,assigned=None,description=None):
        actor = staff_auth(slug,staff_key)
        with database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pid = property_id(conn,slug)
            existing = scoped_ticket(conn,pid,ticket_id)
            if existing["status"] not in from_states:
                raise HTTPException(409,"Invalid ticket transition from "+existing["status"])
            if to_state in ("in_progress","resolved") and existing["assigned_to"] != actor:
                raise HTTPException(403,"Only the assigned staff member may perform this step")
            conn.execute(
                "UPDATE service_tickets SET status=?,updated_at=?,assigned_to=?,resolution=? "
                "WHERE property_id=? AND id=?",
                (to_state,utc_now().isoformat(),assigned if assigned is not None else existing["assigned_to"],
                 resolution if resolution is not None else existing["resolution"],pid,ticket_id),
            )
            record_ticket_change(conn,pid,ticket_id,actor,event,description)
        return {"ticket_id":ticket_id,"status":to_state,"notifications_live":False}

    @app.post("/api/properties/{slug}/staff/tickets/{ticket_id}/claim")
    def claim_ticket(slug: str, ticket_id: str, x_staff_key: str | None = Header(None)):
        actor=staff_auth(slug,x_staff_key)
        return transition(slug,ticket_id,x_staff_key,("open","reopened"),"assigned","ticket_claimed",assigned=actor)

    @app.post("/api/properties/{slug}/staff/tickets/{ticket_id}/start")
    def start_ticket(slug: str, ticket_id: str, x_staff_key: str | None = Header(None)):
        return transition(slug,ticket_id,x_staff_key,("assigned",),"in_progress","ticket_started")

    @app.post("/api/properties/{slug}/staff/tickets/{ticket_id}/resolve")
    def resolve_ticket(slug: str, ticket_id: str, body: Resolution, x_staff_key: str | None = Header(None)):
        return transition(slug,ticket_id,x_staff_key,("in_progress",),"resolved",
                          "ticket_resolved",resolution=body.summary,description=body.summary)

    @app.post("/api/properties/{slug}/staff/tickets/{ticket_id}/reopen")
    def reopen_ticket(slug: str, ticket_id: str, body: Note, x_staff_key: str | None = Header(None)):
        actor=staff_auth(slug,x_staff_key)
        with database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pid=property_id(conn,slug)
            existing=scoped_ticket(conn,pid,ticket_id)
            if existing["status"] != "resolved":
                raise HTTPException(409,"Only resolved tickets can be reopened")
            conn.execute(
                "UPDATE service_tickets SET status='reopened',assigned_to=NULL,resolution=NULL,"
                "updated_at=? WHERE property_id=? AND id=?",
                (utc_now().isoformat(),pid,ticket_id),
            )
            record_ticket_change(conn,pid,ticket_id,actor,"ticket_reopened",body.text)
        return {"ticket_id":ticket_id,"status":"reopened","notifications_live":False}

    @app.post("/api/properties/{slug}/staff/tickets/{ticket_id}/notes",status_code=201)
    def add_ticket_note(slug: str, ticket_id: str, body: Note, x_staff_key: str | None = Header(None)):
        actor=staff_auth(slug,x_staff_key)
        with database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pid=property_id(conn,slug)
            scoped_ticket(conn,pid,ticket_id)
            record_ticket_change(conn,pid,ticket_id,actor,"ticket_note",body.text)
            conn.execute(
                "UPDATE service_tickets SET updated_at=? WHERE property_id=? AND id=?",
                (utc_now().isoformat(),pid,ticket_id),
            )
        return {"ticket_id":ticket_id,"note_recorded":True,"notifications_live":False}
