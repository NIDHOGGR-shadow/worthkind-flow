"""Real local SQLite ticket attention API, property access and deadlines."""
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from sla_rules import classify_due


KEYS = {"demo-hotel": "synthetic-attention-one", "demo-hotel-two": "synthetic-attention-two"}


@pytest.fixture
def rig(tmp_path, monkeypatch):
    location = tmp_path / "attention.sqlite3"
    monkeypatch.setenv("WF_DATABASE_PATH", str(location))
    monkeypatch.setenv("WF_DEV_STAFF_KEYS_JSON", json.dumps(KEYS))
    with TestClient(main.app) as client:
        yield client, location


def attention(client, slug="demo-hotel", key=None, suffix=""):
    return client.get(
        f"/api/properties/{slug}/staff/operations/attention{suffix}",
        headers={"X-Staff-Key": key or KEYS[slug]},
    )


def create_ticket(client, slug, unique):
    result = client.post(
        f"/api/properties/{slug}/staff/tickets",
        headers={"X-Staff-Key": KEYS[slug]},
        json={
            "request_key": "attention-" + unique,
            "category": "maintenance", "priority": "high",
            "subject": "Synthetic hotel asset check " + unique,
            "description": "Synthetic internal repair follow-up, not a real service request.",
        },
    )
    assert result.status_code == 201, result.text
    return result.json()["ticket_id"]


def test_sla_classification_is_deterministic_and_never_sends_alerts():
    now = datetime(2026, 11, 20, 16, 0, tzinfo=timezone.utc)
    assert classify_due((now - timedelta(seconds=1)).isoformat(), "open", now) == ("overdue", 1)
    assert classify_due((now + timedelta(minutes=60)).isoformat(), "assigned", now) == ("due_soon", 60)
    assert classify_due((now + timedelta(minutes=61)).isoformat(), "in_progress", now) == ("on_track", 61)
    assert classify_due((now - timedelta(hours=1)).isoformat(), "resolved", now) == ("resolved", None)
    assert classify_due("corrupt", "open", now) == ("invalid_due", None)
    assert classify_due("2026-11-20 16:00:00", "open", now) == ("due_soon", 0)
    with pytest.raises(ValueError):
        classify_due(now.isoformat(), "open", now, soon_minutes=0)


def test_empty_hotel_has_zero_actionable_work_and_no_provider_claim(rig):
    client, _ = rig
    data = attention(client).json()
    assert data["source"] == "local_sqlite_development"
    assert data["property"] == "demo-hotel"
    assert data["counts"] == {
        "overdue": 0, "due_soon": 0, "invalid_due": 0, "on_track": 0
    }
    assert data["actionable_total"] == 0
    assert data["items"] == []
    assert data["alerts_sent"] == 0
    assert data["provider_connected"] is False
    assert attention(client).headers["Cache-Control"] == "no-store"


def test_attention_queue_counts_and_sorting_ignore_resolved_and_other_hotel(rig):
    client, location = rig
    overdue = create_ticket(client, "demo-hotel", "overdue")
    upcoming = create_ticket(client, "demo-hotel", "soon")
    future = create_ticket(client, "demo-hotel", "future")
    malformed = create_ticket(client, "demo-hotel", "invalid")
    resolved = create_ticket(client, "demo-hotel", "resolved")
    different = create_ticket(client, "demo-hotel-two", "other-hotel")
    now = datetime.now(timezone.utc)
    with sqlite3.connect(location) as conn:
        for tid, when in [
            (overdue, now - timedelta(minutes=90)),
            (upcoming, now + timedelta(minutes=20)),
            (future, now + timedelta(hours=5)),
            (different, now - timedelta(days=3)),
        ]:
            conn.execute("UPDATE service_tickets SET due_at=? WHERE id=?", (when.isoformat(), tid))
        conn.execute("UPDATE service_tickets SET due_at='not-a-date' WHERE id=?", (malformed,))
        conn.execute(
            "UPDATE service_tickets SET status='resolved',due_at='2000-01-01' WHERE id=?",
            (resolved,),
        )

    result = attention(client)
    assert result.status_code == 200
    data = result.json()
    assert data["counts"] == {
        "overdue": 1, "due_soon": 1, "invalid_due": 1, "on_track": 1
    }
    assert data["actionable_total"] == 3
    assert [row["attention"] for row in data["items"]] == [
        "overdue", "invalid_due", "due_soon"
    ]
    assert {row["ticket_id"] for row in data["items"]} == {overdue, upcoming, malformed}
    assert different not in json.dumps(data)
    assert resolved not in json.dumps(data)
    assert "synthetic@example.invalid" not in json.dumps(data)
    assert data["alerts_sent"] == 0

    shortened = attention(client, suffix="?limit=1").json()
    assert shortened["truncated"] is True
    assert shortened["actionable_total"] == 3
    assert len(shortened["items"]) == 1
    assert shortened["items"][0]["ticket_id"] == overdue


def test_staff_key_and_cross_property_scope_are_enforced(rig):
    client, _ = rig
    create_ticket(client, "demo-hotel", "tenant-protected")
    url = "/api/properties/demo-hotel/staff/operations/attention"
    denied = client.get(url)
    other = client.get(url, headers={"X-Staff-Key": KEYS["demo-hotel-two"]})
    assert denied.status_code == other.status_code == 401
    assert denied.headers["Cache-Control"] == "no-store"
    assert other.headers["Cache-Control"] == "no-store"
    assert attention(client, "demo-hotel-two").json()["actionable_total"] == 0
    assert client.get(url + "?limit=0", headers={"X-Staff-Key": KEYS["demo-hotel"]}).status_code == 422
