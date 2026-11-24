"""Synthetic hotel knowledge draft/review/approval for local SQLite development only.

There is no real editor identity, hotel approval, production CMS, or external API.
A separate local approval key exercises distinct roles without pretending to
implement a verified staff/manager login.
"""
from hashlib import sha256
import hmac
import json
import os
from uuid import uuid4

from fastapi import Header, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

KEYS = ("name", "booking", "staff")
FactKey = Literal["name", "booking", "staff"]


def initialize_knowledge_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS knowledge_drafts (
        property_id TEXT NOT NULL,
        question_key TEXT NOT NULL CHECK(question_key IN ('name','booking','staff')),
        answer TEXT NOT NULL,
        base_version INTEGER NOT NULL CHECK(base_version >= 0),
        revision INTEGER NOT NULL CHECK(revision >= 1),
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(property_id, question_key),
        FOREIGN KEY(property_id) REFERENCES properties(id)
    );
    CREATE TABLE IF NOT EXISTS knowledge_audit (
        id TEXT PRIMARY KEY,
        property_id TEXT NOT NULL,
        question_key TEXT NOT NULL,
        action TEXT NOT NULL,
        version INTEGER NOT NULL,
        answer_sha256 TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(property_id) REFERENCES properties(id)
    );
    CREATE INDEX IF NOT EXISTS idx_knowledge_audit
      ON knowledge_audit(property_id,question_key,created_at);
    """)


def require_local_approver(slug, approval_key):
    try:
        keys = json.loads(os.getenv("WF_DEV_APPROVAL_KEYS_JSON", "{}"))
    except (ValueError, TypeError):
        raise HTTPException(503, "Local approval keys misconfigured")
    expected = keys.get(slug) if isinstance(keys, dict) else None
    if not isinstance(expected, str) or len(expected) < 32:
        raise HTTPException(503, "Local approval key not configured")
    if not approval_key or not hmac.compare_digest(expected, approval_key):
        raise HTTPException(403, "Local content approval not authorized")
    return "dev-approver:" + slug


class DraftInput(BaseModel):
    question_key: FactKey
    answer: str = Field(min_length=10, max_length=1200)
    expected_published_version: int = Field(ge=0)


class RevisionInput(BaseModel):
    expected_draft_revision: int = Field(ge=1)


def _audit(conn, property_key, key, action, version, answer=None):
    conn.execute(
        "INSERT INTO knowledge_audit(id,property_id,question_key,action,version,answer_sha256) "
        "VALUES (?,?,?,?,?,?)",
        (
            str(uuid4()), property_key, key, action, version,
            sha256(answer.encode()).hexdigest() if answer is not None else None,
        ),
    )


def install_knowledge_routes(app, database, property_id, require_staff):
    @app.get("/api/properties/{slug}/staff/knowledge")
    def list_local_knowledge(slug: str, x_staff_key: str | None = Header(None)):
        require_staff(slug, x_staff_key)
        with database() as conn:
            pid = property_id(conn, slug)
            published = {
                row["question_key"]: dict(row) for row in conn.execute(
                    "SELECT question_key,answer,version,approved,source FROM public_facts "
                    "WHERE property_id=?", (pid,)
                )
            }
            drafts = {
                row["question_key"]: dict(row) for row in conn.execute(
                    "SELECT question_key,answer,base_version,revision,updated_at "
                    "FROM knowledge_drafts WHERE property_id=?", (pid,)
                )
            }
        return {
            "source": "local_sqlite_development_only",
            "real_hotel_approval": False,
            "guest_visible_only_if_approved": True,
            "facts": [
                {"key": key, "published": published.get(key), "draft": drafts.get(key)}
                for key in KEYS
            ],
        }

    @app.post("/api/properties/{slug}/staff/knowledge/drafts")
    def save_local_draft(slug: str, body: DraftInput, x_staff_key: str | None = Header(None)):
        actor = require_staff(slug, x_staff_key)
        answer = body.answer.strip()
        if len(answer) < 10:
            raise HTTPException(422, "Draft answer must contain at least 10 visible characters")
        with database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pid = property_id(conn, slug)
            published = conn.execute(
                "SELECT version FROM public_facts WHERE property_id=? AND question_key=?",
                (pid, body.question_key)
            ).fetchone()
            version = published["version"] if published else 0
            if version != body.expected_published_version:
                raise HTTPException(409, "Published content changed. Refresh and review again.")
            draft = conn.execute(
                "SELECT revision FROM knowledge_drafts WHERE property_id=? AND question_key=?",
                (pid, body.question_key)
            ).fetchone()
            revision = (draft["revision"] + 1) if draft else 1
            conn.execute(
                "INSERT INTO knowledge_drafts(property_id,question_key,answer,base_version,revision) "
                "VALUES(?,?,?,?,?) ON CONFLICT(property_id,question_key) DO UPDATE SET "
                "answer=excluded.answer,base_version=excluded.base_version,"
                "revision=excluded.revision,updated_at=CURRENT_TIMESTAMP",
                (pid, body.question_key, answer, version, revision),
            )
            _audit(conn, pid, body.question_key, "draft_saved:" + actor, revision, answer)
        return {
            "question_key": body.question_key, "revision": revision,
            "published_unchanged": True, "guest_visible": False,
            "status": "awaiting_local_review",
        }

    @app.post("/api/properties/{slug}/staff/knowledge/{key}/approve")
    def approve_local_draft(
        slug: str, key: FactKey, body: RevisionInput,
        x_approval_key: str | None = Header(None)
    ):
        # Not the general staff key: approval requires a separate locally
        # generated key. Production will require verified hotel manager RBAC.
        require_local_approver(slug, x_approval_key)
        with database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pid = property_id(conn, slug)
            draft = conn.execute(
                "SELECT answer,base_version,revision FROM knowledge_drafts "
                "WHERE property_id=? AND question_key=?", (pid, key)
            ).fetchone()
            if not draft:
                raise HTTPException(404, "No draft awaiting review")
            if draft["revision"] != body.expected_draft_revision:
                raise HTTPException(409, "Draft changed since review. Refresh before approving.")
            published = conn.execute(
                "SELECT version FROM public_facts WHERE property_id=? AND question_key=?",
                (pid, key)
            ).fetchone()
            published_version = published["version"] if published else 0
            if published_version != draft["base_version"]:
                raise HTTPException(409, "Published content changed. Review draft again.")
            next_version = published_version + 1
            conn.execute(
                "INSERT INTO public_facts(property_id,question_key,answer,version,approved,source) "
                "VALUES(?,?,?,?,1,'local_dev_approval_fixture') "
                "ON CONFLICT(property_id,question_key) DO UPDATE SET "
                "answer=excluded.answer,version=excluded.version,approved=1,source=excluded.source",
                (pid, key, draft["answer"], next_version),
            )
            _audit(conn, pid, key, "draft_published_local", next_version, draft["answer"])
            conn.execute(
                "DELETE FROM knowledge_drafts WHERE property_id=? AND question_key=?",
                (pid, key),
            )
        return {
            "question_key": key, "published_version": next_version,
            "approved_for_synthetic_local_guest_view": True,
            "real_hotel_approval": False,
        }

    @app.post("/api/properties/{slug}/staff/knowledge/{key}/withdraw")
    def withdraw_local_fact(slug: str, key: FactKey, x_approval_key: str | None = Header(None)):
        require_local_approver(slug, x_approval_key)
        with database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pid = property_id(conn, slug)
            changed = conn.execute(
                "UPDATE public_facts SET approved=0,version=version+1 "
                "WHERE property_id=? AND question_key=? AND approved=1",
                (pid, key),
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "This fact is not currently published")
            row = conn.execute(
                "SELECT version FROM public_facts WHERE property_id=? AND question_key=?",
                (pid, key),
            ).fetchone()
            # The previously prepared draft, if present, now has an obsolete
            # base_version and cannot be approved without explicit review.
            _audit(conn, pid, key, "local_publication_withdrawn", row["version"])
        return {"question_key": key, "published": False, "real_hotel_approval": False}
