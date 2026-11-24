"""Source-of-truth local SQLite management dashboard tests.

These checks use only synthetic hotel records and the existing FastAPI app.
They do NOT assert real hotel performance, external delivery or production RBAC.
"""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


KEYS = {"demo-hotel": "key-hotel-one-local", "demo-hotel-two": "key-hotel-two-local"}


@pytest.fixture
def rig(tmp_path, monkeypatch):
    path = tmp_path / "operations.sqlite3"
    monkeypatch.setenv("WF_DATABASE_PATH", str(path))
    monkeypatch.setenv("WF_DEV_STAFF_KEYS_JSON", json.dumps(KEYS))
    with TestClient(main.app) as client:
        yield client, path


def overview(client, hotel="demo-hotel", key=None):
    return client.get(
        f"/api/properties/{hotel}/staff/operations/overview",
        headers={"X-Staff-Key": key or KEYS[hotel]},
    )


def enquiry(client, hotel, request_key):
    response = client.post(f"/api/properties/{hotel}/enquiries", json={
        "request_key": request_key,
        "kind": "support",
        "name": "Synthetic Guest",
        "contact": "nobody@example.invalid",
        "details": "I would like help with a synthetic hotel service request.",
    })
    assert response.status_code == 201
    return response.json()["case_id"]


def ticket(client, hotel, request_key, source=None):
    response = client.post(
        f"/api/properties/{hotel}/staff/tickets",
        headers={"X-Staff-Key": KEYS[hotel]},
        json={
            "request_key": request_key,
            "category": "maintenance",
            "priority": "normal",
            "subject": "Synthetic air conditioner fault",
            "description": "Maintenance report for a synthetic hotel room only.",
            "origin_case_id": source,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["ticket_id"]


def test_empty_hotel_shows_actual_zeros_not_synthetic_dashboard_numbers(rig):
    client, _ = rig
    for slug in KEYS:
        response = overview(client, slug)
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "local_sqlite_development"
        assert data["property"]["slug"] == slug
        assert data["case_counts"] == {
            "total": 0, "by_status": {"queued": 0, "claimed": 0, "responded": 0},
            "by_kind": {},
        }
        assert data["ticket_counts"]["total"] == 0
        assert data["ticket_counts"]["overdue"] == 0
        assert data["local_events"]["pending_total"] == 0
        assert data["local_events"]["provider_delivery_connected"] is False
        assert data["local_events"]["delivery_confirmed"] is False
        assert data["external_metrics"]["confirmed_bookings"] is None
        assert data["external_metrics"]["hotel_revenue"] is None
        assert data["external_metrics"]["occupancy"] is None
        assert data["recent_activity"] == []
        assert datetime.fromisoformat(data["generated_at"]).tzinfo == timezone.utc
        assert response.headers["Cache-Control"] == "no-store"


def test_property_authentication_and_not_found_do_not_leak_records(rig):
    client, _ = rig
    enquiry(client, "demo-hotel", "case-only-hotel-one-1234")
    url = "/api/properties/demo-hotel/staff/operations/overview"
    denied = client.get(url)
    wrong = client.get(url, headers={"X-Staff-Key": KEYS["demo-hotel-two"]})
    assert denied.status_code == wrong.status_code == 401
    assert denied.headers["Cache-Control"] == "no-store"
    assert wrong.headers["Cache-Control"] == "no-store"
    second = overview(client, "demo-hotel-two")
    assert second.json()["case_counts"]["total"] == 0
    assert client.get(
        "/api/properties/unknown/staff/operations/overview",
        headers={"X-Staff-Key": KEYS["demo-hotel"]},
    ).status_code == 401


def test_actual_case_ticket_pending_event_and_activity_counts_are_tenant_scoped(rig):
    client, path = rig
    a1 = enquiry(client, "demo-hotel", "hotel-one-request-00001")
    enquiry(client, "demo-hotel", "hotel-one-request-00002")
    b1 = enquiry(client, "demo-hotel-two", "hotel-two-request-00003")

    case_path = f"/api/properties/demo-hotel/staff/enquiries/{a1}"
    assert client.post(case_path + "/claim", headers={"X-Staff-Key": KEYS["demo-hotel"]}).status_code == 200
    assert client.post(
        case_path + "/respond",
        headers={"X-Staff-Key": KEYS["demo-hotel"]},
        json={"message": "Synthetic staff reply only, no external notification."},
    ).status_code == 200

    a_ticket = ticket(client, "demo-hotel", "hotel-one-ticket-001", source=a1)
    ticket(client, "demo-hotel", "hotel-one-ticket-002")
    b_ticket = ticket(client, "demo-hotel-two", "hotel-two-ticket-003")

    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE service_tickets SET due_at='2000-01-01T00:00:00+00:00' WHERE id=?",
            (a_ticket,),
        )

    a = overview(client).json()
    b = overview(client, "demo-hotel-two").json()

    assert a["case_counts"]["total"] == 2
    assert a["case_counts"]["by_status"] == {"queued": 1, "claimed": 0, "responded": 1}
    assert a["case_counts"]["by_kind"] == {"support": 2}
    assert a["ticket_counts"]["total"] == 2
    assert a["ticket_counts"]["by_status"]["open"] == 2
    assert a["ticket_counts"]["by_category"] == {"maintenance": 2}
    assert a["ticket_counts"]["unresolved"] == 2
    assert a["ticket_counts"]["overdue"] == 1
    assert a["local_events"] == {
        "pending_case_events": 4,
        "pending_ticket_events": 2,
        "pending_total": 6,
        "provider_delivery_connected": False,
        "delivery_confirmed": False,
        "description": "Local pending records only, not messages sent or delivered.",
    }

    assert b["case_counts"]["total"] == 1
    assert b["case_counts"]["by_status"]["queued"] == 1
    assert b["ticket_counts"]["total"] == 1
    assert b["local_events"]["pending_total"] == 2

    refs_a = {event["reference"] for event in a["recent_activity"]}
    assert a1 in refs_a
    assert a_ticket in refs_a
    assert b1 not in refs_a
    assert b_ticket not in refs_a
    assert "nobody@example.invalid" not in json.dumps(a)
    assert "nobody@example.invalid" not in json.dumps(b)
    assert all(event["type"] in ("guest_case", "service_ticket") for event in a["recent_activity"])


def test_resolved_ticket_and_pending_local_event_counts_follow_sqlite_changes(rig):
    client, path = rig
    tid = ticket(client, "demo-hotel", "ticket-status-updates-001")
    endpoint = f"/api/properties/demo-hotel/staff/tickets/{tid}"
    key = {"X-Staff-Key": KEYS["demo-hotel"]}
    assert client.post(endpoint + "/claim", headers=key).status_code == 200
    assert client.post(endpoint + "/start", headers=key).status_code == 200
    assert client.post(
        endpoint + "/resolve", headers=key,
        json={"summary": "Synthetic work concluded locally, not at a real hotel."},
    ).status_code == 200
    data = overview(client).json()
    assert data["ticket_counts"]["by_status"]["resolved"] == 1
    assert data["ticket_counts"]["unresolved"] == 0
    assert data["local_events"]["pending_ticket_events"] == 4

    # Mark one event processed as a LOCAL simulation; still not delivered.
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE ticket_outbox SET processed_at=CURRENT_TIMESTAMP WHERE id=("
            "SELECT id FROM ticket_outbox WHERE property_id='demo-hotel' ORDER BY rowid LIMIT 1)"
        )
    next_data = overview(client).json()
    assert next_data["local_events"]["pending_ticket_events"] == 3
    assert next_data["local_events"]["delivery_confirmed"] is False


def test_malformed_due_date_is_visible_not_misreported_as_on_time(rig):
    client, path = rig
    ticket_id = ticket(client, "demo-hotel", "due-date-invalid-0001")
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE service_tickets SET due_at='corrupt-date' WHERE id=?", (ticket_id,))
    response = overview(client)
    assert response.status_code == 200
    details = response.json()["ticket_counts"]
    assert details["overdue"] == 0
    assert details["invalid_due_dates"] == 1
    assert details["unresolved"] == 1
