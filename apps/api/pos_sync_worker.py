"""Periodic refresh of already linked receipts; no new matches or payment writes."""
import logging
import os
import signal
import time
from datetime import datetime
import psycopg
from fastapi import HTTPException
from loyverse_pg import account,fetch,receipt_view

log=logging.getLogger("wf.pos_sync")
running=True

def stop(*_):
    global running
    running=False

def db(query,params,many=False):
    with psycopg.connect(os.environ["WF_POS_SYNC_POSTGRES_DSN"],connect_timeout=5) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE wf_pos_sync")
            conn.execute("SET LOCAL statement_timeout='10s'")
            cur=conn.execute(query,params)
            return cur.fetchall() if many else cur.fetchone()

def run_once():
    rows=db("SELECT * FROM worthkind_flow.lease_pos_refresh(%s)",(5,),many=True)
    for evidence_id,lease,slug,store,alias,currency,digits,number in rows:
        try:
            cfg=account(slug,(store,alias,currency,digits))
            raw=fetch(cfg,number)
            amount,kind,created,updated=receipt_view(cfg,number,raw)
            cancelled=raw.get("cancelled_at")
            if cancelled is not None:
                cancelled=datetime.fromisoformat(cancelled.replace("Z","+00:00"))
                if cancelled.tzinfo is None or cancelled<created:
                    raise ValueError("Invalid cancellation time")
            params=(evidence_id,lease,alias,store,number,amount,kind,created,updated,cancelled,True)
        except (HTTPException,ValueError,TypeError,AttributeError):
            params=(evidence_id,lease,alias,store,number,None,None,None,None,None,False)
        db("SELECT worthkind_flow.complete_pos_refresh(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",params)
    return len(rows)

def main():
    if os.getenv("WF_POS_SYNC_ENABLED")!="1":
        raise SystemExit("POS sync not enabled")
    if not os.getenv("WF_POS_SYNC_POSTGRES_DSN") or not os.getenv("WF_LOYVERSE_ACCOUNTS_JSON"):
        raise SystemExit("POS sync configuration missing")
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    while running:
        try:
            n=run_once()
            if n:
                log.info("Processed %s receipt refresh leases",n)
        except (psycopg.Error,KeyError):
            log.warning("Receipt refresh database unavailable")
        for _ in range(30):
            if not running:
                break
            time.sleep(1)

if __name__=="__main__":
    main()
