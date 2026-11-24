import json
import os
import secrets
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WF_DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("WF_DEV_STAFF_KEYS_JSON", json.dumps({"demo-hotel": "staff-key-one", "demo-hotel-two": "staff-key-two"}))
    with TestClient(app) as c:
        yield c


def test_health_and_honest_booking_capabilities(client):
    assert client.get("/health").json()["live_bookings"] is False
    data = client.get("/api/properties/demo-hotel/booking-capabilities").json()
    assert data["confirmed_reservations"] is False
    assert data["payments"] is False


@pytest.mark.parametrize("text,intent", [
    ("I need a human", "human"),
    ("There is a fire", "urgent"),
    ("Want a room", "booking"),
    ("I want to sell hotel equipment", "supplier"),
    ("I want a job", "careers"),
    ("Please show the menu", "food"),
])
def test_rules_intent_and_bypass(client, text, intent):
    body = client.post("/api/properties/demo-hotel/route", json={"text": text}).json()
    assert body["intent"] == intent
    assert body["ai_model_invoked"] is False
    assert body["verified_action"] is False
    if intent in ("human", "urgent"):
        assert body["next_action"] == "human_bypass"


def submit(client, slug="demo-hotel", key=None, details="I need a room next Friday"):
    return client.post(f"/api/properties/{slug}/enquiries", json={
        "request_key": key or secrets.token_hex(12), "kind": "booking",
        "name": "Example Visitor", "contact": "guest@example.invalid", "details": details,
    })


def test_submission_is_enquiry_not_booking(client):
    r = submit(client)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "queued"
    assert "No booking" in body["message"]
    assert body["receipt_token"]
    hidden = client.get(f"/api/properties/demo-hotel/enquiries/{body['case_id']}")
    assert hidden.status_code == 404
    shown = client.get(f"/api/properties/demo-hotel/enquiries/{body['case_id']}",
                       headers={"X-Receipt-Token": body["receipt_token"]})
    assert shown.status_code == 200


def test_cross_property_access_denied(client):
    r = submit(client).json()
    path = f"/api/properties/demo-hotel-two/enquiries/{r['case_id']}"
    denied = client.get(path, headers={"X-Receipt-Token": r["receipt_token"]})
    assert denied.status_code == 404
    staff = client.get("/api/properties/demo-hotel/staff/enquiries", headers={"X-Staff-Key": "staff-key-two"})
    assert staff.status_code == 401


def test_idempotency_and_conflict(client):
    key = "same-unique-request-101"
    first = submit(client, key=key).json()
    duplicate = submit(client, key=key).json()
    assert first["case_id"] == duplicate["case_id"]
    assert duplicate["duplicate"] is True
    collision = submit(client, key=key, details="A different room request")
    assert collision.status_code == 409


def test_staff_claim_respond_guest_can_read(client):
    new = submit(client).json()
    case_id = new["case_id"]
    base = f"/api/properties/demo-hotel/staff/enquiries/{case_id}"
    assert client.post(base + "/claim").status_code == 401
    claimed = client.post(base + "/claim", headers={"X-Staff-Key": "staff-key-one"})
    assert claimed.status_code == 200
    again = client.post(base + "/claim", headers={"X-Staff-Key": "staff-key-one"})
    assert again.status_code == 409
    answered = client.post(base + "/respond", json={"message": "Reception will call shortly."},
                           headers={"X-Staff-Key": "staff-key-one"})
    assert answered.status_code == 200
    guest = client.get(f"/api/properties/demo-hotel/enquiries/{case_id}",
                       headers={"X-Receipt-Token": new["receipt_token"]})
    assert guest.json()["staff_reply"] == "Reception will call shortly."
    assert guest.json()["status"] == "responded"


def test_unknown_property_rejected(client):
    assert client.get("/api/properties/missing-hotel").status_code == 404
    assert submit(client, slug="missing-hotel").status_code == 404
