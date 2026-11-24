"""Local operations overview: source accuracy, property isolation and absence of fake KPIs."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


@pytest.fixture
def rig(tmp_path, monkeypatch):
    location = tmp_path / "overview.sqlite3"
    monkeypatch.setenv("WF_DATABASE_PATH", str(location))
    monkeypatch.setenv(
        "WF_DEV_STAFF_KEYS_JSON",
        json.dumps({"demo-hotel": "local-dev-hotel-a", "demo-hotel-two": "local-dev-hotel-b"}),
    )
    with TestClient(main.app) as client:
        yield client, location


def staff(slug="demo-hotel"):
    return {"X-Staff-Key": {
        "demo-hotel": "local-dev-hotel-a",
        "demo-hotel-two": "local-dev-hotel-b",
    }[slug]}


def overview(client, slug="demo-hotel", key=None):
    return client.get(
        f"/api/properties/{slug}/staff/overview",
        headers=key if key is not None else staff(slug),
    )


def new_case(client, slug="demo-hotel", request_key="dashboard-case-one"):
    response = client.post(f"/api/properties/{slug}/enquiries", json={
        "request_key": request_key, "receipt_token": "R" * 43,
        "kind": "human", "name": "Synthetic User", "contact": "nobody@example.invalid",
        "details": "I need to speak with reception about an enquiry",
    })
    assert response.status_code == 201
    return response.json()["case_id"]


def new_ticket(client, slug="demo-hotel", request_key="dashboard-ticket-one", priority="normal"):
    response = client.post(f"/api/properties/{slug}/staff/tickets", headers=staff(slug), json={
        "request_key": request_key,
        "category": "it", "priority": priority,
        "subject": "Synthetic reception router fault",
        "description": "The mock front desk router does not respond.",
    })
    assert response.status_code == 201
    return response.json()["ticket_id"]


def test_empty_overview_is_real_zero_not_fake_kpis(rig):
    client, _ = rig
    r = overview(client)
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "no-store"
    data = r.json()
    assert data["source"] == "property_scoped_local_sqlite"
    assert data["data_is_synthetic"] is True
    assert data["production_ready"] is False
    assert data["cases"]["total"] == 0
    assert data["tickets"]["total"] == 0
    assert data["local_outbox"]["pending_total"] == 0
    assert data["cases"]["recent"] == []
    assert data["tickets"]["recent"] == []
    assert all(value is None for value in data["unsupported"].values())


def test_case_and_ticket_counts_are_derived_from_sqlite(rig):
    client, location = rig
    case = new_case(client)
    t1 = new_ticket(client)
    t2 = new_ticket(client, request_key="dashboard-ticket-two", priority="high")

    assert client.post(
        f"/api/properties/demo-hotel/staff/enquiries/{case}/claim",
        headers=staff(),
    ).status_code == 200
    assert client.post(
        f"/api/properties/demo-hotel/staff/tickets/{t1}/claim",
        headers=staff(),
    ).status_code == 200
    assert client.post(
        f"/api/properties/demo-hotel/staff/tickets/{t1}/start",
        headers=staff(),
    ).status_code == 200
    assert client.post(
        f"/api/properties/demo-hotel/staff/tickets/{t1}/resolve",
        headers=staff(), json={"summary": "Synthetic router restored after a local check"},
    ).status_code == 200

    with sqlite3.connect(location) as conn:
        conn.execute(
            "UPDATE service_tickets SET due_at='2000-01-01T00:00:00+00:00' WHERE id=?",
            (t2,),
        )
        expected_case_events = conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
        expected_ticket_events = conn.execute("SELECT COUNT(*) FROM ticket_outbox").fetchone()[0]
    data = overview(client).json()
    assert data["cases"]["total"] == 1
    assert data["cases"]["by_status"]["queued"] == 0
    assert data["cases"]["by_status"]["claimed"] == 1
    assert data["tickets"]["total"] == 2
    assert data["tickets"]["by_status"]["open"] == 1
    assert data["tickets"]["by_status"]["resolved"] == 1
    assert data["tickets"]["unresolved"] == 1
    assert data["tickets"]["overdue"] == 1
    assert data["local_outbox"]["pending_case_events"] == expected_case_events
    assert data["local_outbox"]["pending_ticket_events"] == expected_ticket_events
    assert data["local_outbox"]["pending_total"] == expected_case_events + expected_ticket_events
    assert data["local_outbox"]["external_notifications_sent"] is None
    assert all("customer_name" not in row and "contact" not in row
               for row in data["cases"]["recent"])
    assert all("description" not in row and "subject" not in row
               for row in data["tickets"]["recent"])


def test_hotel_a_and_b_have_disjoint_overviews(rig):
    client, _ = rig
    new_case(client, "demo-hotel", "case-a-100001")
    new_case(client, "demo-hotel-two", "case-b-100001")
    new_case(client, "demo-hotel-two", "case-b-100002")
    new_ticket(client, "demo-hotel-two", "ticket-b-100001")
    a = overview(client).json()
    b = overview(client, "demo-hotel-two").json()
    assert a["property"]["slug"] == "demo-hotel"
    assert b["property"]["slug"] == "demo-hotel-two"
    assert a["cases"]["total"] == 1
    assert b["cases"]["total"] == 2
    assert a["tickets"]["total"] == 0
    assert b["tickets"]["total"] == 1
    assert a["local_outbox"]["pending_total"] == 1
    assert b["local_outbox"]["pending_total"] == 3
    assert {row["id"] for row in a["cases"]["recent"]}.isdisjoint(
        {row["id"] for row in b["cases"]["recent"]}
    )


def test_missing_wrong_and_cross_property_staff_keys_fail_closed(rig):
    client, _ = rig
    assert client.get("/api/properties/demo-hotel/staff/overview").status_code == 401
    assert overview(client, key=staff("demo-hotel-two")).status_code == 401
    assert overview(client, "demo-hotel-two", key=staff("demo-hotel")).status_code == 401
    assert overview(client, "missing-hotel", key={"X-Staff-Key": "unknown"}).status_code == 401
    denied = overview(client, key=staff("demo-hotel-two"))
    assert denied.headers["Cache-Control"] == "no-store"
    assert "cases" not in denied.json()


def test_pending_local_events_are_not_delivery_proof(rig):
    client, location = rig
    new_case(client)
    first = overview(client).json()
    assert first["local_outbox"]["pending_total"] == 1
    with sqlite3.connect(location) as conn:
        conn.execute(
            "UPDATE outbox SET processed_at='2026-11-19 18:00:00' WHERE property_id=?",
            ("demo-hotel",),
        )
    # Even a locally simulated process mark is not a provider delivery.
    second = overview(client).json()
    assert second["local_outbox"]["pending_total"] == 0
    assert second["local_outbox"]["delivery_authority"] == "none_local_simulation_only"
    assert second["local_outbox"]["external_notifications_sent"] is None
