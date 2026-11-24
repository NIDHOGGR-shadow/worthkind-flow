"""SQLite hotel knowledge approval/withdrawal: real local transactions, fake hotels.

Production-level hotel owner identity and two-person approval are NOT present.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
import knowledge


KEYS = {"demo-hotel": "local-knowledge-key-one", "demo-hotel-two": "local-knowledge-key-two"}


@pytest.fixture
def rig(tmp_path, monkeypatch):
    db = tmp_path / "knowledge.sqlite3"
    monkeypatch.setenv("WF_DATABASE_PATH", str(db))
    monkeypatch.setenv("WF_DEV_STAFF_KEYS_JSON", json.dumps(KEYS))
    with TestClient(main.app) as client:
        yield client, db


def auth(slug="demo-hotel"):
    return {"X-Staff-Key": KEYS[slug]}


def draft(client, slug, key, question_key="dining", answer=None, source=None):
    return client.post(
        f"/api/properties/{slug}/staff/knowledge/drafts",
        headers=auth(slug),
        json={
            "request_key": key,
            "question_key": question_key,
            "answer": answer or "Synthetic dining is available only after a person verifies it.",
            "source_reference": source or "Local synthetic staff QA reference",
        },
    )


def public(client, slug, question):
    return client.post(
        f"/api/properties/{slug}/information",
        json={"question": question},
    )


def test_draft_is_not_public_until_approved_and_versions_are_preserved(rig):
    client, db = rig
    question = "Do you have a restaurant menu?"
    assert public(client, "demo-hotel", question).json()["status"] == "unknown"

    result = draft(client, "demo-hotel", "dining-review-0000001")
    assert result.status_code == 201
    identifier = result.json()["draft_id"]
    assert result.json()["status"] == "draft"
    assert result.json()["base_version"] == 0
    assert result.json()["published"] is False

    # Only the property's development key sees the unpublished source and draft.
    listed = client.get("/api/properties/demo-hotel/staff/knowledge", headers=auth())
    assert listed.status_code == 200
    assert listed.json()["production_approval"] is False
    assert any(row["id"] == identifier for row in listed.json()["drafts"])
    assert public(client, "demo-hotel", question).json()["status"] == "unknown"

    approved = client.post(
        f"/api/properties/demo-hotel/staff/knowledge/drafts/{identifier}/approve",
        headers=auth(),
    )
    assert approved.status_code == 200
    assert approved.json()["version"] == 1
    assert approved.json()["production_approval"] is False

    visible = public(client, "demo-hotel", question)
    assert visible.status_code == 200
    assert visible.json()["status"] == "answered"
    assert visible.json()["version"] == 1
    assert visible.json()["ai_model_invoked"] is False
    assert "Synthetic dining" in visible.json()["answer"]
    assert visible.json()["source"].startswith("local_development_review:")
    assert public(client, "demo-hotel-two", question).json()["status"] == "unknown"

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM knowledge_revisions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM knowledge_audit").fetchone()[0] == 2


def test_idempotent_draft_creation_and_payload_conflict(rig):
    client, db = rig
    first = draft(client, "demo-hotel", "reused-draft-key-001")
    again = draft(client, "demo-hotel", "reused-draft-key-001")
    assert first.status_code == again.status_code == 201
    assert again.json()["duplicate"] is True
    assert again.json()["draft_id"] == first.json()["draft_id"]
    conflict = draft(
        client, "demo-hotel", "reused-draft-key-001",
        answer="Different synthetic restaurant menu details that were not in original draft.",
    )
    assert conflict.status_code == 409
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM knowledge_drafts").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM knowledge_audit").fetchone()[0] == 1


def test_competing_drafts_stale_conflict_withdrawal_and_republication(rig):
    client, db = rig
    first = draft(client, "demo-hotel", "versioned-menu-first")
    second = draft(client, "demo-hotel", "versioned-menu-second",
                   answer="Another synthetic draft for the same dining question.")
    first_id = first.json()["draft_id"]
    second_id = second.json()["draft_id"]
    assert first.json()["base_version"] == second.json()["base_version"] == 0

    approve_url = "/api/properties/demo-hotel/staff/knowledge/drafts/"
    assert client.post(approve_url + first_id + "/approve", headers=auth()).status_code == 200
    assert client.post(approve_url + first_id + "/approve", headers=auth()).status_code == 409
    stale = client.post(approve_url + second_id + "/approve", headers=auth())
    assert stale.status_code == 409
    assert "changed after" in stale.json()["detail"]

    withdrawn = client.post(
        "/api/properties/demo-hotel/staff/knowledge/dining/withdraw",
        headers=auth(), json={"reason": "Synthetic verification shows content should no longer be public"},
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["version"] == 2
    assert public(client, "demo-hotel", "restaurant menu").json()["status"] == "unknown"
    assert client.post(
        "/api/properties/demo-hotel/staff/knowledge/dining/withdraw",
        headers=auth(), json={"reason": "Another unnecessary withdrawal request"},
    ).status_code == 409

    renewed = draft(client, "demo-hotel", "versioned-menu-renewed",
                    answer="Updated synthetic restaurant information verified only for local QA.")
    assert renewed.json()["base_version"] == 2
    reapproved = client.post(approve_url + renewed.json()["draft_id"] + "/approve", headers=auth())
    assert reapproved.json()["version"] == 3
    assert public(client, "demo-hotel", "Do you have food?").json()["version"] == 3

    history = client.get(
        "/api/properties/demo-hotel/staff/knowledge/history?question_key=dining",
        headers=auth(),
    )
    assert history.status_code == 200
    versions = history.json()["history"]
    assert [item["version"] for item in versions] == [3, 2, 1]
    assert [item["approved"] for item in versions] == [1, 0, 1]
    with sqlite3.connect(db) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM knowledge_audit WHERE action='knowledge_approved'"
        ).fetchone()[0] == 2


def test_wrong_hotel_and_no_auth_cannot_view_or_publish_drafts(rig):
    client, _ = rig
    draft_id = draft(client, "demo-hotel", "hotel-one-private-faq") .json()["draft_id"]
    a = "/api/properties/demo-hotel/staff/knowledge"
    b = "/api/properties/demo-hotel-two/staff/knowledge"
    assert client.get(a).status_code == 401
    assert client.get(a, headers=auth("demo-hotel-two")).status_code == 401
    assert client.get(b, headers=auth("demo-hotel-two")).json()["drafts"] == []
    hidden = client.post(
        b + "/drafts/" + draft_id + "/approve",
        headers=auth("demo-hotel-two"),
    )
    assert hidden.status_code == 404
    assert client.get(b + "/history", headers=auth("demo-hotel-two")).json()["history"] == []
    assert client.get(a).headers["Cache-Control"] == "no-store"
    assert client.get(a, headers=auth()).headers["Cache-Control"] == "no-store"


def test_rejection_and_failed_audit_transaction_cannot_publish(rig, monkeypatch):
    client, db = rig
    first = draft(client, "demo-hotel", "knowledge-rejected-001")
    draft_id = first.json()["draft_id"]
    rejected = client.post(
        "/api/properties/demo-hotel/staff/knowledge/drafts/" + draft_id + "/reject",
        headers=auth(), json={"reason": "Synthetic source has no authoritative approval"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["published"] is False
    assert client.post(
        "/api/properties/demo-hotel/staff/knowledge/drafts/" + draft_id + "/approve",
        headers=auth(),
    ).status_code == 409
    assert public(client, "demo-hotel", "restaurant menu").json()["status"] == "unknown"

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError("Synthetic audit write failure")

    monkeypatch.setattr(knowledge, "_audit", broken)
    with pytest.raises(sqlite3.OperationalError):
        draft(client, "demo-hotel", "knowledge-audit-rollback")
    with sqlite3.connect(db) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM knowledge_drafts WHERE request_key=?",
            ("knowledge-audit-rollback",),
        ).fetchone()[0] == 0


@pytest.mark.parametrize("bad", [
    {"question_key": "raw_payment_credentials"},
    {"answer": "short"},
    {"source_reference": "short"},
    {"request_key": "no"},
])
def test_invalid_drafts_are_rejected(rig, bad):
    client, _ = rig
    payload = {
        "request_key": "valid-request-key-knowledge",
        "question_key": "dining",
        "answer": "Synthetic restaurant knowledge needing review before publication.",
        "source_reference": "A synthetic local test note",
    }
    payload.update(bad)
    result = client.post(
        "/api/properties/demo-hotel/staff/knowledge/drafts",
        headers=auth(), json=payload,
    )
    assert result.status_code == 422
