"""SQLite-only hotel knowledge draft, separate approval and safe guest visibility."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
import knowledge_editor


@pytest.fixture
def rig(tmp_path, monkeypatch):
    location = tmp_path / "knowledge.sqlite3"
    monkeypatch.setenv("WF_DATABASE_PATH", str(location))
    monkeypatch.setenv(
        "WF_DEV_STAFF_KEYS_JSON",
        json.dumps({"demo-hotel": "hotel-a-staff-123", "demo-hotel-two": "hotel-b-staff-789"}),
    )
    monkeypatch.setenv(
        "WF_DEV_APPROVAL_KEYS_JSON",
        json.dumps({"demo-hotel": "A"*43, "demo-hotel-two": "B"*43}),
    )
    with TestClient(main.app) as client:
        yield client, location


def staff(slug="demo-hotel"):
    return {"X-Staff-Key": "hotel-a-staff-123" if slug == "demo-hotel" else "hotel-b-staff-789"}


def approved(slug="demo-hotel"):
    return {"X-Approval-Key": "A"*43 if slug == "demo-hotel" else "B"*43}


def route(slug="demo-hotel"):
    return f"/api/properties/{slug}/staff/knowledge"


def save(client, answer, *, key="name", version=1, slug="demo-hotel"):
    return client.post(route(slug)+"/drafts", headers=staff(slug), json={
        "question_key": key, "answer": answer,
        "expected_published_version": version,
    })


def guest_name(client, slug="demo-hotel"):
    return client.post(f"/api/properties/{slug}/information", json={
        "question": "What is the hotel called?"
    }).json()


def test_private_local_drafts_do_not_change_published_guest_answers(rig):
    client, db = rig
    original = guest_name(client)
    assert original["status"] == "answered"
    draft = save(client, "The test property is called Synthetic Meridian Hotel.")
    assert draft.status_code == 200
    assert draft.json()["status"] == "awaiting_local_review"
    assert draft.json()["guest_visible"] is False
    assert guest_name(client)["answer"] == original["answer"]
    listing = client.get(route(), headers=staff())
    assert listing.status_code == 200
    assert listing.headers["Cache-Control"] == "no-store"
    entry = next(item for item in listing.json()["facts"] if item["key"] == "name")
    assert entry["draft"]["answer"] == "The test property is called Synthetic Meridian Hotel."
    assert entry["published"]["version"] == 1
    assert listing.json()["real_hotel_approval"] is False
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM knowledge_audit").fetchone()[0] == 1


def test_only_second_key_can_approve_and_stale_revision_is_rejected(rig):
    client, db = rig
    assert save(client, "Provisional synthetic hotel name for local review.").json()["revision"] == 1
    assert save(client, "Updated synthetic hotel name after staff correction.").json()["revision"] == 2
    path = route()+"/name/approve"
    payload = {"expected_draft_revision": 2}
    assert client.post(path, json=payload, headers=staff()).status_code in (403, 503)
    assert client.post(path, json=payload, headers={"X-Approval-Key": "bad"}).status_code == 403
    assert client.post(path, json={"expected_draft_revision": 1}, headers=approved()).status_code == 409
    assert client.post(path, json=payload, headers=approved("demo-hotel-two")).status_code == 403
    before = guest_name(client)["answer"]
    assert before != "Updated synthetic hotel name after staff correction."
    success = client.post(path, json=payload, headers=approved())
    assert success.status_code == 200
    assert success.json()["published_version"] == 2
    assert success.json()["real_hotel_approval"] is False
    assert guest_name(client)["answer"] == "Updated synthetic hotel name after staff correction."
    assert guest_name(client, "demo-hotel-two")["answer"] != guest_name(client)["answer"]
    assert client.post(path, json=payload, headers=approved()).status_code == 404
    with sqlite3.connect(db) as conn:
        published = conn.execute(
            "SELECT version,source,approved FROM public_facts "
            "WHERE property_id='demo-hotel' AND question_key='name'"
        ).fetchone()
        assert published == (2, "local_dev_approval_fixture", 1)
        assert conn.execute("SELECT COUNT(*) FROM knowledge_drafts").fetchone()[0] == 0
        assert [row[0] for row in conn.execute(
            "SELECT action FROM knowledge_audit ORDER BY rowid"
        ).fetchall()][-1] == "draft_published_local"


def test_withdraw_publication_causes_guest_fallback_not_fake_answer(rig):
    client, _ = rig
    before = guest_name(client)
    assert before["status"] == "answered"
    path = route()+"/name/withdraw"
    assert client.post(path, headers=staff()).status_code in (403, 503)
    assert client.post(path, headers=approved("demo-hotel-two")).status_code == 403
    result = client.post(path, headers=approved())
    assert result.status_code == 200
    assert result.json()["published"] is False
    fallback = guest_name(client)
    assert fallback["status"] == "unknown"
    assert fallback["answer"] is None
    assert fallback["next_action"] == "human_enquiry"
    assert client.post(path, headers=approved()).status_code == 409


def test_stale_draft_cannot_override_newer_published_version(rig):
    client, db = rig
    first = save(client, "Synthetic hotel name awaiting local approval.")
    assert first.status_code == 200
    assert client.post(route()+"/name/withdraw", headers=approved()).status_code == 200
    # Guest-publication revision moved from 1 to 2 after withdrawal.
    assert client.post(route()+"/name/approve",
                       headers=approved(), json={"expected_draft_revision": 1}).status_code == 409
    assert save(client, "A new synthetic hotel name with reviewed version.",
                version=1).status_code == 409
    assert save(client, "A new synthetic hotel name with reviewed version.",
                version=2).status_code == 200
    assert client.post(route()+"/name/approve",
                       headers=approved(), json={"expected_draft_revision": 2}).status_code == 200
    assert guest_name(client)["status"] == "answered"


def test_wrong_tenant_and_unauthorized_staff_cannot_edit_or_approve(rig):
    client, _ = rig
    assert client.get(route()).status_code == 401
    assert client.get(route(), headers=staff("demo-hotel-two")).status_code == 401
    assert save(client, "Valid synthetic local example", slug="demo-hotel-two").status_code == 200
    assert client.post(route("demo-hotel-two")+"/name/approve",
                       json={"expected_draft_revision": 1}, headers=approved("demo-hotel")).status_code == 403
    assert client.post(route("demo-hotel-two")+"/name/approve",
                       json={"expected_draft_revision": 1}, headers=approved("demo-hotel-two")).status_code == 200
    assert "Valid synthetic local example" not in guest_name(client)["answer"]
    assert "Valid synthetic local example" in guest_name(client, "demo-hotel-two")["answer"]


@pytest.mark.parametrize("body", [
    {"question_key": "payments", "answer": "Unsupported key should be refused", "expected_published_version": 1},
    {"question_key": "name", "answer": "short", "expected_published_version": 1},
    {"question_key": "name", "answer": "Valid approved fact for synthetic hotel", "expected_published_version": -1},
])
def test_invalid_draft_inputs_rejected_without_writes(rig, body):
    client, db = rig
    r = client.post(route()+"/drafts", headers=staff(), json=body)
    assert r.status_code == 422
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM knowledge_drafts").fetchone()[0] == 0


def test_draft_and_publication_audit_failure_roll_back_atomically(rig, monkeypatch):
    client, db = rig
    original = knowledge_editor._audit
    def broken(*args, **kwargs):
        raise sqlite3.OperationalError("simulated unavailable knowledge audit storage")
    monkeypatch.setattr(knowledge_editor, "_audit", broken)
    with pytest.raises(sqlite3.OperationalError):
        save(client, "Synthetic hotel facts cannot publish without audit.")
    monkeypatch.setattr(knowledge_editor, "_audit", original)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM knowledge_drafts").fetchone()[0] == 0

    assert save(client, "Synthetic hotel now has a draft awaiting approval.").status_code == 200
    monkeypatch.setattr(knowledge_editor, "_audit", broken)
    with pytest.raises(sqlite3.OperationalError):
        client.post(route()+"/name/approve",
                    headers=approved(), json={"expected_draft_revision": 1})
    monkeypatch.setattr(knowledge_editor, "_audit", original)
    with sqlite3.connect(db) as conn:
        public = conn.execute(
            "SELECT version,source FROM public_facts "
            "WHERE property_id='demo-hotel' AND question_key='name'"
        ).fetchone()
        assert public == (1, "synthetic_demo_fixture")
        assert conn.execute("SELECT COUNT(*) FROM knowledge_drafts").fetchone()[0] == 1


def test_production_import_remains_disabled(rig):
    client, _ = rig
    assert client.get("/health").json()["live_bookings"] is False
    assert client.get("/health").json()["live_payments"] is False


def test_knowledge_web_route_and_assets_available(rig):
    client, _ = rig
    page = client.get("/staff/knowledge")
    assert page.status_code == 200
    assert "Publish facts with review" in page.text
    assert "knowledge-approve" in page.text
    js = client.get("/static/knowledge.js")
    assert js.status_code == 200
    assert "WF_DEV_APPROVAL_KEYS_JSON" not in js.text
    assert "localStorage" not in js.text
    assert "sessionStorage" not in js.text
