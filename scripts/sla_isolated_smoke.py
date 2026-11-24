"""Real local FastAPI + SQLite contract smoke test for the SLA attention endpoint.

No hosted DB, production tenant, real hotel, email, SMS or payment.
This is a focused contract test, not the full Worthkind app/browser suite.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys
import tempfile

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps' / 'api'))
from sla import install_sla_routes


def run_smoke():
    with tempfile.TemporaryDirectory(prefix='worthkind-sla-local-') as directory:
        path = Path(directory) / 'attention.sqlite3'
        with sqlite3.connect(path) as conn:
            conn.execute('CREATE TABLE service_tickets(id TEXT PRIMARY KEY,property_id TEXT,category TEXT,priority TEXT,subject TEXT,status TEXT,due_at TEXT,origin_case_id TEXT)')
            now = datetime.now(timezone.utc)
            sample = (
                ('old', 'hotel-a', now - timedelta(hours=2), 'open'),
                ('soon', 'hotel-a', now + timedelta(minutes=30), 'assigned'),
                ('far', 'hotel-a', now + timedelta(hours=5), 'open'),
                ('resolved', 'hotel-a', now - timedelta(days=1), 'resolved'),
                ('other', 'hotel-b', now - timedelta(hours=1), 'open'),
            )
            for code, hotel, due, status in sample:
                conn.execute('INSERT INTO service_tickets VALUES(?,?,?,?,?,?,?,?)',
                    (code, hotel, 'maintenance', 'high', 'Synthetic ' + code, status, due.isoformat(), None))
            conn.execute('INSERT INTO service_tickets VALUES(?,?,?,?,?,?,?,?)',
                ('bad', 'hotel-a', 'maintenance', 'low', 'Synthetic invalid due', 'open', 'bad-date', None))

        @contextmanager
        def database():
            with sqlite3.connect(path) as conn:
                conn.row_factory = sqlite3.Row
                yield conn

        def property_id(conn, slug):
            if slug not in ('hotel-a', 'hotel-b'):
                raise HTTPException(404, 'Unknown local test hotel')
            return slug

        def require_staff(slug, key):
            if key != {'hotel-a': 'local-test-key-a', 'hotel-b': 'local-test-key-b'}.get(slug):
                raise HTTPException(401, 'Test credential denied')

        app = FastAPI()
        install_sla_routes(app, database, property_id, require_staff)
        with TestClient(app) as client:
            url = '/api/properties/hotel-a/staff/operations/attention'
            key = {'X-Staff-Key': 'local-test-key-a'}
            response = client.get(url, headers=key)
            assert response.status_code == 200, response.text
            result = response.json()
            assert result['counts'] == {'overdue': 1, 'due_soon': 1, 'invalid_due': 1, 'on_track': 1}
            assert [item['attention'] for item in result['items']] == ['overdue', 'invalid_due', 'due_soon']
            assert result['alerts_sent'] == 0 and result['provider_connected'] is False
            assert client.get(url, headers={'X-Staff-Key': 'local-test-key-b'}).status_code == 401
            assert client.get('/api/properties/hotel-b/staff/operations/attention',
                headers={'X-Staff-Key': 'local-test-key-b'}).json()['actionable_total'] == 1
            short = client.get(url + '?limit=1', headers=key).json()
            assert short['truncated'] is True and short['actionable_total'] == 3 and len(short['items']) == 1

    print('PASS: 7 isolated FastAPI/SQLite SLA contract assertions; no provider calls')


if __name__ == '__main__':
    run_smoke()
