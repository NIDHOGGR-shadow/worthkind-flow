"""Local SQLite overview must show sourced counts and refuse cross-hotel access."""
import json
from pathlib import Path
import sqlite3
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


@pytest.fixture
def rig(tmp_path, monkeypatch):
    db = tmp_path / "metrics.sqlite3"
    monkeypatch.setenv("WF_DATABASE_PATH", str(db))
    monkeypatch.setenv("WF_DEV_STAFF_KEYS_JSON", json.dumps({
        "demo-hotel": "local-one",
        "demo-hotel-two": "local-two",
    }))
    with TestClient(main.app) as client:
        yield client, db


def read(client, slug="demo-hotel", key="local-one"):
    return client.get(
        f"/api/properties/{slug}/staff/overview",
        headers={"X-Staff-Key": key} if key else {},
    )


def create_case(client, slug, request_key):
    result = client.post(
        f"/api/properties/{slug}/enquiries",
        json={
            "request_key": request_key, "receipt_token": "T"*40,
            "kind": "support", "name": "Synthetic Only",
            "contact": "guest@example.invalid",
            "details": "Please ask reception to help with the demo.",
        },
    )
    assert result.status_code == 201
    return result.json()["case_id"]


def create_ticket(client, slug, key, request_key, category="maintenance"):
    result = client.post(
        f"/api/properties/{slug}/staff/tickets",
        headers={"X-Staff-Key": key},
        json={
            "request_key": request_key,
            "category": category,
            "priority": "normal",
            "subject": "Synthetic room maintenance",
            "description": "Example fixture for local source-labelled metrics.",
        },
    )
    assert result.status_code == 201
    return result.json()["ticket_id"]


def test_empty_property_only_has_zero_source_derived_counts(rig):
    client, _ = rig
    result = read(client)
    assert result.status_code == 200
    data = result.json()
    assert data["source"] == "property_scoped_local_sqlite"
    assert data["environment"] == "development_only"
    assert data["guest_cases"]["total"] == 0
    assert data["guest_cases"]["awaiting_local_response"] == 0
    assert data["service_tickets"]["total"] == 0
    assert data["service_tickets"]["overdue_demo_targets"] == 0
    assert data["pending_local_events"] == {"guest_case_events": 0, "ticket_events": 0}
    assert data["unavailable_sources"]["hotel_occupancy"] is True
    assert data["unavailable_sources"]["guest_payment_revenue"] is True
    assert data["unavailable_sources"]["actual_notification_delivery"] is True
    assert "guest@example.invalid" not in result.text
    assert result.headers["Cache-Control"] == "no-store"


def test_case_ticket_updates_produce_truthful_isolated_counts(rig):
    client, db = rig
    case_a = create_case(client, "demo-hotel", "metrics-hotel-a-enquiry")
    case_b = create_case(client, "demo-hotel-two", "metrics-hotel-b-enquiry")
    ticket_a = create_ticket(client, "demo-hotel", "local-one", "metrics-ticket-hotel-a")
    ticket_b = create_ticket(client, "demo-hotel-two", "local-two", "metrics-ticket-hotel-b")

    # One local hotel-A claim, which is still waiting for a staff response.
    assert client.post(
        f"/api/properties/demo-hotel/staff/enquiries/{case_a}/claim",
        headers={"X-Staff-Key": "local-one"}
    ).status_code == 200

    # Hotel B has a local response; NOT a sent external message.
    assert client.post(
        f"/api/properties/demo-hotel-two/staff/enquiries/{case_b}/claim",
        headers={"X-Staff-Key": "local-two"}
    ).status_code == 200
    assert client.post(
        f"/api/properties/demo-hotel-two/staff/enquiries/{case_b}/respond",
        headers={"X-Staff-Key": "local-two"},
        json={"message": "Synthetic response; no notification sent."},
    ).status_code == 200

    # Hotel A has one open ticket, and Hotel B has one resolved ticket.
    base_b = f"/api/properties/demo-hotel-two/staff/tickets/{ticket_b}"
    head_b = {"X-Staff-Key": "local-two"}
    assert client.post(base_b + "/claim", headers=head_b).status_code == 200
    assert client.post(base_b + "/start", headers=head_b).status_code == 200
    assert client.post(
        base_b + "/resolve", headers=head_b,
        json={"summary": "Synthetic issue resolved locally. No guest notification sent."}
    ).status_code == 200

    a = read(client).json()
    b = read(client, "demo-hotel-two", "local-two").json()
    assert a["guest_cases"]["total"] == b["guest_cases"]["total"] == 1
    assert a["guest_cases"]["by_status"]["claimed"] == 1
    assert a["guest_cases"]["awaiting_local_response"] == 1
    assert b["guest_cases"]["by_status"]["responded"] == 1
    assert b["guest_cases"]["awaiting_local_response"] == 0
    assert a["service_tickets"]["total"] == b["service_tickets"]["total"] == 1
    assert a["service_tickets"]["unresolved"] == 1
    assert a["service_tickets"]["by_category"] == {"maintenance": 1}
    assert b["service_tickets"]["unresolved"] == 0
    assert b["service_tickets"]["by_status"]["resolved"] == 1
    assert a["pending_local_events"]["guest_case_events"] == 2
    assert b["pending_local_events"]["guest_case_events"] == 3
    assert a["pending_local_events"]["ticket_events"] == 1
    assert b["pending_local_events"]["ticket_events"] == 4

    assert read(client, "demo-hotel-two", "local-one").status_code == 401
    assert read(client, "demo-hotel", "local-two").status_code == 401
    assert read(client, key="").status_code == 401
    for report in (a, b):
        assert "Synthetic Only" not in json.dumps(report)
        assert "guest@example.invalid" not in json.dumps(report)
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 2
        assert con.execute("SELECT COUNT(*) FROM service_tickets").fetchone()[0] == 2


def test_overdue_sample_target_uses_actual_due_date_not_hardcoded_dashboard(rig):
    client, db = rig
    tid = create_ticket(client, "demo-hotel", "local-one", "metrics-overdue-demo")
    with sqlite3.connect(db) as con:
        con.execute(
            "UPDATE service_tickets SET due_at='2000-01-01T00:00:00+00:00' WHERE id=?",
            (tid,),
        )
    a = read(client).json()
    assert a["service_tickets"]["overdue_demo_targets"] == 1
    b = read(client, "demo-hotel-two", "local-two").json()
    assert b["service_tickets"]["overdue_demo_targets"] == 0
