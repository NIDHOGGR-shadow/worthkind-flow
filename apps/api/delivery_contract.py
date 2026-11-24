"""Deterministic LOCAL fake-provider contract for Worthkind Flow's SQLite outbox.

No HTTP client, SMS/email provider, background scheduler, or production sending path.
Provider 'accepted' differs from 'delivered'; only an explicit synthetic receipt
can mark delivery. Real integrations require signed receipts and safe leases.
"""
from datetime import datetime, timedelta, timezone
import os
import re

from fastapi import Header, HTTPException, Query

MAX_ATTEMPTS = 3
OUTCOMES = frozenset({"accepted", "transient_error", "permanent_error"})


def reject_production():
    if os.getenv("WF_ENV", "").strip().casefold() == "production":
        raise RuntimeError("Fake-provider delivery contract must not run in production")


def utc(now=None):
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Expected an offset-aware UTC instant")
    return current.astimezone(timezone.utc).replace(microsecond=0)


def stamp(at):
    return at.isoformat().replace("+00:00", "Z")


def create_delivery_tables(conn):
    """Add development-only state without altering the existing outbox contract."""
    reject_production()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS dev_provider_delivery_state (
            event_id TEXT PRIMARY KEY REFERENCES outbox(id),
            property_id TEXT NOT NULL REFERENCES properties(id),
            state TEXT NOT NULL CHECK(state IN ('retry_due','accepted','delivered','dead_letter')),
            attempts INTEGER NOT NULL CHECK(attempts >= 1),
            retry_after TEXT,
            ack_ref TEXT,
            last_error_code TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS dev_provider_attempts (
            event_id TEXT NOT NULL REFERENCES outbox(id),
            attempt_no INTEGER NOT NULL,
            outcome TEXT NOT NULL,
            at_utc TEXT NOT NULL,
            PRIMARY KEY(event_id, attempt_no)
        );
        CREATE TABLE IF NOT EXISTS dev_provider_receipts (
            event_id TEXT NOT NULL REFERENCES outbox(id),
            receipt_id TEXT NOT NULL,
            outcome TEXT NOT NULL CHECK(outcome IN ('delivered','undeliverable')),
            at_utc TEXT NOT NULL,
            PRIMARY KEY(event_id, receipt_id)
        );
        CREATE INDEX IF NOT EXISTS idx_dev_provider_delivery_property
            ON dev_provider_delivery_state(property_id, state);
    """)


def _event(conn, event_id):
    row = conn.execute("SELECT id,property_id,processed_at FROM outbox WHERE id=?", (event_id,)).fetchone()
    if row is None:
        raise ValueError("Outbox event does not exist")
    return row


def _state(conn, event_id):
    row = conn.execute("SELECT * FROM dev_provider_delivery_state WHERE event_id=?", (event_id,)).fetchone()
    return dict(row) if row else None


def simulate_attempt(conn, event_id, outcome, now=None):
    """Run exactly one synthetic attempt in the caller's IMMEDIATE transaction.

    The caller commits/rolls back. Retry eligibility is clock-controlled, and
    accepted events are never attempted again. No provider call occurs.
    """
    reject_production()
    if outcome not in OUTCOMES:
        raise ValueError("Unsupported fake provider outcome")
    instant = utc(now)
    event = _event(conn, event_id)
    old = _state(conn, event_id)
    if old and old["state"] in ("accepted", "delivered", "dead_letter"):
        return dict(old)  # idempotent replays; do not increment attempts
    if event["processed_at"] is not None:
        raise ValueError("Event was already consumed by another local worker")
    if old and old["retry_after"]:
        due = datetime.fromisoformat(old["retry_after"].replace("Z", "+00:00"))
        if instant < due:
            return dict(old)  # never bypass backoff
    attempts = (old["attempts"] if old else 0) + 1
    if outcome == "accepted":
        state, retry_after, error, ack = "accepted", None, None, "mock:" + event_id
    elif outcome == "permanent_error" or attempts >= MAX_ATTEMPTS:
        state, retry_after, error, ack = "dead_letter", None, (
            "MOCK_PERMANENT" if outcome == "permanent_error" else "MOCK_MAX_ATTEMPTS"
        ), None
    else:
        state, retry_after, error, ack = (
            "retry_due", stamp(instant + timedelta(seconds=min(60 * 2 ** (attempts-1), 3600))),
            "MOCK_TRANSIENT", None
        )
    conn.execute(
        "INSERT INTO dev_provider_attempts(event_id,attempt_no,outcome,at_utc) VALUES(?,?,?,?)",
        (event_id, attempts, outcome, stamp(instant)),
    )
    conn.execute(
        "INSERT INTO dev_provider_delivery_state(event_id,property_id,state,attempts,retry_after,ack_ref,last_error_code,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET "
        "state=excluded.state,attempts=excluded.attempts,retry_after=excluded.retry_after,"
        "ack_ref=excluded.ack_ref,last_error_code=excluded.last_error_code,updated_at=excluded.updated_at",
        (event_id, event["property_id"], state, attempts, retry_after, ack, error, stamp(instant)),
    )
    if state == "accepted":
        # Consumed by the *fake* provider, not proof of a message reaching anyone.
        conn.execute("UPDATE outbox SET processed_at=?,attempts=attempts+1 WHERE id=? AND processed_at IS NULL",
                     (stamp(instant), event_id))
    return _state(conn, event_id)


def simulate_receipt(conn, event_id, receipt_id, outcome, now=None):
    """Record an explicit fake receipt. Not a webhook signature verification API."""
    reject_production()
    if outcome not in ("delivered", "undeliverable"):
        raise ValueError("Unsupported synthetic receipt")
    if not isinstance(receipt_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,100}", receipt_id) is None:
        raise ValueError("Invalid synthetic receipt identifier")
    instant = utc(now)
    _event(conn, event_id)
    past = conn.execute("SELECT outcome FROM dev_provider_receipts WHERE event_id=? AND receipt_id=?",
                        (event_id, receipt_id)).fetchone()
    if past:
        if past["outcome"] != outcome:
            raise ValueError("Conflicting replay for receipt identifier")
        return _state(conn, event_id)
    state = _state(conn, event_id)
    if not state or state["state"] != "accepted":
        raise ValueError("A synthetic provider acceptance is required first")
    conn.execute("INSERT INTO dev_provider_receipts(event_id,receipt_id,outcome,at_utc) VALUES(?,?,?,?)",
                 (event_id, receipt_id, outcome, stamp(instant)))
    conn.execute("UPDATE dev_provider_delivery_state SET state=?,last_error_code=?,updated_at=? WHERE event_id=?",
                 ("delivered" if outcome == "delivered" else "dead_letter",
                  None if outcome == "delivered" else "MOCK_UNDELIVERABLE", stamp(instant), event_id))
    return _state(conn, event_id)


def install_delivery_routes(app, database, property_id, require_staff):
    @app.get("/api/properties/{slug}/staff/operations/delivery")
    def delivery_review(slug: str, limit: int = Query(40, ge=1, le=100),
                        x_staff_key: str | None = Header(None)):
        require_staff(slug, x_staff_key)
        with database() as conn:
            pid = property_id(conn, slug)
            rows = conn.execute(
                "SELECT o.id AS event_id,o.event_type,o.created_at,"
                "CASE WHEN d.state IS NOT NULL THEN d.state "
                "WHEN o.processed_at IS NOT NULL THEN 'legacy_local_consumed' "
                "ELSE 'queued' END AS state,"
                "COALESCE(d.attempts,0) AS fake_attempts,d.retry_after,d.last_error_code "
                "FROM outbox AS o LEFT JOIN dev_provider_delivery_state AS d "
                "ON d.event_id=o.id AND d.property_id=o.property_id "
                "WHERE o.property_id=? ORDER BY o.created_at DESC,o.rowid DESC LIMIT ?",
                (pid, limit),
            ).fetchall()
            counts = conn.execute(
                "SELECT CASE WHEN d.state IS NOT NULL THEN d.state "
                "WHEN o.processed_at IS NOT NULL THEN 'legacy_local_consumed' "
                "ELSE 'queued' END AS state, COUNT(*) AS n "
                "FROM outbox AS o LEFT JOIN dev_provider_delivery_state AS d "
                "ON d.event_id=o.id AND d.property_id=o.property_id "
                "WHERE o.property_id=? GROUP BY state", (pid,)
            ).fetchall()
        return {"property": slug, "source": "local_sqlite_synthetic_only",
                "real_messages_sent": 0, "real_delivery_verified": False,
                "counts": {row["state"]: row["n"] for row in counts},
                "events": [dict(row) for row in rows]}
