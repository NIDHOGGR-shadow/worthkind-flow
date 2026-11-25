"""Worthkind Flow P0 API. DEVELOPMENT REFERENCE ONLY: not a production PMS or payment integration."""
from contextlib import contextmanager
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from ticketing import create_ticket_tables, install_ticket_routes
from operations import install_operations_routes
from sla import install_sla_routes
from delivery_contract import create_delivery_tables, install_delivery_routes
from knowledge import create_knowledge_tables, install_knowledge_routes, identify_knowledge_key

from guest_postgres import (
    submit_guest_enquiry, guest_case_status, GuestStorageNotConfigured,
    GuestRecordUnavailable, GuestRequestConflict, GuestStorageError,
)
from staff_oidc import (
    verified_provider_subject, staff_case_operation, StaffTokenRejected,
    StaffAuthConfigurationError, StaffPermissionDenied, StaffStorageUnavailable,
)

from runtime_boundary import StaffConfigurationError, sqlite_ready, staff_key_matches, validate_environment

APP_ENV = validate_environment(os.getenv("WF_ENV", "development"))
app = FastAPI(title="Worthkind Flow P0", version="0.1.0", description="Human-assisted enquiry. No live booking or payment.")

@app.middleware("http")
async def protect_private_api_responses(request, call_next):
    """Sensitive enquiry/employee data must not be stored by shared HTTP caches.

    This is defense in depth for the development prototype, not a substitute
    for production staff identities, authorization, or HTTPS.
    """
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/") or path in ("/health", "/ready"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response

WEB = Path(__file__).resolve().parents[1] / "web"
if WEB.exists():
    app.mount("/static", StaticFiles(directory=str(WEB)), name="static")


@contextmanager
def database():
    conn = sqlite3.connect(os.getenv("WF_DATABASE_PATH", "./worthkind-flow-dev.sqlite3"), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize():
    with database() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS properties (
            id TEXT PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY, property_id TEXT NOT NULL,
            request_key TEXT NOT NULL, payload_hash TEXT NOT NULL,
            receipt_hash TEXT NOT NULL, kind TEXT NOT NULL,
            customer_name TEXT NOT NULL, contact TEXT NOT NULL, details TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            assigned_to TEXT, staff_reply TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(property_id, request_key),
            FOREIGN KEY(property_id) REFERENCES properties(id)
        );
        CREATE TABLE IF NOT EXISTS audit (
            id TEXT PRIMARY KEY, property_id TEXT NOT NULL, case_id TEXT NOT NULL,
            actor TEXT NOT NULL, action TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS outbox (
            id TEXT PRIMARY KEY, property_id TEXT NOT NULL, case_id TEXT NOT NULL,
            event_type TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            processed_at TEXT, attempts INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(property_id) REFERENCES properties(id),
            FOREIGN KEY(case_id) REFERENCES cases(id)
        );
        CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox(processed_at,created_at);
        CREATE TABLE IF NOT EXISTS dev_delivery_log (
            event_id TEXT PRIMARY KEY,
            property_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            simulated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(event_id) REFERENCES outbox(id)
        );
        CREATE TABLE IF NOT EXISTS public_facts (
            property_id TEXT NOT NULL,
            question_key TEXT NOT NULL,
            answer TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            approved INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL,
            PRIMARY KEY(property_id,question_key),
            FOREIGN KEY(property_id) REFERENCES properties(id)
        );
        """)
        create_ticket_tables(conn)
        create_knowledge_tables(conn)
        create_delivery_tables(conn)
        for slug, name in (("demo-hotel", "Demo Hotel (Synthetic)"), ("demo-hotel-two", "Second Demo Hotel (Synthetic)")):
            conn.execute("INSERT OR IGNORE INTO properties(id,slug,name) VALUES (?,?,?)", (slug, slug, name))
            # Synthetic fixtures only. Real hotel knowledge requires documented approval.
            facts = (
                ("name", "This is " + name + "."),
                ("booking", "Booking is enquiry-only in this development demonstration. No room has been reserved."),
                ("staff", "Use the direct human enquiry form. No live hotel staff are connected to this demonstration."),
            )
            for question_key, answer in facts:
                conn.execute(
                    "INSERT OR IGNORE INTO public_facts(property_id,question_key,answer,approved,source) "
                    "VALUES (?,?,?,?,?)",
                    (slug, question_key, answer, 1, "synthetic_demo_fixture"),
                )


def record_event(conn, property_key: str, case_id: str, actor: str, action: str) -> None:
    """Write audit and outbox events in the SAME business transaction.

    Outbox delivery is NOT implemented: pending records are not proof of notifications.
    """
    conn.execute(
        "INSERT INTO audit(id,property_id,case_id,actor,action) VALUES(?,?,?,?,?)",
        (str(uuid4()), property_key, case_id, actor, action),
    )
    conn.execute(
        "INSERT INTO outbox(id,property_id,case_id,event_type) VALUES(?,?,?,?)",
        (str(uuid4()), property_key, case_id, action),
    )


@app.on_event("startup")
def startup():
    initialize()


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/staff")
def staff_page():
    return FileResponse(WEB / "staff.html")


@app.get("/staff/tickets")
def staff_tickets_page():
    return FileResponse(WEB / "tickets.html")


@app.get("/staff/operations")
def staff_operations_page():
    return FileResponse(WEB / "operations.html")


@app.get("/staff/knowledge")
def staff_knowledge_page():
    return FileResponse(WEB / "knowledge.html")


@app.get("/health")
def health():
    return {"status": "ok", "stage": "p0-dev-only", "live_bookings": False, "live_payments": False}


@app.get("/ready", include_in_schema=False)
def ready():
    available = sqlite_ready(os.getenv("WF_DATABASE_PATH", "./worthkind-flow-dev.sqlite3"))
    return JSONResponse(status_code=200 if available else 503, content={
        "status": "ready" if available else "not_ready",
        "stage": "p0-dev-only", "production_ready": False,
    })


def property_id(conn, slug: str):
    row = conn.execute("SELECT id FROM properties WHERE slug=?", (slug,)).fetchone()
    if not row:
        raise HTTPException(404, "Property not found")
    return row["id"]


@app.get("/api/properties/{slug}")
def property_info(slug: str):
    with database() as conn:
        pid = property_id(conn, slug)
        row = conn.execute("SELECT name FROM properties WHERE id=?", (pid,)).fetchone()
        return {"slug": slug, "name": row["name"], "direct_contact": True,
                "ai_optional": True, "booking_mode": "enquiry_only",
                "live_availability": False, "live_payment": False}


class KnowledgeInput(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@app.post("/api/properties/{slug}/information")
def property_information(slug: str, data: KnowledgeInput):
    """Public, property-scoped DEMO FAQ; explicitly abstains when unsupported."""
    key = identify_knowledge_key(data.question)
    with database() as conn:
        pid = property_id(conn, slug)
        fact = conn.execute(
            "SELECT answer,version,source FROM public_facts "
            "WHERE property_id=? AND question_key=? AND approved=1",
            (pid, key),
        ).fetchone() if key else None
    if not fact:
        return {"status": "unknown", "answer": None, "next_action": "human_enquiry",
                "ai_model_invoked": False}
    return {"status": "answered", "answer": fact["answer"], "version": fact["version"],
            "source": fact["source"], "ai_model_invoked": False}


INTENTS = (
    ("urgent", (r"\bfire\b", r"\bambulance\b", r"\bunsafe\b", r"\bmedical emergency\b")),
    ("human", (r"\bhuman\b", r"\breceptionist\b", r"\bno ai\b", r"\bspeak to staff\b")),
    ("careers", (r"\bjob\b", r"\bvacanc", r"\bintern")),
    ("supplier", (r"\bsupplier\b", r"\bvendor\b", r"\bsell (to|you|hotel|equipment)\b")),
    ("food", (r"\bfood\b", r"\bmenu\b", r"\bdelivery\b", r"\brestaurant\b")),
    ("events", (r"\bwedding\b", r"\bconference\b", r"\bevent\b")),
    ("booking", (r"\bbook\b", r"\breserv\b", r"\broom\b", r"\bstay\b")),
)

def route_intent(message: str) -> str:
    for label, expressions in INTENTS:
        if any(re.search(pattern, message, flags=re.I) for pattern in expressions):
            return label
    return "information"


class RouteInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@app.post("/api/properties/{slug}/route")
def route(slug: str, body: RouteInput):
    with database() as conn:
        property_id(conn, slug)
    intent = route_intent(body.text)
    if intent in ("human", "urgent"):
        action = "human_bypass"
    elif intent == "information":
        action = "show_services_or_offer_staff"
    else:
        action = "collect_enquiry_or_use_direct_form"
    return {"intent": intent, "next_action": action, "source": "rules",
            "ai_model_invoked": False, "verified_action": False,
            "message": "This is routing only; no reservation, order or payment has been made."}


class EnquiryInput(BaseModel):
    request_key: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    kind: str = Field(pattern=r"^(booking|human|food|careers|supplier|events|support|general)$")
    name: str = Field(min_length=2, max_length=100)
    contact: str = Field(min_length=5, max_length=200)
    details: str = Field(min_length=8, max_length=3000)
    receipt_token: str | None = Field(default=None, min_length=32, max_length=128,
                                      pattern=r"^[A-Za-z0-9_-]+$")


@app.post("/api/properties/{slug}/enquiries", status_code=201)
def new_enquiry(slug: str, data: EnquiryInput):
    body = data.model_dump(exclude={"receipt_token"})
    fingerprint = sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    with database() as conn:
        # SQLite developer reference only; serialize writes to prevent create races.
        conn.execute("BEGIN IMMEDIATE")
        pid = property_id(conn, slug)
        exists = conn.execute("SELECT id,payload_hash,status FROM cases WHERE property_id=? AND request_key=?",
                              (pid, data.request_key)).fetchone()
        if exists:
            if not hmac.compare_digest(exists["payload_hash"], fingerprint):
                raise HTTPException(409, "Idempotency key already used for a different request")
            result = {"case_id": exists["id"], "status": exists["status"], "duplicate": True,
                      "message": "Prior enquiry already recorded; keep the original receipt token."}
            if data.receipt_token:
                original = conn.execute(
                    "SELECT receipt_hash FROM cases WHERE property_id=? AND id=?",
                    (pid, exists["id"]),
                ).fetchone()
                token_hash = sha256(data.receipt_token.encode()).hexdigest()
                if not original or not hmac.compare_digest(original["receipt_hash"], token_hash):
                    raise HTTPException(409, "Receipt does not match the original enquiry")
                result["receipt_token"] = data.receipt_token
            return result
        receipt = data.receipt_token or secrets.token_urlsafe(32)
        case_id = str(uuid4())
        conn.execute("INSERT INTO cases(id,property_id,request_key,payload_hash,receipt_hash,kind,customer_name,contact,details,status) VALUES(?,?,?,?,?,?,?,?,?,'queued')",
                     (case_id, pid, data.request_key, fingerprint, sha256(receipt.encode()).hexdigest(),
                      data.kind, data.name, data.contact, data.details))
        record_event(conn, pid, case_id, "guest", "case_created")
    return {"case_id": case_id, "receipt_token": receipt, "status": "queued", "duplicate": False,
            "message": "Enquiry queued for hotel staff. No booking, order, payment or job offer is confirmed."}


@app.get("/api/properties/{slug}/enquiries/{case_id}")
def read_enquiry(slug: str, case_id: str, x_receipt_token: str | None = Header(None)):
    with database() as conn:
        pid = property_id(conn, slug)
        row = conn.execute("SELECT receipt_hash,kind,status,staff_reply FROM cases WHERE property_id=? AND id=?",
                           (pid, case_id)).fetchone()
        if not row or not x_receipt_token or not hmac.compare_digest(row["receipt_hash"], sha256(x_receipt_token.encode()).hexdigest()):
            raise HTTPException(404, "Enquiry not found")
        return {"case_id": case_id, "kind": row["kind"], "status": row["status"], "staff_reply": row["staff_reply"]}


def require_staff(slug: str, staff_key: str | None):
    try:
        authorized = staff_key_matches(os.getenv("WF_DEV_STAFF_KEYS_JSON", "{}"), slug, staff_key)
    except StaffConfigurationError:
        raise HTTPException(503, "Staff keys misconfigured") from None
    if not authorized:
        raise HTTPException(401, "Staff authentication required")
    # DEVELOPMENT ONLY: use real staff login and per-role permissions before production.
    return "dev-staff:" + slug


@app.get("/api/properties/{slug}/staff/enquiries")
def staff_enquiries(slug: str, x_staff_key: str | None = Header(None)):
    actor = require_staff(slug, x_staff_key)
    with database() as conn:
        pid = property_id(conn, slug)
        rows = conn.execute(
            "SELECT c.id,c.kind,c.customer_name,c.details,c.status,c.assigned_to,c.staff_reply,"
            "t.id AS linked_ticket_id,t.status AS linked_ticket_status "
            "FROM cases AS c LEFT JOIN service_tickets AS t "
            "ON t.property_id=c.property_id AND t.origin_case_id=c.id "
            "WHERE c.property_id=? ORDER BY c.created_at DESC,c.rowid DESC",
            (pid,),
        ).fetchall()
        return {"actor": actor, "cases": [dict(r) for r in rows]}


@app.post("/api/properties/{slug}/staff/enquiries/{case_id}/claim")
def claim_case(slug: str, case_id: str, x_staff_key: str | None = Header(None)):
    actor = require_staff(slug, x_staff_key)
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        pid = property_id(conn, slug)
        changed = conn.execute("UPDATE cases SET assigned_to=?,status='claimed',updated_at=CURRENT_TIMESTAMP WHERE id=? AND property_id=? AND status='queued'",
                               (actor, case_id, pid))
        if changed.rowcount != 1:
            raise HTTPException(409, "Case not queued or already claimed")
        record_event(conn, pid, case_id, actor, "case_claimed")
    return {"case_id": case_id, "status": "claimed"}


class StaffResponse(BaseModel):
    message: str = Field(min_length=2, max_length=3000)


@app.post("/api/properties/{slug}/staff/enquiries/{case_id}/respond")
def respond_case(slug: str, case_id: str, body: StaffResponse, x_staff_key: str | None = Header(None)):
    actor = require_staff(slug, x_staff_key)
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        pid = property_id(conn, slug)
        changed = conn.execute("UPDATE cases SET status='responded',staff_reply=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND property_id=? AND assigned_to=? AND status='claimed'",
                               (body.message, case_id, pid, actor))
        if changed.rowcount != 1:
            raise HTTPException(409, "Claim case first or it was already answered")
        record_event(conn, pid, case_id, actor, "case_responded")
    return {"case_id": case_id, "status": "responded"}


@app.get("/api/properties/{slug}/booking-capabilities")
def booking_capabilities(slug: str):
    with database() as conn:
        property_id(conn, slug)
    return {"mode": "enquiry_only", "availability": False, "holds": False,
            "payments": False, "confirmed_reservations": False,
            "reason": "No authorized hotel PMS or payment adapter is connected."}


# Local-only staff/department operations extend the existing SQLite case lifecycle.
# They do not call hotel, email, payment, AI or messaging providers.
install_ticket_routes(app, database, property_id, require_staff)
install_operations_routes(app, database, property_id, require_staff)
install_sla_routes(app, database, property_id, require_staff)
install_delivery_routes(app, database, property_id, require_staff)
install_knowledge_routes(app, database, property_id, require_staff)


def _verified_staff_subject(authorization: str | None) -> str:
    try:
        return verified_provider_subject(authorization)
    except StaffTokenRejected as error:
        raise HTTPException(401, str(error), headers={"WWW-Authenticate": "Bearer"}) from error
    except StaffAuthConfigurationError as error:
        raise HTTPException(503, "Staff sign-in not configured") from error


def _staff_db_action(subject: str, slug: str, *, action: str, case_id: UUID | None = None, reply_message: str | None = None):
    try:
        return staff_case_operation(subject, slug, action=action, case_id=case_id, reply_message=reply_message)
    except StaffAuthConfigurationError as error:
        raise HTTPException(503, "Hotel staff database not configured") from error
    except StaffPermissionDenied as error:
        raise HTTPException(403, "Staff action unavailable") from error
    except StaffStorageUnavailable as error:
        raise HTTPException(503, "Hotel staff data temporarily unavailable") from error
    except (GuestStorageNotConfigured, GuestStorageError) as error:
        raise HTTPException(503, "Hotel guest encryption service unavailable") from error


@app.get("/api/v1/properties/{slug}/staff/cases")
def verified_staff_cases_v1(slug: str, authorization: str | None = Header(None)):
    """Trusted OIDC + PostgreSQL RLS; authorized hotel staff can access encrypted guest details."""
    subject = _verified_staff_subject(authorization)
    return _staff_db_action(subject, slug, action="case:read")


@app.post("/api/v1/properties/{slug}/staff/cases/{case_id}/claim")
def verified_staff_claim_v1(
    slug: str, case_id: UUID, authorization: str | None = Header(None)
):
    """Atomic staff claim. Queued audit/outbox is not delivered notification."""
    subject = _verified_staff_subject(authorization)
    return _staff_db_action(subject, slug, action="case:claim", case_id=case_id)


class PostgreSQLGuestEnquiry(EnquiryInput):
    # A client-generated secret preserves private status proof across lost responses.
    receipt_token: str = Field(
        min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    )


@app.post("/api/v1/properties/{slug}/enquiries", status_code=201)
def postgres_guest_enquiry_v1(slug: str, data: PostgreSQLGuestEnquiry):
    """Development-only encrypted guest request; never a booked hotel room."""
    try:
        return submit_guest_enquiry(slug, data.model_dump())
    except GuestStorageNotConfigured as error:
        raise HTTPException(503, "Guest enquiry storage not configured") from error
    except GuestRequestConflict as error:
        raise HTTPException(409, str(error)) from error
    except GuestRecordUnavailable as error:
        raise HTTPException(404, "Hotel unavailable") from error
    except GuestStorageError as error:
        raise HTTPException(503, "Guest enquiry unavailable") from error


@app.get("/api/v1/properties/{slug}/enquiries/{case_id}")
def postgres_guest_status_v1(
    slug: str, case_id: UUID, x_receipt_token: str | None = Header(None)
):
    if not x_receipt_token or not 32 <= len(x_receipt_token) <= 128 or not re.fullmatch(
        r"[A-Za-z0-9_-]+", x_receipt_token
    ):
        raise HTTPException(404, "Case not found")
    try:
        return guest_case_status(slug, case_id, x_receipt_token)
    except GuestStorageNotConfigured as error:
        raise HTTPException(503, "Guest enquiry storage not configured") from error
    except GuestRecordUnavailable as error:
        raise HTTPException(404, "Case not found") from error
    except GuestStorageError as error:
        raise HTTPException(503, "Guest status temporarily unavailable") from error


@app.post("/api/v1/properties/{slug}/staff/cases/{case_id}/respond")
def postgres_staff_reply_v1(
    slug: str, case_id: UUID, body: StaffResponse,
    authorization: str | None = Header(None),
):
    subject = _verified_staff_subject(authorization)
    return _staff_db_action(
        subject, slug, action="case:reply",
        case_id=case_id, reply_message=body.message,
    )
