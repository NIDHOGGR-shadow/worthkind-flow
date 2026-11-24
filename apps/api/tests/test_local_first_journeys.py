"""End-to-end human-first local journeys; no external APIs, models or payments.

24 parameterized guest -> staff -> guest scenarios use a fresh SQLite DB, synthetic
contacts and FastAPI TestClient. They verify *local dev* behavior, not production.
"""
from itertools import product
from pathlib import Path
import json
import sqlite3
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


@pytest.fixture
def local_client(tmp_path, monkeypatch):
    location = tmp_path / "local-first.sqlite3"
    monkeypatch.setenv("WF_DATABASE_PATH", str(location))
    monkeypatch.setenv(
        "WF_DEV_STAFF_KEYS_JSON",
        json.dumps({"demo-hotel": "synthetic-hotel-a-key", "demo-hotel-two": "synthetic-hotel-b-key"}),
    )
    with TestClient(main.app) as client:
        yield client, location


# Three independent variants for each of the eight service types.
# 24 successful complete no-AI guest -> staff -> guest journeys.
JOURNEYS = [
    (slug, kind, variant)
    for slug, kind, variant in product(
        ("demo-hotel", "demo-hotel-two"),
        ("booking", "food", "events", "human", "careers", "supplier", "support", "general"),
        ("direct", "repeat", "late")
    )
    if (slug == "demo-hotel" and variant != "late")
    or (slug == "demo-hotel-two" and variant == "late")
]
assert len(JOURNEYS) == 24


@pytest.mark.parametrize("slug,kind,variant", JOURNEYS)
def test_local_full_human_first_journey(local_client, slug, kind, variant):
    client, location = local_client
    own_key = "synthetic-hotel-a-key" if slug == "demo-hotel" else "synthetic-hotel-b-key"
    wrong_key = "synthetic-hotel-b-key" if slug == "demo-hotel" else "synthetic-hotel-a-key"
    other_slug = "demo-hotel-two" if slug == "demo-hotel" else "demo-hotel"
    request_key = f"journey-{slug}-{kind}-{variant}-01"
    receipt = "Synthetic-Receipt-" + "A" * 45
    payload = {
        "request_key": request_key, "receipt_token": receipt,
        "kind": kind, "name": "Synthetic Visitor",
        "contact": "guest@example.invalid",
        "details": f"Please contact reception about {kind} using only the direct guest form.",
    }

    public = client.get(f"/api/properties/{slug}")
    assert public.status_code == 200
    assert public.json()["ai_optional"] is True
    assert public.json()["live_payment"] is False
    assert public.json()["live_availability"] is False

    created = client.post(f"/api/properties/{slug}/enquiries", json=payload)
    assert created.status_code == 201
    assert created.json()["duplicate"] is False
    assert "No booking" in created.json()["message"]
    assert created.json()["receipt_token"] == receipt
    case_id = created.json()["case_id"]

    duplicate = client.post(f"/api/properties/{slug}/enquiries", json=payload)
    assert duplicate.status_code == 201
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["case_id"] == case_id

    guest_url = f"/api/properties/{slug}/enquiries/{case_id}"
    assert client.get(guest_url).status_code == 404
    assert client.get(guest_url, headers={"X-Receipt-Token": "wrong"}).status_code == 404
    assert client.get(
        f"/api/properties/{other_slug}/enquiries/{case_id}",
        headers={"X-Receipt-Token": receipt},
    ).status_code == 404

    staff_queue = f"/api/properties/{slug}/staff/enquiries"
    assert client.get(staff_queue, headers={"X-Staff-Key": wrong_key}).status_code == 401
    authorized = client.get(staff_queue, headers={"X-Staff-Key": own_key})
    assert authorized.status_code == 200
    assert [case["id"] for case in authorized.json()["cases"]] == [case_id]

    case_url = staff_queue + "/" + case_id
    assert client.post(case_url + "/claim", headers={"X-Staff-Key": wrong_key}).status_code == 401
    claimed = client.post(case_url + "/claim", headers={"X-Staff-Key": own_key})
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "claimed"
    assert client.post(case_url + "/claim", headers={"X-Staff-Key": own_key}).status_code == 409
    assert client.get(guest_url, headers={"X-Receipt-Token": receipt}).json()["status"] == "claimed"

    reply = f"Synthetic hotel reception acknowledges {kind}; no real service has been completed."
    responded = client.post(
        case_url + "/respond",
        json={"message": reply},
        headers={"X-Staff-Key": own_key},
    )
    assert responded.status_code == 200
    assert client.post(
        case_url + "/respond", json={"message": "Repeat not accepted"}, headers={"X-Staff-Key": own_key},
    ).status_code == 409

    guest = client.get(guest_url, headers={"X-Receipt-Token": receipt})
    assert guest.status_code == 200
    assert guest.json()["status"] == "responded"
    assert guest.json()["staff_reply"] == reply
    assert guest.headers["Cache-Control"] == "no-store"

    with sqlite3.connect(location) as conn:
        audit = conn.execute(
            "SELECT action FROM audit WHERE case_id=? ORDER BY rowid", (case_id,),
        ).fetchall()
        outbox = conn.execute(
            "SELECT event_type,processed_at FROM outbox WHERE case_id=? ORDER BY rowid", (case_id,),
        ).fetchall()
    assert [row[0] for row in audit] == ["case_created", "case_claimed", "case_responded"]
    assert [row[0] for row in outbox] == [row[0] for row in audit]
    assert all(row[1] is None for row in outbox)  # Not delivered by any provider.


def test_local_no_ai_fallback_does_not_call_provider(local_client, monkeypatch):
    client, _ = local_client
    # The only available P0 router is deterministic; an unknown request must
    # explicitly offer human service rather than fake a hotel answer.
    unseen = client.post(
        "/api/properties/demo-hotel/information",
        json={"question": "What is your guaranteed room rate today?"},
    )
    # Booking keywords may match the approved *synthetic* booking disclaimer,
    # never a live rate or availability.
    assert unseen.status_code == 200
    assert unseen.json().get("ai_model_invoked") is False
    assert "No room has been reserved" in unseen.json()["answer"]
    unknown = client.post(
        "/api/properties/demo-hotel/information",
        json={"question": "Is your rooftop sauna open at midnight?"},
    )
    assert unknown.json()["status"] == "unknown"
    assert unknown.json()["next_action"] == "human_enquiry"


def test_local_wrong_property_cannot_modify_existing_case(local_client):
    client, location = local_client
    created = client.post("/api/properties/demo-hotel/enquiries", json={
        "request_key": "attack-test-reference-key", "receipt_token": "G"*40,
        "kind": "human", "name": "Synthetic Visitor",
        "contact": "guest@example.invalid", "details": "I need help with the room.",
    }).json()
    case_id = created["case_id"]
    response = client.post(
        f"/api/properties/demo-hotel-two/staff/enquiries/{case_id}/claim",
        headers={"X-Staff-Key": "synthetic-hotel-b-key"},
    )
    assert response.status_code == 409
    with sqlite3.connect(location) as conn:
        assert conn.execute("SELECT status FROM cases WHERE id=?", (case_id,)).fetchone()[0] == "queued"
        assert conn.execute("SELECT COUNT(*) FROM audit WHERE case_id=?", (case_id,)).fetchone()[0] == 1
