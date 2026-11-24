"""Local launcher startup and repeatable synthetic fixtures; no online services."""
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import local_dev


def test_local_settings_are_private_and_repeatable(tmp_path, monkeypatch):
    monkeypatch.setenv("WF_ENV", "development")
    monkeypatch.delenv("WF_DATABASE_PATH", raising=False)
    location = tmp_path / "state"
    db, keys = local_dev.local_settings(location)
    assert db == location / "worthkind-flow-dev.sqlite3"
    assert set(keys) == {"demo-hotel", "demo-hotel-two"}
    assert keys["demo-hotel"] != keys["demo-hotel-two"]
    assert all(len(key) >= 32 for key in keys.values())
    assert json.loads((location / "staff-keys.json").read_text()) == keys
    if os.name == "posix":
        assert stat.S_IMODE(location.stat().st_mode) == 0o700
        assert stat.S_IMODE((location / "staff-keys.json").stat().st_mode) == 0o600

    # A fresh invocation reuses keys rather than breaking staff access.
    monkeypatch.delenv("WF_DATABASE_PATH")
    second_db, second_keys = local_dev.local_settings(location)
    assert db == second_db and keys == second_keys


def test_local_runner_rejects_online_or_production_context(tmp_path, monkeypatch):
    monkeypatch.setenv("WF_ENV", "production")
    monkeypatch.delenv("WF_DATABASE_PATH", raising=False)
    with pytest.raises(RuntimeError, match="non-development"):
        local_dev.local_settings(tmp_path / "a")

    monkeypatch.setenv("WF_ENV", "development")
    monkeypatch.setenv("WF_DATABASE_PATH", "/tmp/some-other-app.sqlite3")
    with pytest.raises(RuntimeError, match="WF_DATABASE_PATH override"):
        local_dev.local_settings(tmp_path / "b")


def test_symlinked_key_file_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("WF_ENV", "development")
    monkeypatch.delenv("WF_DATABASE_PATH", raising=False)
    state = tmp_path / "state"
    state.mkdir()
    secret = tmp_path / "elsewhere.json"
    secret.write_text("{}")
    (state / "staff-keys.json").symlink_to(secret)
    with pytest.raises(RuntimeError, match="symlinked"):
        local_dev.local_settings(state)


def test_demo_seed_twice_is_idempotent_and_displays_all_case_states(tmp_path, monkeypatch):
    monkeypatch.setenv("WF_ENV", "development")
    monkeypatch.delenv("WF_DATABASE_PATH", raising=False)
    db, _ = local_dev.local_settings(tmp_path / "workspace")
    assert local_dev.seed_synthetic_cases() == 16
    assert local_dev.seed_synthetic_cases() == 0
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 16
        assert dict(conn.execute(
            "SELECT status,COUNT(*) FROM cases GROUP BY status"
        ).fetchall()) == {"queued": 12, "claimed": 2, "responded": 2}
        assert conn.execute(
            "SELECT COUNT(*) FROM cases WHERE contact LIKE '%@guest.invalid'"
        ).fetchone()[0] == 16
        assert conn.execute(
            "SELECT COUNT(*) FROM outbox WHERE processed_at IS NOT NULL"
        ).fetchone()[0] == 0
