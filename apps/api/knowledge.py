"""Property-scoped approved hotel knowledge in local SQLite (development only).

Draft -> review -> publish/withdraw changes to the existing approved public_facts
table. No AI model, external hotel system, email, or API provider is invoked.

IMPORTANT: A hotel-scoped development key is NOT a real individual approver.
Production must use verified identities, role gates, approval policy, retention,
and signed hotel content authority before real facts are published.
"""
from hashlib import sha256
import hmac
import json
import re
from typing import Literal
from uuid import uuid4

from fastapi import Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

KnowledgeKey = Literal[
    "name", "booking", "staff", "dining", "events", "parking", "checkin",
    "checkout", "amenities", "accessibility", "cancellation"
]
ALLOWED_KEYS = (
    "name", "booking", "staff", "dining", "events", "parking", "checkin",
    "checkout", "amenities", "accessibility", "cancellation"
)
MATCHERS = (
    ("name", r"\b(name|called)\b"),
    ("cancellation", r"\b(cancel|cancellation|refund)\b"),
    ("checkin", r"\b(check[ -]?in|arrival time)\b"),
    ("checkout", r"\b(check[ -]?out|departure time)\b"),
    ("parking", r"\b(parking|car park|vehicle parking)\b"),
    ("dining", r"\b(dining|restaurant|menu|food)\b"),
    ("events", r"\b(event|wedding|conference|meeting venue)\b"),
    ("amenities", r"\b(wifi|wi-fi|pool|gym|amenit|facilities)\b"),
    ("accessibility", r"\b(accessib|wheelchair|step-free)\b"),
    ("booking", r"\b(book|reserv|room|price|pay|availab)"),
    ("staff", r"\b(human|staff|reception|contact|help)\b"),
)


def identify_knowledge_key(question: str) -> str | None:
    """Deterministic topic routing. No inference of unsupported hotel facts."""
    for key, expression in MATCHERS:
        if re.search(expression, question, flags=re.I):
            return key
    return None


def create_knowledge_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS knowledge_drafts (
      id TEXT PRIMARY KEY,
      property_id TEXT NOT NULL,
      request_key TEXT NOT NULL,
      payload_hash TEXT NOT NULL,
      question_key TEXT NOT NULL,
      answer TEXT NOT NULL,
      source_reference TEXT NOT NULL,
      base_version INTEGER NOT NULL CHECK(base_version>=0),
      status TEXT NOT NULL DEFAULT 'draft'
        CHECK(status IN ('draft','approved','rejected')),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      decided_at TEXT,
      UNIQUE(property_id,request_key),
      FOREIGN KEY(property_id) REFERENCES properties(id)
    );
    CREATE INDEX IF NOT EXISTS idx_knowledge_drafts_property
      ON knowledge_drafts(property_id,status,created_at);
    CREATE TABLE IF NOT EXISTS knowledge_revisions (
      id TEXT PRIMARY KEY,
      property_id TEXT NOT NULL,
      question_key TEXT NOT NULL,
      version INTEGER NOT NULL CHECK(version>=1),
      answer TEXT NOT NULL,
      source TEXT NOT NULL,
      approved INTEGER NOT NULL CHECK(approved IN (0,1)),
      actor TEXT NOT NULL,
      reason TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(property_id,question_key,version),
      FOREIGN KEY(property_id) REFERENCES properties(id)
    );
    CREATE TABLE IF NOT EXISTS knowledge_audit (
      id TEXT PRIMARY KEY,
      property_id TEXT NOT NULL,
      draft_id TEXT,
      question_key TEXT NOT NULL,
      actor TEXT NOT NULL,
      action TEXT NOT NULL,
      details TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(property_id) REFERENCES properties(id)
    );
    CREATE INDEX IF NOT EXISTS idx_knowledge_history
      ON knowledge_revisions(property_id,question_key,version);
    """)


class NewDraft(BaseModel):
    request_key: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    question_key: KnowledgeKey
    answer: str = Field(min_length=8, max_length=2000)
    source_reference: str = Field(min_length=8, max_length=240)

    @field_validator("answer", "source_reference")
    @classmethod
    def meaningful_content(cls, value: str) -> str:
        if len(value.strip()) < 8:
            raise ValueError("Knowledge content needs at least eight non-space characters")
        return value.strip()


class ReviewReason(BaseModel):
    reason: str = Field(min_length=8, max_length=500)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value: str) -> str:
        if len(value.strip()) < 8:
            raise ValueError("Review rationale needs at least eight non-space characters")
        return value.strip()


def _audit(conn, pid, actor, action, key, draft_id=None, details=None):
    conn.execute(
        "INSERT INTO knowledge_audit(id,property_id,draft_id,question_key,actor,action,details) "
        "VALUES(?,?,?,?,?,?,?)",
        (str(uuid4()), pid, draft_id, key, actor, action, details),
    )


def _fact_version(conn, pid, key):
    row = conn.execute(
        "SELECT version FROM public_facts WHERE property_id=? AND question_key=?",
        (pid, key),
    ).fetchone()
    return row["version"] if row else 0


def install_knowledge_routes(app, database, property_id, require_staff):
    @app.get("/api/properties/{slug}/staff/knowledge")
    def knowledge_list(slug: str, x_staff_key: str | None = Header(None)):
        require_staff(slug, x_staff_key)
        with database() as conn:
            pid = property_id(conn, slug)
            facts = conn.execute(
                "SELECT question_key,answer,version,approved,source FROM public_facts "
                "WHERE property_id=? ORDER BY question_key",
                (pid,),
            ).fetchall()
            drafts = conn.execute(
                "SELECT id,question_key,answer,source_reference,base_version,status,created_at "
                "FROM knowledge_drafts WHERE property_id=? ORDER BY created_at DESC,id DESC LIMIT 100",
                (pid,),
            ).fetchall()
        return {
            "property": slug,
            "source": "local_sqlite_development",
            "facts": [dict(row) for row in facts],
            "drafts": [dict(row) for row in drafts],
            "production_approval": False,
        }

    @app.post("/api/properties/{slug}/staff/knowledge/drafts", status_code=201)
    def draft_knowledge(slug: str, body: NewDraft, x_staff_key: str | None = Header(None)):
        actor = require_staff(slug, x_staff_key)
        payload = body.model_dump(exclude={"request_key"})
        fingerprint = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pid = property_id(conn, slug)
            previous = conn.execute(
                "SELECT id,payload_hash,status,base_version FROM knowledge_drafts "
                "WHERE property_id=? AND request_key=?",
                (pid, body.request_key),
            ).fetchone()
            if previous:
                if not hmac.compare_digest(previous["payload_hash"], fingerprint):
                    raise HTTPException(409, "Draft request key used with different content")
                return {
                    "draft_id": previous["id"],
                    "status": previous["status"],
                    "base_version": previous["base_version"],
                    "duplicate": True,
                }
            version = _fact_version(conn, pid, body.question_key)
            draft_id = str(uuid4())
            conn.execute(
                "INSERT INTO knowledge_drafts "
                "(id,property_id,request_key,payload_hash,question_key,answer,source_reference,base_version) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (draft_id, pid, body.request_key, fingerprint, body.question_key,
                 body.answer.strip(), body.source_reference.strip(), version),
            )
            _audit(conn, pid, actor, "knowledge_drafted", body.question_key, draft_id)
        return {"draft_id": draft_id, "status": "draft", "base_version": version,
                "duplicate": False, "published": False}

    @app.post("/api/properties/{slug}/staff/knowledge/drafts/{draft_id}/approve")
    def approve_knowledge(slug: str, draft_id: str, x_staff_key: str | None = Header(None)):
        actor = require_staff(slug, x_staff_key)
        with database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pid = property_id(conn, slug)
            draft = conn.execute(
                "SELECT question_key,answer,source_reference,base_version,status "
                "FROM knowledge_drafts WHERE property_id=? AND id=?",
                (pid, draft_id),
            ).fetchone()
            if not draft:
                raise HTTPException(404, "Knowledge draft not found")
            if draft["status"] != "draft":
                raise HTTPException(409, "Knowledge draft is no longer pending")
            version = _fact_version(conn, pid, draft["question_key"])
            if version != draft["base_version"]:
                raise HTTPException(409, "Knowledge was changed after this draft. Recheck and redraft.")
            new_version = version + 1
            provenance = "local_development_review:" + draft["source_reference"]
            conn.execute(
                "INSERT INTO public_facts(property_id,question_key,answer,version,approved,source) "
                "VALUES(?,?,?,?,1,?) ON CONFLICT(property_id,question_key) "
                "DO UPDATE SET answer=excluded.answer,version=excluded.version,"
                "approved=1,source=excluded.source",
                (pid, draft["question_key"], draft["answer"], new_version, provenance),
            )
            conn.execute(
                "UPDATE knowledge_drafts SET status='approved',decided_at=CURRENT_TIMESTAMP "
                "WHERE property_id=? AND id=?",
                (pid, draft_id),
            )
            conn.execute(
                "INSERT INTO knowledge_revisions "
                "(id,property_id,question_key,version,answer,source,approved,actor,reason) "
                "VALUES(?,?,?,?,?,?,1,?,?)",
                (str(uuid4()), pid, draft["question_key"], new_version,
                 draft["answer"], provenance, actor, "local_development_review"),
            )
            _audit(conn, pid, actor, "knowledge_approved", draft["question_key"], draft_id)
        return {
            "question_key": draft["question_key"],
            "version": new_version,
            "status": "approved",
            "published_for_dev_faq": True,
            "production_approval": False,
        }

    @app.post("/api/properties/{slug}/staff/knowledge/drafts/{draft_id}/reject")
    def reject_knowledge(
        slug: str, draft_id: str, body: ReviewReason, x_staff_key: str | None = Header(None)
    ):
        actor = require_staff(slug, x_staff_key)
        with database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pid = property_id(conn, slug)
            draft = conn.execute(
                "SELECT question_key,status FROM knowledge_drafts "
                "WHERE property_id=? AND id=?",
                (pid, draft_id),
            ).fetchone()
            if not draft:
                raise HTTPException(404, "Knowledge draft not found")
            if draft["status"] != "draft":
                raise HTTPException(409, "Knowledge draft is no longer pending")
            conn.execute(
                "UPDATE knowledge_drafts SET status='rejected',decided_at=CURRENT_TIMESTAMP "
                "WHERE property_id=? AND id=?",
                (pid, draft_id),
            )
            _audit(conn, pid, actor, "knowledge_rejected", draft["question_key"], draft_id, body.reason)
        return {"draft_id": draft_id, "status": "rejected", "published": False}

    @app.post("/api/properties/{slug}/staff/knowledge/{question_key}/withdraw")
    def withdraw_knowledge(
        slug: str, question_key: KnowledgeKey, body: ReviewReason,
        x_staff_key: str | None = Header(None),
    ):
        actor = require_staff(slug, x_staff_key)
        with database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pid = property_id(conn, slug)
            old = conn.execute(
                "SELECT answer,source,version,approved FROM public_facts "
                "WHERE property_id=? AND question_key=?",
                (pid, question_key),
            ).fetchone()
            if not old or not old["approved"]:
                raise HTTPException(409, "No published knowledge fact is available to withdraw")
            version = old["version"] + 1
            conn.execute(
                "UPDATE public_facts SET approved=0,version=? "
                "WHERE property_id=? AND question_key=?",
                (version, pid, question_key),
            )
            conn.execute(
                "INSERT INTO knowledge_revisions "
                "(id,property_id,question_key,version,answer,source,approved,actor,reason) "
                "VALUES(?,?,?,?,?,?,0,?,?)",
                (str(uuid4()), pid, question_key, version, old["answer"],
                 old["source"], actor, body.reason),
            )
            _audit(conn, pid, actor, "knowledge_withdrawn", question_key, details=body.reason)
        return {
            "question_key": question_key,
            "version": version,
            "status": "withdrawn",
            "visible_in_public_faq": False,
        }

    @app.get("/api/properties/{slug}/staff/knowledge/history")
    def knowledge_history(
        slug: str, question_key: KnowledgeKey | None = Query(None),
        x_staff_key: str | None = Header(None),
    ):
        require_staff(slug, x_staff_key)
        with database() as conn:
            pid = property_id(conn, slug)
            if question_key:
                history = conn.execute(
                    "SELECT question_key,version,answer,source,approved,actor,reason,created_at "
                    "FROM knowledge_revisions WHERE property_id=? AND question_key=? "
                    "ORDER BY version DESC LIMIT 100",
                    (pid, question_key),
                ).fetchall()
            else:
                history = conn.execute(
                    "SELECT question_key,version,answer,source,approved,actor,reason,created_at "
                    "FROM knowledge_revisions WHERE property_id=? "
                    "ORDER BY created_at DESC,version DESC LIMIT 100",
                    (pid,),
                ).fetchall()
        return {"property": slug, "history": [dict(row) for row in history],
                "production_approval": False}
