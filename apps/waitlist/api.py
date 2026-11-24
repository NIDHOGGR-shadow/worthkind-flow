"""Worthkind Flow private waitlist development preview.

Not production ready: no email verification, authorized operator verification,
distributed anti-abuse, external CRM, secrets infrastructure or deletion pipeline.
Do not run with live hotel personal data or deploy publicly.
"""
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Literal
import json
import os
import re
import secrets
import sqlite3
import time
import unicodedata
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator


if os.environ.get("WF_WAITLIST_ENV") != "development":
    raise RuntimeError("Waitlist preview blocks production deployment until security and privacy reviews.")

ROOT = Path(__file__).resolve().parent
DB_FALLBACK = "./worthkind-flow-waitlist-dev.sqlite3"
CONSENT_NOTICE = "wf-waitlist-2026-11-17-v1"
RATE_LIMIT_PER_HOUR = 12


@contextmanager
def db():
    con = sqlite3.connect(os.environ.get("WF_WAITLIST_DB", DB_FALLBACK), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=10000")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS applications (
          id TEXT PRIMARY KEY,
          hotel_key TEXT NOT NULL,
          hotel_name TEXT NOT NULL,
          hotel_address TEXT,
          area TEXT NOT NULL,
          rooms_reported INTEGER,
          representative TEXT NOT NULL,
          representative_role TEXT NOT NULL,
          email TEXT NOT NULL,
          workflow_challenge TEXT NOT NULL,
          update_opt_in INTEGER NOT NULL CHECK(update_opt_in IN(0,1)),
          marketing_opt_in INTEGER NOT NULL CHECK(marketing_opt_in IN(0,1)),
          notice_version TEXT NOT NULL,
          consent_at TEXT NOT NULL,
          withdraw_proof_hash TEXT NOT NULL UNIQUE,
          status TEXT NOT NULL CHECK(status IN ('pending_verification','withdrawn')),
          created_at TEXT NOT NULL,
          UNIQUE(hotel_key, email)
        );
        CREATE TABLE IF NOT EXISTS consent_events (
          id TEXT PRIMARY KEY,
          application_id TEXT NOT NULL,
          action TEXT NOT NULL,
          notice_version TEXT NOT NULL,
          occurred_at TEXT NOT NULL,
          FOREIGN KEY(application_id) REFERENCES applications(id)
        );
        CREATE TABLE IF NOT EXISTS rate_buckets (
          actor_hash TEXT NOT NULL,
          hour_bucket INTEGER NOT NULL,
          attempts INTEGER NOT NULL,
          PRIMARY KEY(actor_hash,hour_bucket)
        );
        """)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init()
    yield


app = FastAPI(title="Worthkind Flow Early Access — Preview Only", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/assets", StaticFiles(directory=str(ROOT / "web")), name="assets")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    result = await call_next(request)
    result.headers["Cache-Control"] = "no-store"
    result.headers["X-Content-Type-Options"] = "nosniff"
    result.headers["Referrer-Policy"] = "no-referrer"
    result.headers["X-Frame-Options"] = "DENY"
    result.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    return result


@app.get("/")
def landing():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/privacy")
def privacy():
    return FileResponse(ROOT / "web" / "privacy.html")


@app.get("/health")
def health():
    return {"status": "preview", "signup_live": False, "pilot_partners": 0}


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKC", value).lower()).strip("-")


class LeadIn(BaseModel):
    hotel_name: str = Field(min_length=3, max_length=150)
    hotel_address: str | None = Field(default=None, max_length=220)
    area: str = Field(min_length=3, max_length=100)
    rooms_reported: int | None = Field(default=None, ge=1, le=2000)
    representative: str = Field(min_length=3, max_length=120)
    representative_role: Literal["owner", "general_manager", "operations", "reservations", "other"]
    email: str = Field(min_length=6, max_length=200)
    workflow_challenge: Literal["lost_enquiries", "slow_handoff", "manual_followup", "booking_workflow", "exploring", "other"]
    consent_early_access: Literal[True]
    consent_marketing: bool = False

    @field_validator("hotel_name", "area", "representative", "hotel_address")
    @classmethod
    def normalize_whitespace(cls, value):
        return re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def safe_email(cls, value):
        v = value.strip().lower()
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_\`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", v):
            raise ValueError("Enter a valid business contact email")
        return v


class WithdrawIn(BaseModel):
    token: str = Field(min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def throttle(con: sqlite3.Connection, request: Request):
    client_host = request.client.host if request.client else "unknown"
    # Hash the actor in the development database instead of retaining raw IP.
    # Never trust X-Forwarded-For in the preview.
    key = sha256(("preview-only-v1:" + client_host).encode()).hexdigest()
    bucket = int(time.time()) // 3600
    row = con.execute("SELECT attempts FROM rate_buckets WHERE actor_hash=? AND hour_bucket=?", (key, bucket)).fetchone()
    if row and row["attempts"] >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(429, "Too many attempts; please try again later.")
    con.execute(
        "INSERT INTO rate_buckets(actor_hash,hour_bucket,attempts) VALUES(?,?,1) "
        "ON CONFLICT(actor_hash,hour_bucket) DO UPDATE SET attempts=attempts+1",
        (key, bucket),
    )


@app.post("/api/early-access", status_code=201)
def early_access(lead: LeadIn, request: Request):
    hotel_key = norm(lead.hotel_name) + "|" + norm(lead.area)
    if len(hotel_key) < 9:
        raise HTTPException(422, "Specify hotel name and area")
    token = secrets.token_urlsafe(32)
    ident = str(uuid4())
    now = utc_now()
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        throttle(con, request)
        exists = con.execute(
            "SELECT id FROM applications WHERE hotel_key=? AND email=?",
            (hotel_key, lead.email),
        ).fetchone()
        if exists:
            raise HTTPException(409, "This hotel and contact are already registered for review.")
        con.execute(
            "INSERT INTO applications"
            "(id,hotel_key,hotel_name,hotel_address,area,rooms_reported,representative,representative_role,"
            "email,workflow_challenge,update_opt_in,marketing_opt_in,notice_version,consent_at,"
            "withdraw_proof_hash,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ident, hotel_key, lead.hotel_name, lead.hotel_address, lead.area, lead.rooms_reported,
             lead.representative, lead.representative_role, lead.email, lead.workflow_challenge,
             1, int(lead.consent_marketing), CONSENT_NOTICE, now,
             sha256(token.encode()).hexdigest(), "pending_verification", now),
        )
        con.execute(
            "INSERT INTO consent_events(id,application_id,action,notice_version,occurred_at) VALUES(?,?,?,?,?)",
            (str(uuid4()), ident, "explicit_early_access_opt_in", CONSENT_NOTICE, now),
        )
    return {"reference": ident, "status": "pending_verification",
            "qualified_waitlist": False,
            "withdraw_token": token,
            "message": "Your request has been recorded for review. This does not reserve or confirm a pilot."}


@app.post("/api/early-access/withdraw", status_code=202)
def withdraw(data: WithdrawIn):
    token_hash = sha256(data.token.encode()).hexdigest()
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT id,status FROM applications WHERE withdraw_proof_hash=?", (token_hash,)).fetchone()
        if row and row["status"] != "withdrawn":
            con.execute("UPDATE applications SET status='withdrawn',update_opt_in=0,marketing_opt_in=0 WHERE id=?", (row["id"],))
            con.execute(
                "INSERT INTO consent_events(id,application_id,action,notice_version,occurred_at) VALUES(?,?,?,?,?)",
                (str(uuid4()), row["id"], "withdrawn", CONSENT_NOTICE, utc_now()),
            )
    # Non-enumerating result; client cannot learn whether the token existed.
    return {"message": "If the token matched, the early-access request was withdrawn.",
            "qualified_waitlist": False}
