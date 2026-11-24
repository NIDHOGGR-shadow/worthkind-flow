"""Consent, tenant-like property dedupe, withdrawal, privacy and abuse tests."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("WF_WAITLIST_ENV", "development")  # explicit dev opt-in for test import
from api import app


@pytest.fixture
def rig(tmp_path, monkeypatch):
    database = tmp_path / "isolated.sqlite3"
    monkeypatch.setenv("WF_WAITLIST_DB", str(database))
    with TestClient(app) as client:
        yield client, database


def payload(hotel="Hotel Example", email="operator@example.invalid", updates=True, marketing=False):
    return {
        "hotel_name": hotel,
        "area": "Ikeja, Lagos",
        "hotel_address": "123 Example Street, Ikeja",
        "rooms_reported": 30,
        "representative": "Example Manager",
        "representative_role": "general_manager",
        "email": email,
        "workflow_challenge": "lost_enquiries",
        "consent_early_access": updates,
        "consent_marketing": marketing,
    }


def test_preview_only_health_and_security_headers(rig):
    c, _ = rig
    health = c.get("/health")
    assert health.json() == {"status": "preview", "signup_live": False, "pilot_partners": 0}
    assert health.headers["cache-control"] == "no-store"
    assert health.headers["referrer-policy"] == "no-referrer"
    assert health.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in health.headers["content-security-policy"]
    assert "PRIVATE DEVELOPMENT PREVIEW" in c.get("/").text
    assert "privacy" in c.get("/privacy").text.lower()
    assert c.get("/api/early-access").status_code == 405


def test_explicit_consent_and_separate_optional_marketing(rig):
    c, db = rig
    assert c.post("/api/early-access", json=payload(updates=False)).status_code == 422
    assert c.post("/api/early-access", json={k:v for k,v in payload().items() if k != "consent_early_access"}).status_code == 422
    result = c.post("/api/early-access", json=payload())
    assert result.status_code == 201
    data = result.json()
    assert data["qualified_waitlist"] is False
    assert data["status"] == "pending_verification"
    assert len(data["withdraw_token"]) >= 32
    with sqlite3.connect(db) as con:
        record = con.execute("SELECT status,update_opt_in,marketing_opt_in,notice_version FROM applications").fetchone()
        assert record[0:3] == ("pending_verification",1,0)
        assert record[3] == "wf-waitlist-2026-11-17-v1"
        assert con.execute("SELECT COUNT(*) FROM consent_events").fetchone()[0] == 1


def test_duplicate_hotel_contact_rejected_and_other_property_allowed(rig):
    c, db = rig
    first = c.post("/api/early-access", json=payload())
    assert first.status_code == 201
    assert c.post("/api/early-access", json=payload(hotel=" HOTEL EXAMPLE ")).status_code == 409
    assert c.post("/api/early-access", json=payload(hotel="Different Property")).status_code == 201
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 2


def test_opt_out_revokes_both_consents_without_enumerating(rig):
    c, db = rig
    first = c.post("/api/early-access", json=payload(marketing=True))
    token = first.json()["withdraw_token"]
    assert c.post("/api/early-access/withdraw", json={"token": "W"*43}).status_code == 202
    assert c.post("/api/early-access/withdraw", json={"token": token}).status_code == 202
    assert c.post("/api/early-access/withdraw", json={"token": token}).status_code == 202
    with sqlite3.connect(db) as con:
        record = con.execute("SELECT status,update_opt_in,marketing_opt_in FROM applications").fetchone()
        assert record == ("withdrawn",0,0)
        events = [r[0] for r in con.execute("SELECT action FROM consent_events ORDER BY rowid")]
        assert events == ["explicit_early_access_opt_in", "withdrawn"]


def test_no_public_list_of_contacts_or_admin(rig):
    c, db = rig
    assert c.post("/api/early-access", json=payload()).status_code == 201
    for url in ("/api/early-access/all", "/api/early-access/metrics", "/admin", "/openapi.json"):
        assert c.get(url).status_code == 404
    assert "operator@example.invalid" not in c.get("/").text
    assert "operator@example.invalid" not in c.get("/privacy").text


def test_wrong_inputs_and_rate_limit(rig):
    c, db = rig
    invalid = payload()
    invalid["email"] = "not-an-email"
    assert c.post("/api/early-access", json=invalid).status_code == 422
    for i in range(12):
        assert c.post("/api/early-access", json=payload(hotel=f"Hotel Sample {i}")).status_code == 201
    assert c.post("/api/early-access", json=payload(hotel="Another Hotel Extra")).status_code == 429
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 12


def test_production_import_refuses_to_start(tmp_path):
    env = dict(os.environ)
    env["WF_WAITLIST_ENV"] = "production"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run([sys.executable, "-c", "import api"],env=env,check=False,capture_output=True,text=True,timeout=10)
    assert result.returncode != 0
    assert "blocks production deployment" in result.stderr



def test_unset_environment_refuses_to_start(tmp_path):
    env = dict(os.environ)
    env.pop("WF_WAITLIST_ENV", None)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run([sys.executable, "-c", "import api"],env=env,check=False,capture_output=True,text=True,timeout=10)
    assert result.returncode != 0
    assert "blocks production deployment" in result.stderr
