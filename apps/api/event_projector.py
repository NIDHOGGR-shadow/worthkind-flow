"""Internal event projection worker. Does not send messages or confirm delivery."""
import argparse
import logging
import os
import signal
import threading

import psycopg

LOG = logging.getLogger("worthkind.event_projector")


def project_batch(dsn: str, limit: int = 100) -> int:
    if not 1 <= limit <= 500:
        raise ValueError("Batch size must be between 1 and 500")
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE wf_event_projector")
            conn.execute("SET LOCAL statement_timeout = '15s'")
            return conn.execute("SELECT worthkind_flow.project_case_events(%s)", (limit,)).fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 500:
        parser.error("batch size must be between 1 and 500")
    dsn = os.getenv("WF_EVENT_PROJECTOR_POSTGRES_DSN")
    if not dsn:
        parser.error("WF_EVENT_PROJECTOR_POSTGRES_DSN is required")
    logging.basicConfig(level=logging.INFO)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    backoff = 1
    while not stop.is_set():
        try:
            count = project_batch(dsn, args.batch_size)
            LOG.info("Projected %d internal events", count)
            backoff = 1
            if args.once:
                return 0
            if count < args.batch_size:
                stop.wait(2)
        except psycopg.Error:
            LOG.warning("Event projection transaction failed; retrying without acknowledging events")
            if args.once:
                return 1
            stop.wait(backoff)
            backoff = min(backoff * 2, 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
