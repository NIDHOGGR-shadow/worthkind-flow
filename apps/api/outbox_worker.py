"""Worthkind Flow local event outbox exercise.

This simulates an idempotent local sink and deliberately DOES NOT send notifications.
A production worker must use provider-side idempotency, leases and monitoring.
"""
import argparse
import json
import os

from main import database
from delivery_contract import create_delivery_tables


def simulate_local_delivery(limit: int = 100, fail_after: int | None = None) -> int:
    """Atomically mark a batch processed only after local simulated delivery is logged.

    Test-only SQLite workflow; external network side effects cannot be committed in
    the same transaction and need an idempotent provider/inbox contract.
    """
    if os.getenv("WF_ENV") == "production":
        raise RuntimeError("Local simulation worker may not run in production")
    if limit < 1 or limit > 500:
        raise ValueError("Limit must be between 1 and 500")
    count = 0
    with database() as conn:
        create_delivery_tables(conn)  # supports older local SQLite files too
        conn.execute("BEGIN IMMEDIATE")
        events = conn.execute(
            "SELECT id, property_id, case_id, event_type "
            "FROM outbox WHERE processed_at IS NULL AND NOT EXISTS ("
            "SELECT 1 FROM dev_provider_delivery_state d WHERE d.event_id=outbox.id"
            ") ORDER BY created_at, rowid LIMIT ?",
            (limit,),
        ).fetchall()
        for event in events:
            if fail_after is not None and count >= fail_after:
                raise RuntimeError("Simulated crash before transaction commit")
            conn.execute(
                "INSERT OR IGNORE INTO dev_delivery_log(event_id, property_id, case_id, event_type) "
                "VALUES(?,?,?,?)",
                (event["id"], event["property_id"], event["case_id"], event["event_type"]),
            )
            conn.execute(
                "UPDATE outbox SET processed_at=CURRENT_TIMESTAMP, attempts=attempts+1 "
                "WHERE id=? AND processed_at IS NULL",
                (event["id"],),
            )
            count += 1
    return count


def pending_outbox_count() -> int:
    with database() as conn:
        return conn.execute("SELECT COUNT(*) FROM outbox WHERE processed_at IS NULL").fetchone()[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Worthkind Flow local outbox testing")
    parser.add_argument("--simulate-local", action="store_true",
                        help="Simulate event consumption into a local SQLite log; no messages sent")
    args = parser.parse_args()
    if args.simulate_local:
        result = {"simulated_events": simulate_local_delivery(), "real_notifications_sent": 0}
    else:
        result = {"pending_events": pending_outbox_count(), "real_notifications_sent": 0}
    print(json.dumps(result))
