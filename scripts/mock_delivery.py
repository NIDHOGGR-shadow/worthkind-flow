"""Explicit, local-only fake-provider exercise; never sends a message.

Usage (after local app has created outbox events):
    python scripts/mock_delivery.py attempt EVENT_ID transient_error
    python scripts/mock_delivery.py attempt EVENT_ID accepted
    python scripts/mock_delivery.py receipt EVENT_ID FAKE_RECEIPT_ID delivered
"""
import argparse
import json
import os
from pathlib import Path
import sys

API = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API))


def main():
    parser = argparse.ArgumentParser(description="LOCAL mock delivery outcomes only. No real messaging.")
    options = parser.add_subparsers(dest="command", required=True)
    attempt = options.add_parser("attempt", help="Simulate one provider acceptance/failure for a stored outbox event")
    attempt.add_argument("event_id")
    attempt.add_argument("outcome", choices=("accepted", "transient_error", "permanent_error"))
    receipt = options.add_parser("receipt", help="Record an explicit fake delivery/undeliverable receipt")
    receipt.add_argument("event_id")
    receipt.add_argument("receipt_id")
    receipt.add_argument("outcome", choices=("delivered", "undeliverable"))
    args = parser.parse_args()
    if os.getenv("WF_ENV", "").strip().casefold() == "production":
        parser.error("Fake-provider simulator is forbidden in production")
    from main import initialize, database
    from delivery_contract import simulate_attempt, simulate_receipt
    initialize()
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if args.command == "attempt":
            result = simulate_attempt(conn, args.event_id, args.outcome)
        else:
            result = simulate_receipt(conn, args.event_id, args.receipt_id, args.outcome)
    print(json.dumps({"synthetic_only": True, "actual_messages_sent": 0,
                      "event_id": result["event_id"], "state": result["state"],
                      "attempts": result["attempts"], "retry_after": result["retry_after"]}))


if __name__ == "__main__":
    main()
