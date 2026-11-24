"""Synthetic SQLite delivery-contract verification (no real providers)."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os
import sqlite3
from uuid import uuid4

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from delivery_contract import (
    create_delivery_tables, install_delivery_routes, simulate_attempt,
    simulate_receipt, MAX_ATTEMPTS,
)
NOW = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("WF_ENV", "development")
    db_file = tmp_path / "delivery.sqlite3"
    def connect():
        conn = sqlite3.connect(db_file, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE properties(id TEXT PRIMARY KEY,slug TEXT UNIQUE NOT NULL);
        CREATE TABLE cases(id TEXT PRIMARY KEY,property_id TEXT NOT NULL);
        CREATE TABLE outbox(id TEXT PRIMARY KEY,property_id TEXT NOT NULL REFERENCES properties(id),
           case_id TEXT NOT NULL REFERENCES cases(id),event_type TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,
           processed_at TEXT,attempts INTEGER NOT NULL DEFAULT 0);
        INSERT INTO properties VALUES('first','one'),('second','two');
        INSERT INTO cases VALUES('case-1','first'),('case-2','second');
        INSERT INTO outbox(id,property_id,case_id,event_type) VALUES
           ('event-1','first','case-1','case_created'),('event-2','second','case-2','case_created');
        """)
        create_delivery_tables(conn)
    return connect


def simulate(db, event, outcome, now=NOW):
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        return simulate_attempt(conn, event, outcome, now=now)


def receipt(db, event, receipt_id, outcome='delivered', now=NOW):
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        return simulate_receipt(conn, event, receipt_id, outcome, now)


def test_accepted_is_not_delivered_and_fake_receipt_is_explicit(db):
    ack = simulate(db, 'event-1', 'accepted')
    assert ack['state'] == 'accepted' and ack['ack_ref'] == 'mock:event-1'
    assert ack['attempts'] == 1
    with db() as conn:
        assert conn.execute('SELECT processed_at FROM outbox WHERE id=?', ('event-1',)).fetchone()[0]
    ack2 = simulate(db, 'event-1', 'accepted')
    assert ack2['attempts'] == 1
    delivered = receipt(db, 'event-1', 'fake-receipt-a')
    assert delivered['state'] == 'delivered'
    assert receipt(db, 'event-1', 'fake-receipt-a')['state'] == 'delivered'
    with pytest.raises(ValueError, match='Conflicting'):
        receipt(db, 'event-1', 'fake-receipt-a', 'undeliverable')
    assert simulate(db, 'event-1', 'accepted')['state'] == 'delivered'
    with db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM dev_provider_attempts WHERE event_id="event-1"').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM dev_provider_receipts WHERE event_id="event-1"').fetchone()[0] == 1


def test_backoff_is_enforced_and_exhausts_to_dead_letter(db):
    first = simulate(db, 'event-1', 'transient_error')
    assert first['state'] == 'retry_due' and first['retry_after'] == '2026-11-20T12:01:00Z'
    early = simulate(db, 'event-1', 'accepted', NOW + timedelta(seconds=59))
    assert early['state'] == 'retry_due' and early['attempts'] == 1
    second = simulate(db, 'event-1', 'transient_error', NOW + timedelta(seconds=60))
    assert second['retry_after'] == '2026-11-20T12:03:00Z' and second['attempts'] == 2
    third = simulate(db, 'event-1', 'transient_error', NOW + timedelta(seconds=180))
    assert third['state'] == 'dead_letter' and third['last_error_code'] == 'MOCK_MAX_ATTEMPTS'
    assert third['attempts'] == MAX_ATTEMPTS
    assert simulate(db,'event-1','accepted',NOW + timedelta(days=1))['state'] == 'dead_letter'
    with db() as conn:
        assert conn.execute('SELECT processed_at FROM outbox WHERE id="event-1"').fetchone()[0] is None
        assert conn.execute('SELECT COUNT(*) FROM dev_provider_attempts WHERE event_id="event-1"').fetchone()[0] == 3


def test_permanent_error_never_marks_processed(db):
    state = simulate(db,'event-1','permanent_error')
    assert state['state'] == 'dead_letter' and state['last_error_code'] == 'MOCK_PERMANENT'
    with db() as conn:
        assert conn.execute('SELECT processed_at FROM outbox WHERE id="event-1"').fetchone()[0] is None


def test_receipt_before_acceptance_refused_and_undeliverable_terminal(db):
    with pytest.raises(ValueError, match='acceptance'):
        receipt(db,'event-1','receipt-a')
    simulate(db,'event-1','accepted')
    terminal = receipt(db,'event-1','receipt-failed','undeliverable')
    assert terminal['state'] == 'dead_letter' and terminal['last_error_code'] == 'MOCK_UNDELIVERABLE'
    with pytest.raises(ValueError, match='acceptance'):
        receipt(db,'event-1','receipt-other')


def test_invalid_outcomes_and_time_rejected(db):
    with db() as conn:
        with pytest.raises(ValueError, match='Unsupported'):
            simulate_attempt(conn,'event-1','real_sent')
        with pytest.raises(ValueError, match='offset-aware'):
            simulate_attempt(conn,'event-1','accepted',datetime(2026,11,20))
        with pytest.raises(ValueError, match='does not exist'):
            simulate_attempt(conn,'unknown','accepted')
    with pytest.raises(ValueError, match='Invalid'):
        receipt(db,'event-1','not a valid id')
    # A fake receipt is a synthetic provider identifier, never a free-form
    # Unicode string or a transport object which could crash the worker.
    for bad_id in (123, None, True, 'é', '层', 'fake-receipt-🙂', 'bad name', 'x'*101):
        with pytest.raises(ValueError, match='Invalid synthetic receipt'):
            receipt(db,'event-1',bad_id)
    # The strict format still allows normal ASCII provider receipt IDs.
    simulate(db,'event-1','accepted')
    assert receipt(db,'event-1','ASCII_123-xyz')['state']=='delivered'



def test_crash_rolls_back_state_and_outbox_together(db):
    with pytest.raises(RuntimeError, match='crash'):
        with db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            simulate_attempt(conn,'event-1','accepted',NOW)
            raise RuntimeError('crash before commit')
    with db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM dev_provider_delivery_state').fetchone()[0] == 0
        assert conn.execute('SELECT processed_at FROM outbox WHERE id="event-1"').fetchone()[0] is None


def test_previously_consumed_outbox_event_refused(db):
    with db() as conn:
        conn.execute("UPDATE outbox SET processed_at=CURRENT_TIMESTAMP WHERE id='event-1'")
    with pytest.raises(ValueError, match='already consumed'):
        simulate(db,'event-1','accepted')


def test_property_scoped_read_endpoint_and_redaction(db):
    app = FastAPI()
    @contextmanager
    def database():
        with db() as conn:
            yield conn
    def pid(conn, slug):
        row = conn.execute('SELECT id FROM properties WHERE slug=?',(slug,)).fetchone()
        if not row: raise HTTPException(404, 'Unknown property')
        return row['id']
    def staff(slug, key):
        if not key or key != {'one':'key-one','two':'key-two'}.get(slug):
            raise HTTPException(401, 'Unauthorized')
    install_delivery_routes(app,database,pid,staff)
    simulate(db,'event-1','accepted')
    receipt(db,'event-1','receipt-good')
    client=TestClient(app)
    url='/api/properties/one/staff/operations/delivery'
    assert client.get(url).status_code == 401
    assert client.get(url,headers={'X-Staff-Key':'key-two'}).status_code == 401
    first=client.get(url,headers={'X-Staff-Key':'key-one'})
    assert first.status_code == 200
    data=first.json()
    assert data['counts']=={'delivered':1}
    assert data['events'][0]['event_id']=='event-1'
    assert data['real_messages_sent']==0 and data['real_delivery_verified'] is False
    assert 'case_id' not in data['events'][0] and 'contact' not in str(data)
    second=client.get('/api/properties/two/staff/operations/delivery',headers={'X-Staff-Key':'key-two'})
    assert second.json()['counts']=={'queued':1} and second.json()['events'][0]['event_id']=='event-2'
    assert client.get(url+'?limit=101',headers={'X-Staff-Key':'key-one'}).status_code==422


def test_case_and_whitespace_variants_of_production_fail_before_db_write(db, monkeypatch):
    for value in ('PRODUCTION', 'Production', ' production ', '  pRoDuCtIoN  '):
        monkeypatch.setenv('WF_ENV', value)
        with pytest.raises(RuntimeError,match='production'):
            simulate(db,'event-1','accepted')
        with db() as conn:
            with pytest.raises(RuntimeError,match='production'):
                create_delivery_tables(conn)
            assert conn.execute('SELECT COUNT(*) FROM dev_provider_attempts').fetchone()[0] == 0

def test_production_guard(db, monkeypatch):
    monkeypatch.setenv('WF_ENV','production')
    with pytest.raises(RuntimeError,match='production'):
        simulate(db,'event-1','accepted')
    with db() as conn:
        with pytest.raises(RuntimeError,match='production'):
            create_delivery_tables(conn)
