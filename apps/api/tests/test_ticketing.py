"""IT and hotel service tickets: property security, lifecycle, SLA and atomic audit."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
import ticketing


@pytest.fixture
def rig(tmp_path, monkeypatch):
    db = tmp_path / "ticket-api.sqlite3"
    monkeypatch.setenv("WF_DATABASE_PATH", str(db))
    monkeypatch.setenv("WF_DEV_STAFF_KEYS_JSON", json.dumps({
        "demo-hotel": "only-hotel-one",
        "demo-hotel-two": "only-hotel-two",
    }))
    with TestClient(main.app) as client:
        yield client, db


def headers(slug="demo-hotel"):
    return {"X-Staff-Key": {"demo-hotel": "only-hotel-one", "demo-hotel-two": "only-hotel-two"}[slug]}


def create(client, key="support-ticket-012345", category="it", slug="demo-hotel", origin_case_id=None):
    return client.post(f"/api/properties/{slug}/staff/tickets", headers=headers(slug), json={
        "request_key": key,
        "category": category,
        "priority": "high",
        "subject": "Reception network is unavailable",
        "description": "Front desk workstations cannot connect to the hotel Wi-Fi.",
        "origin_case_id": origin_case_id,
    })


def url(ticket_id, slug="demo-hotel"):
    return f"/api/properties/{slug}/staff/tickets/{ticket_id}"


def test_hotel_it_ticket_lifecycle_and_audit(rig):
    client, db = rig
    created = create(client)
    assert created.status_code == 201
    ticket_id = created.json()["ticket_id"]
    assert created.json()["status"] == "open"
    found = client.get(url(ticket_id), headers=headers())
    assert found.status_code == 200
    assert found.json()["ticket"]["category"] == "it"
    assert found.json()["ticket"]["priority"] == "high"
    assert found.json()["ticket"]["assigned_to"] is None
    assert found.json()["ticket"]["overdue"] is False

    metrics = client.get("/api/properties/demo-hotel/staff/tickets/metrics", headers=headers()).json()
    assert metrics["total"] == 1
    assert metrics["unresolved"] == 1
    assert metrics["notifications_live"] is False
    assert metrics["by_status"]["open"] == 1

    # Staff must acknowledge before starting, and start before resolving.
    assert client.post(url(ticket_id) + "/start", headers=headers()).status_code == 409
    assert client.post(url(ticket_id) + "/claim", headers=headers()).json()["status"] == "assigned"
    assert client.post(url(ticket_id) + "/claim", headers=headers()).status_code == 409
    assert client.post(url(ticket_id) + "/start", headers=headers()).json()["status"] == "in_progress"
    note = client.post(url(ticket_id) + "/notes", headers=headers(), json={"text": "Router diagnostic underway"})
    assert note.status_code == 201
    assert client.post(url(ticket_id) + "/resolve", headers=headers(), json={"summary": "Restarted router and verified network on front desk."}).status_code == 200
    assert client.post(url(ticket_id) + "/resolve", headers=headers(), json={"summary": "Duplicate resolution."}).status_code == 409
    metrics = client.get("/api/properties/demo-hotel/staff/tickets/metrics", headers=headers()).json()
    assert metrics["by_status"]["resolved"] == 1
    assert metrics["unresolved"] == 0
    assert client.post(url(ticket_id) + "/reopen", headers=headers(), json={"text": "The fault has returned."}).json()["status"] == "reopened"
    assert client.post(url(ticket_id) + "/claim", headers=headers()).json()["status"] == "assigned"

    detail = client.get(url(ticket_id), headers=headers()).json()
    assert [e["event"] for e in detail["history"]] == [
        "ticket_created", "ticket_claimed", "ticket_started", "ticket_note",
        "ticket_resolved", "ticket_reopened", "ticket_claimed",
    ]
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM service_tickets").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM ticket_history").fetchone()[0] == 7
        assert con.execute("SELECT COUNT(*) FROM ticket_outbox").fetchone()[0] == 7
        assert con.execute("SELECT COUNT(*) FROM ticket_outbox WHERE processed_at IS NOT NULL").fetchone()[0] == 0


def test_guest_and_wrong_property_cannot_read_or_change_tickets(rig):
    client, db = rig
    tid = create(client).json()["ticket_id"]
    assert client.get(url(tid)).status_code == 401
    assert client.get(url(tid), headers=headers("demo-hotel-two")).status_code == 401
    assert client.get(url(tid, "demo-hotel-two"), headers=headers("demo-hotel-two")).status_code == 404
    assert client.post(url(tid, "demo-hotel-two") + "/claim", headers=headers("demo-hotel-two")).status_code == 404
    assert client.get("/api/properties/demo-hotel/staff/tickets").status_code == 401
    assert client.get("/api/properties/demo-hotel/staff/tickets/metrics").status_code == 401
    other = client.get("/api/properties/demo-hotel-two/staff/tickets/metrics", headers=headers("demo-hotel-two")).json()
    assert other["total"] == 0
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT status FROM service_tickets WHERE id=?", (tid,)).fetchone()[0] == "open"


def test_idempotency_one_ticket_one_event(rig):
    client, db = rig
    first = create(client, key="idempotent-guest-work-10001")
    repeated = create(client, key="idempotent-guest-work-10001")
    assert first.status_code == repeated.status_code == 201
    assert first.json()["ticket_id"] == repeated.json()["ticket_id"]
    assert repeated.json()["duplicate"] is True
    collision = client.post("/api/properties/demo-hotel/staff/tickets", headers=headers(), json={
        "request_key": "idempotent-guest-work-10001", "category": "it", "priority": "high",
        "subject": "Another incident", "description": "A completely different reported incident"
    })
    assert collision.status_code == 409
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM service_tickets").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM ticket_history").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM ticket_outbox").fetchone()[0] == 1


def test_link_to_reception_case_requires_claim_and_correct_tenant(rig):
    client, db = rig
    enquiry = client.post("/api/properties/demo-hotel/enquiries", json={
        "request_key": "guest-case-000123456", "kind": "support",
        "name": "Synthetic Guest", "contact": "guest@example.invalid",
        "details": "There is no working air conditioning in my room"
    }).json()["case_id"]

    # Cannot convert an unclaimed enquiry into a silently assigned ticket.
    assert create(client, key="from-enquiry-000001", category="maintenance", origin_case_id=enquiry).status_code == 409
    claim = client.post(f"/api/properties/demo-hotel/staff/enquiries/{enquiry}/claim", headers=headers())
    assert claim.status_code == 200
    made = create(client, key="from-enquiry-000001", category="maintenance", origin_case_id=enquiry)
    assert made.status_code == 201
    assert create(client, key="from-enquiry-000002", category="maintenance", origin_case_id=enquiry).status_code == 409
    assert create(client, key="from-another-000003", category="maintenance", slug="demo-hotel-two", origin_case_id=enquiry).status_code == 404
    detail = client.get(url(made.json()["ticket_id"]), headers=headers()).json()
    assert detail["ticket"]["origin_case_id"] == enquiry


def test_overdue_and_priority_filtering(rig):
    client, db = rig
    first = create(client, key="overdue-ticket-123456").json()["ticket_id"]
    create(client, key="other-ticket-123456", category="housekeeping")
    with sqlite3.connect(db) as con:
        con.execute("UPDATE service_tickets SET due_at='2000-01-01T00:00:00+00:00' WHERE id=?", (first,))
    current = client.get("/api/properties/demo-hotel/staff/tickets/metrics", headers=headers()).json()
    assert current["overdue"] == 1
    filtered = client.get("/api/properties/demo-hotel/staff/tickets?category=it", headers=headers()).json()["tickets"]
    assert len(filtered) == 1
    assert filtered[0]["overdue"] is True
    assert client.get("/api/properties/demo-hotel/staff/tickets?limit=1000", headers=headers()).status_code == 422
    assert client.get("/api/properties/demo-hotel/staff/tickets?category=random", headers=headers()).status_code == 422


def test_failed_history_write_rolls_back_ticket(rig, monkeypatch):
    client, db = rig
    original=ticketing.record_ticket_change
    def broken(*args,**kwargs):
        raise sqlite3.OperationalError("Simulated unavailable audit storage")
    monkeypatch.setattr(ticketing, "record_ticket_change", broken)
    with pytest.raises(sqlite3.OperationalError):
        create(client, key="rollback-on-audit-00001")
    monkeypatch.setattr(ticketing,"record_ticket_change",original)
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM service_tickets").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM ticket_history").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM ticket_outbox").fetchone()[0] == 0


@pytest.mark.parametrize("bad",[
    {"category":"piracy"},
    {"priority":"critical"},
    {"subject":"Hi"},
    {"description":"short"},
])
def test_invalid_categories_and_inputs_rejected(rig,bad):
    client, _=rig
    payload={"request_key":"invalid-ticket-00123","category":"it","priority":"normal",
             "subject":"Front desk laptop problem","description":"The front desk laptop will not turn on"}
    payload.update(bad)
    resp=client.post("/api/properties/demo-hotel/staff/tickets",headers=headers(),json=payload)
    assert resp.status_code==422
