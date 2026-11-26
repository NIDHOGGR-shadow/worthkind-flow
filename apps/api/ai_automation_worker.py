"""Deterministic internal alert worker. No access to model, secrets or business mutations."""
import os
import signal
import logging
import time
import psycopg

running=True
log=logging.getLogger("wf.ai_automation")

def stop(*_):
    global running
    running=False

def run_once():
    with psycopg.connect(os.environ["WF_AI_AUTOMATION_POSTGRES_DSN"],connect_timeout=5) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE wf_ai_automation")
            conn.execute("SET LOCAL statement_timeout='10s'")
            return conn.execute("SELECT worthkind_flow.scan_ai_alerts(100)").fetchone()[0]

def main():
    if os.getenv("WF_AI_AUTOMATION_ENABLED")!="1" or not os.getenv("WF_AI_AUTOMATION_POSTGRES_DSN"):
        raise SystemExit("Automation worker not activated")
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGINT,stop)
    signal.signal(signal.SIGTERM,stop)
    while running:
        try:
            count=run_once()
            if count:
                log.info("Created %s internal alerts",count)
        except psycopg.Error:
            log.warning("Internal alert scan unavailable")
        for _ in range(30):
            if not running:
                break
            time.sleep(1)

if __name__=="__main__":
    main()
