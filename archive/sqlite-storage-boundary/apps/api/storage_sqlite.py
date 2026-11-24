"""SQLite development persistence connection boundary for Worthkind Flow.

Worthkind Flow is a normal web application: browser -> FastAPI -> storage.
This module centralizes only the connection/transaction lifecycle and database
configuration. It does NOT pretend the existing sqlite3 SQL in route handlers
is portable to PostgreSQL already. That query/repository extraction follows
as a separate tested step before any Supabase migration.

The existing WF_ENV=production fail-closed behavior remains in main.py.
"""
from contextlib import contextmanager
import os
import sqlite3


DEFAULT_DEV_DB = "./worthkind-flow-dev.sqlite3"


@contextmanager
def database():
    """Return one fresh SQLite connection with property FK enforcement.

    Callers own all domain mutations and must keep business record, audit, and
    outbox writes within this single context. No ORM or online service is used.
    """
    path = os.getenv("WF_DATABASE_PATH", DEFAULT_DEV_DB)
    if not path:
        raise RuntimeError("SQLite development database path is empty")
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
