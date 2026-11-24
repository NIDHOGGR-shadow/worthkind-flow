"""Reception → service ticket handoff via the real local SQLite API."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


KEYS = {"demo-hotel": "demo-handoff-one", "demo-hotel-two": "demo-handoff-two"}


@pytest.fixture
def rig(tmp_path, monkeypatch):
    db = tmp_path / "handoff.sqlite3"
    monkeypatch.setenv("WF_DATABASE_PATH", str(db))
    monkeypatch.setenv("WF_DEV_STAFF_KEYS_JSON", json.dumps(KEYS))
    with TestClient(main.app) as client:
        yield client, db


def auth(slug="demo-hotel"):
    return {"X-Staff-Key": KEYS[slug]}


def guest_case(client, slug, key):
    resp = client.post(f"/api/properties/{slug}/enquiries", json={
        "request_key": key, "kind": "support", "name": "Synthetic Guest",
        "contact": "synthetic@example.invalid",
        "details": "A synthetic hotel equipment issue needs an internal follow-up",
    })
    assert resp.status_code == 201
    return resp.json()["case_id"]


def linked_ticket(client, slug, case_id, key):
    return client.post(
        f"/api/properties/{slug}/staff/tickets", headers=auth(slug),
        json={
            "request_key": key, "origin_case_id": case_id,
            "category": "maintenance", "priority": "high",
            "subject": "Inspect synthetic room asset",
            "description": "Investigate the local demonstration maintenance fault.",
        },
    )


def list_cases(client, slug="demo-hotel"):
    return client.get(f"/api/properties/{slug}/staff/enquiries", headers=auth(slug))


def test_linked_ticket_visible_in_original_staff_queue_and_tracks_lifecycle(rig):
    client, db = rig
    case_id = guest_case(client, "demo-hotel", "linked-enquiry-0000001")

    queue = list_cases(client)
    assert queue.status_code == 200
    assert queue.json()["cases"][0]["linked_ticket_id"] is None
    assert queue.json()["cases"][0]["linked_ticket_status"] is None
    assert queue.headers["Cache-Control"] == "no-store"

    # Cannot bypass reception ownership to create linked work.
    assert linked_ticket(client, "demo-hotel", case_id, "ticket-linked-000001").status_code == 409
    claim = client.post(
        f"/api/properties/demo-hotel/staff/enquiries/{case_id}/claim",
        headers=auth(),
    )
    assert claim.status_code == 200

    first = linked_ticket(client, "demo-hotel", case_id, "ticket-linked-000001")
    assert first.status_code == 201
    ticket_id = first.json()["ticket_id"]
    repeat = linked_ticket(client, "demo-hotel", case_id, "ticket-linked-000001")
    assert repeat.status_code == 201
    assert repeat.json()["duplicate"] is True
    assert repeat.json()["ticket_id"] == ticket_id

    visible = list_cases(client).json()["cases"][0]
    assert visible["linked_ticket_id"] == ticket_id
    assert visible["linked_ticket_status"] == "open"
    ticket_url = f"/api/properties/demo-hotel/staff/tickets/{ticket_id}"
    assert client.post(ticket_url + "/claim", headers=auth()).status_code == 200
    assert client.post(ticket_url + "/start", headers=auth()).status_code == 200
    assert client.post(ticket_url + "/resolve", headers=auth(), json={
        "summary": "Synthetic maintenance issue marked resolved in local SQLite.",
    }).status_code == 200
    assert list_cases(client).json()["cases"][0]["linked_ticket_status"] == "resolved"

    with sqlite3.connect(db) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM service_tickets WHERE origin_case_id=?",
            (case_id,),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM ticket_history WHERE ticket_id=?",
            (ticket_id,),
        ).fetchone()[0] == 4


def test_other_property_cannot_see_or_create_linked_work(rig):
    client, _ = rig
    case_a = guest_case(client, "demo-hotel", "hotel-a-guest-00000011")
    guest_case(client, "demo-hotel-two", "hotel-b-guest-000011")
    client.post(
        f"/api/properties/demo-hotel/staff/enquiries/{case_a}/claim", headers=auth(),
    )
    created = linked_ticket(client, "demo-hotel", case_a, "ticket-a-11111111")
    assert created.status_code == 201

    wrong = linked_ticket(client, "demo-hotel-two", case_a, "ticket-b-22222222")
    assert wrong.status_code == 404
    other_cases = list_cases(client, "demo-hotel-two").json()["cases"]
    assert len(other_cases) == 1
    assert other_cases[0]["linked_ticket_id"] is None
    assert client.get(
        "/api/properties/demo-hotel/staff/enquiries",
        headers=auth("demo-hotel-two"),
    ).status_code == 401


def test_only_one_link_per_case_and_no_false_outbound_delivery(rig):
    client, db = rig
    case_id = guest_case(client, "demo-hotel", "linked-case-for-unique-1")
    client.post(
        f"/api/properties/demo-hotel/staff/enquiries/{case_id}/claim",
        headers=auth(),
    )
    first = linked_ticket(client, "demo-hotel", case_id, "unique-link-0000001")
    second = linked_ticket(client, "demo-hotel", case_id, "unique-link-0000002")
    assert first.status_code == 201
    assert second.status_code == 409
    with sqlite3.connect(db) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM service_tickets WHERE origin_case_id=?",
            (case_id,),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM ticket_outbox WHERE processed_at IS NULL",
        ).fetchone()[0] == 1
