"""P0 adversarial tests: tenant scoping, idempotent receipt recovery, atomic audit/outbox."""
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
    db_path = tmp_path / "worthkind-flow.sqlite3"
    monkeypatch.setenv("WF_DATABASE_PATH", str(db_path))
    monkeypatch.setenv(
        "WF_DEV_STAFF_KEYS_JSON",
        json.dumps({"demo-hotel": "local-staff-one", "demo-hotel-two": "local-staff-two"}),
    )
    with TestClient(main.app) as client:
        yield client, db_path


def request_body(request_key, token=None):
    body = {
        "request_key": request_key,
        "kind": "booking",
        "name": "Synthetic Guest",
        "contact": "test@example.invalid",
        "details": "I am enquiring about a room for Friday",
    }
    if token is not None:
        body["receipt_token"] = token
    return body


def create(client, slug, body):
    return client.post(f"/api/properties/{slug}/enquiries", json=body)


def test_tenant_scoped_public_answers_and_abstention(rig):
    client, db = rig
    first = client.post("/api/properties/demo-hotel/information", json={"question": "What is the hotel called?"})
    second = client.post("/api/properties/demo-hotel-two/information", json={"question": "What is the hotel called?"})
    assert first.status_code == second.status_code == 200
    a, b = first.json(), second.json()
    assert a["status"] == b["status"] == "answered"
    assert a["answer"] != b["answer"]
    assert "Second Demo" not in a["answer"]
    assert a["source"] == b["source"] == "synthetic_demo_fixture"
    unknown = client.post("/api/properties/demo-hotel/information", json={"question": "Is the pool heated?"}).json()
    assert unknown["status"] == "unknown"
    assert unknown["answer"] is None
    assert unknown["next_action"] == "human_enquiry"
    assert unknown["ai_model_invoked"] is False
    assert client.post("/api/properties/nonexistent/information", json={"question": "Name?"}).status_code == 404

    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE public_facts SET approved=0 WHERE property_id=? AND question_key=?", ("demo-hotel", "name"))
    hidden = client.post("/api/properties/demo-hotel/information", json={"question": "What is the hotel name?"}).json()
    assert hidden["status"] == "unknown"
    assert hidden["answer"] is None


def test_authenticated_receipt_retry_and_conflicts(rig):
    client, db = rig
    original_token = "L" * 43  # only possession of original proof allows recovery
    body = request_body("client-enquiry-idem-01234567", token=original_token)
    first = create(client, "demo-hotel", body)
    assert first.status_code == 201
    assert first.json()["receipt_token"] == original_token

    retry = create(client, "demo-hotel", body)
    assert retry.status_code == 201
    assert retry.json()["duplicate"] is True
    assert retry.json()["receipt_token"] == original_token
    assert retry.json()["case_id"] == first.json()["case_id"]

    without_proof = create(client, "demo-hotel", request_body(body["request_key"]))
    assert without_proof.status_code == 201
    assert without_proof.json()["duplicate"] is True
    assert "receipt_token" not in without_proof.json()

    invalid_proof = create(client, "demo-hotel", request_body(body["request_key"], "Q" * 43))
    assert invalid_proof.status_code == 409

    modified = dict(body)
    modified["details"] = "I would like a different date instead"
    assert create(client, "demo-hotel", modified).status_code == 409

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1


def test_atomic_audit_and_outbox_for_each_case_transition(rig):
    client, db = rig
    payload = request_body("transitions-012345678901")
    created = create(client, "demo-hotel", payload).json()
    case = created["case_id"]
    headers = {"X-Staff-Key": "local-staff-one"}
    assert client.post(f"/api/properties/demo-hotel/staff/enquiries/{case}/claim", headers=headers).status_code == 200
    assert client.post(
        f"/api/properties/demo-hotel/staff/enquiries/{case}/respond",
        headers=headers,
        json={"message": "Reception has received your enquiry, not a confirmed reservation."},
    ).status_code == 200

    with sqlite3.connect(db) as conn:
        audit = conn.execute("SELECT action, property_id FROM audit WHERE case_id=? ORDER BY created_at, rowid", (case,)).fetchall()
        outbox = conn.execute("SELECT event_type, property_id, processed_at FROM outbox WHERE case_id=? ORDER BY created_at, rowid", (case,)).fetchall()
    assert [x[0] for x in audit] == ["case_created", "case_claimed", "case_responded"]
    assert [x[0] for x in outbox] == [x[0] for x in audit]
    assert all(x[1] == "demo-hotel" for x in outbox)
    # Delivery is not connected. A queued event is not a sent notification.
    assert all(x[2] is None for x in outbox)


def test_failed_event_write_rolls_back_case(rig, monkeypatch):
    client, db = rig
    original = main.record_event

    def interrupted(*args, **kwargs):
        raise sqlite3.OperationalError("synthetic audit storage failure")

    monkeypatch.setattr(main, "record_event", interrupted)
    with pytest.raises(sqlite3.OperationalError):
        create(client, "demo-hotel", request_body("forced-rollback-0123456789"))
    monkeypatch.setattr(main, "record_event", original)

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 0


def test_unauthorized_case_transition_never_writes_event(rig):
    client, db = rig
    case = create(client, "demo-hotel", request_body("auth-failure-0123456789")).json()["case_id"]
    bad = client.post(f"/api/properties/demo-hotel/staff/enquiries/{case}/claim", headers={"X-Staff-Key": "local-staff-two"})
    assert bad.status_code == 401
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1
        assert conn.execute("SELECT status FROM cases WHERE id=?", (case,)).fetchone()[0] == "queued"


def test_simulated_outbox_is_replay_safe_and_crash_atomic(rig):
    from outbox_worker import pending_outbox_count, simulate_local_delivery

    client, db = rig
    assert create(client, "demo-hotel", request_body("dry-run-101011223344")).status_code == 201
    assert create(client, "demo-hotel-two", request_body("dry-run-204050607080")).status_code == 201
    assert pending_outbox_count() == 2

    # Crash after an event is written but before transaction commit:
    # neither processed flag nor local delivery log may partially persist.
    with pytest.raises(RuntimeError, match="Simulated crash"):
        simulate_local_delivery(fail_after=1)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM dev_delivery_log").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM outbox WHERE processed_at IS NOT NULL").fetchone()[0] == 0

    assert simulate_local_delivery() == 2
    assert simulate_local_delivery() == 0
    assert pending_outbox_count() == 0
    with sqlite3.connect(db) as conn:
        logged = conn.execute("SELECT property_id,event_type FROM dev_delivery_log ORDER BY property_id").fetchall()
        assert logged == [("demo-hotel", "case_created"), ("demo-hotel-two", "case_created")]
        assert conn.execute("SELECT MAX(attempts) FROM outbox").fetchone()[0] == 1


def test_legacy_local_sink_does_not_bypass_provider_retry_or_dead_letter(rig):
    """The old simulated worker must not erase new fake-provider backoff evidence."""
    from datetime import datetime, timedelta, timezone
    from delivery_contract import simulate_attempt
    from outbox_worker import simulate_local_delivery

    client, db = rig
    assert create(client, "demo-hotel", request_body("retry-isolation-00000011")).status_code == 201
    with main.database() as conn:
        event_id = conn.execute("SELECT id FROM outbox ORDER BY rowid DESC LIMIT 1").fetchone()["id"]
        conn.execute("BEGIN IMMEDIATE")
        pending = simulate_attempt(
            conn, event_id, "transient_error",
            now=datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc),
        )
        assert pending["state"] == "retry_due"
    assert simulate_local_delivery() == 0  # Not a real or legacy fake delivery.
    with main.database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        failed = simulate_attempt(
            conn, event_id, "permanent_error",
            now=datetime(2026, 11, 20, 9, 1, tzinfo=timezone.utc),
        )
        assert failed["state"] == "dead_letter"
    assert simulate_local_delivery() == 0
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT processed_at FROM outbox WHERE id=?", (event_id,)).fetchone()[0] is None
        assert conn.execute("SELECT COUNT(*) FROM dev_delivery_log").fetchone()[0] == 0


def test_simulator_rejects_invalid_batch_sizes(rig):
    from outbox_worker import simulate_local_delivery
    with pytest.raises(ValueError):
        simulate_local_delivery(limit=0)
    with pytest.raises(ValueError):
        simulate_local_delivery(limit=501)


def test_python_production_import_fails_closed(tmp_path):
    import subprocess
    import os
    env = dict(os.environ, WF_ENV="production", WF_DATABASE_PATH=str(tmp_path / "prod.sqlite3"))
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run(
        [sys.executable, "-c", "import main"],
        env=env, capture_output=True, text=True, check=False, timeout=10,
    )
    assert result.returncode != 0
    assert "Production blocked" in result.stderr


def test_concurrent_idempotent_submissions_create_exactly_one_case(rig):
    from concurrent.futures import ThreadPoolExecutor

    client, db = rig
    body = request_body("simultaneous-requests-012345", token="R" * 43)
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(lambda _: create(client, "demo-hotel", body), range(4)))
    assert all(response.status_code == 201 for response in responses)
    payloads = [response.json() for response in responses]
    assert len({item["case_id"] for item in payloads}) == 1
    assert all(item["receipt_token"] == "R" * 43 for item in payloads)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1


def test_sensitive_api_responses_disable_http_caching(rig):
    """Receipt-bearing and employee-only API replies must not be cached."""
    client, _ = rig
    token = "S" * 43
    created = create(
        client, "demo-hotel", request_body("cache-policy-012345678901", token=token)
    )
    assert created.status_code == 201
    case_id = created.json()["case_id"]
    guest_path = f"/api/properties/demo-hotel/enquiries/{case_id}"
    checked = (
        created,
        client.get(guest_path, headers={"X-Receipt-Token": token}),
        client.get(guest_path),  # even denied private reads carry no-store
        client.get(
            "/api/properties/demo-hotel/staff/enquiries",
            headers={"X-Staff-Key": "local-staff-one"},
        ),
        client.get("/api/properties/demo-hotel/staff/enquiries"),
    )
    assert [reply.status_code for reply in checked] == [201, 200, 404, 200, 401]
    for reply in checked:
        assert reply.headers["Cache-Control"] == "no-store"
        assert reply.headers["Pragma"] == "no-cache"
