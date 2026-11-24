# WF-DELIVERY-01 — SQLite fake-provider lifecycle (development only)

## The source-of-truth problem
An outbox event proves a local **business transition was recorded**. It does not prove that a provider accepted a message or that a guest received it. The old `outbox_worker.py --simulate-local` only writes a local sink and is not evidence of external delivery. This contract is a **synthetic test instrument**, not an actual SMS/email/WhatsApp gateway.

## Exact states

1. `queued`: existing event has no fake-provider attempt and `processed_at IS NULL`.
2. `retry_due`: fake provider returned `transient_error`. Attempts 1 and 2 become eligible after 60 and 120 seconds; attempts before the due time are no-ops. The third transient error becomes `dead_letter`.
3. `accepted`: fake provider has acknowledged the event; the outbox row is consumed in the same SQLite transaction. **Not delivered.**
4. `delivered`: a second, explicit *synthetic receipt* with outcome `delivered` was recorded for an accepted event. **Not a real guest communication.**
5. `dead_letter`: permanent fake failure, retry exhaustion or synthetic `undeliverable` receipt. This requires future human investigation, not automatic replays.
6. `legacy_local_consumed`: the pre-existing `outbox_worker.py` local sink consumed the event; it is **not** provider acceptance or delivery.

All event attempts, fake receipts, and state are scoped to an existing SQLite outbox event. No customer names, contact details, message bodies, gateway tokens or real receipt addresses are stored in the state. Synthetic error codes (`MOCK_*`) do not contain PII. No network calls are made. The API returns `real_messages_sent: 0` and `real_delivery_verified: false` even if a synthetic receipt says `delivered`.

## How to exercise (synthetic local dev data only)

Start the existing loopback-only demo as documented in `LOCAL_FIRST.md`, or seed it first. Set `WF_DATABASE_PATH` to the **same** SQLite file (and keep `WF_ENV=development`). Inspect `outbox.id` through SQLite in the local development environment; never paste guest PII or dev staff keys into public issues. Run these separately on a previously untouched event:

```bash
python scripts/mock_delivery.py attempt EVENT_ID transient_error
# Backoff is enforced. On a later eligible attempt:
python scripts/mock_delivery.py attempt EVENT_ID accepted
python scripts/mock_delivery.py receipt EVENT_ID fake-receipt-001 delivered
```

Other explicit outcomes: `permanent_error`, `undeliverable`. These do not cause external side effects. Re-running the same accepted event or receipt does not increment attempts. Contradictory reuse of the same receipt ID fails. Simulated failure/attempt history rolls back if the SQLite transaction fails.

Read-only review endpoint:

`GET /api/properties/{slug}/staff/operations/delivery?limit=40` with the **correct hotel development** `X-Staff-Key`; returns event type, timestamp, synthetic retry/error status, per-hotel counts, and the explicit real-delivery false marker. A wrong key cannot see a second hotel's events. This route shares the prototype's **temporary property-wide developer key**, not individual production staff RBAC.

The older `outbox_worker.py --simulate-local` remains available for legacy local sink tests, but now **skips events already managed by this provider simulator**. Do not use these fake-provider states to send actual messages.

## Verification and limits

- `apps/api/tests/test_delivery_contract.py`: accepted vs delivered, idempotent replay, conflicting synthetic receipt, 60/120-second backoff, retry exhaustion, permanent error, invalid input, rollback, legacy worker conflict, API auth and two-hotel isolation, and fail-closed production guard.
- The isolated copy of those tests passed **9/9 on 2026-11-20**, with an in-memory-shape/synthetic local SQLite fixture and FastAPI TestClient; **full combined application, browser and GitHub CI not verified** while [WF-CI-01 issue #68](https://github.com/NIDHOGGR-shadow/worthkind/issues/68) remains open.
- Production requires a leased/atomic worker, provider-side idempotency, signed inbound receipts and signatures, security-approved data retention, real monitoring, human-operated redrive, genuine consent, staff identity/role permissions, and operational cost budgets. **These are not implemented.**
- No Supabase, managed database or paid provider account is needed to run these development tests; this does not change the intended connected web product.