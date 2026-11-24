"""SQLite storage boundary contract; real local DB, no Supabase requirement."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage_sqlite import database


@pytest.fixture
def configured(tmp_path, monkeypatch):
    path=tmp_path / "web-app.sqlite3"
    monkeypatch.setenv("WF_DATABASE_PATH",str(path))
    return path


def test_connection_is_row_addressable_and_fk_protected(configured):
    with database() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 10000
        conn.execute("CREATE TABLE parent(id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE child(parent_id TEXT REFERENCES parent(id))")
        conn.execute("INSERT INTO parent(id) VALUES ('valid')")
        conn.execute("INSERT INTO child(parent_id) VALUES ('valid')")
        item=conn.execute("SELECT parent_id FROM child").fetchone()
        assert item["parent_id"]=="valid"


def test_success_commits_between_independent_http_style_requests(configured):
    with database() as conn:
        conn.execute("CREATE TABLE events(id INTEGER PRIMARY KEY, state TEXT)")
        conn.execute("INSERT INTO events(state) VALUES('queued')")
    with database() as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
        conn.execute("UPDATE events SET state='claimed' WHERE state='queued'")
    with database() as conn:
        assert conn.execute("SELECT state FROM events").fetchone()["state"] == "claimed"


def test_failed_domain_audit_write_rolls_back_both_rows(configured):
    with database() as conn:
        conn.execute("CREATE TABLE domain(id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE audit(domain_id TEXT REFERENCES domain(id), action TEXT)")
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        with database() as conn:
            conn.execute("INSERT INTO domain(id) VALUES('case-1')")
            conn.execute("INSERT INTO audit(domain_id,action) VALUES('case-1','created')")
            raise RuntimeError("synthetic audit failure")
    with database() as conn:
        assert conn.execute("SELECT COUNT(*) FROM domain").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 0


def test_env_path_is_per_request_and_empty_configuration_refused(configured, monkeypatch, tmp_path):
    other=tmp_path / "other.sqlite3"
    with database() as conn:
        conn.execute("CREATE TABLE one(id INTEGER)")
    monkeypatch.setenv("WF_DATABASE_PATH",str(other))
    with database() as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='one'").fetchone() is None
    monkeypatch.setenv("WF_DATABASE_PATH","")
    with pytest.raises(RuntimeError,match="path is empty"):
        with database():
            pass
