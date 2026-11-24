# Local setup: Worthkind Flow P0 reference

This project folder is inside the existing Worthkind monorepo. The movement website remains the root Node.js application.

## Requirements
- Python 3.11 or 3.12.
- No database or AI provider needed for local demo.
- Do not use this development reference for public production.

## Start

From the **Worthkind repository root**:

```bash
python3 -m venv projects/worthkind-flow/.venv
source projects/worthkind-flow/.venv/bin/activate
pip install -r projects/worthkind-flow/apps/api/requirements-dev.txt
export WF_ENV=development
export WF_DATABASE_PATH=/tmp/worthkindflow-dev.sqlite3
export WF_DEV_STAFF_KEYS_JSON='{"demo-hotel":"change-me-demo-only","demo-hotel-two":"separate-key-demo-only"}'
uvicorn main:app --app-dir projects/worthkind-flow/apps/api --reload --port 8000
```

Open `http://127.0.0.1:8000` for guest services and `http://127.0.0.1:8000/staff` for a synthetic receptionist.

## Test

```bash
PYTHONPATH=projects/worthkind-flow/apps/api python -m pytest projects/worthkind-flow/apps/api/tests -q
```

## What works

- Scope-filtered synthetic public hotel FAQs; unknown answers decline rather than invent a fact.
- Authenticated receipt recovery on retry of an unchanged enquiry; concurrent idempotent submissions become one case.
- Atomic case/audit/outbox writes and a local-only replay/crash simulator.

- Optional AI and human-free direct enquiry entry.
- Deterministic intent routing, including human and emergency rules.
- Synthetic property resolution.
- Idempotent enquiry creation with a one-time receipt token.
- Property-scoped status lookup.
- Development-key-gated reception queue, claim and response.
- SQLite business record and audit in one transaction.

## Durability simulation

The P0 API commits every case state transition, an audit row, and a pending outbox
event within a single SQLite transaction. This is a **development contract**, not
a production event infrastructure.

After creating and responding to synthetic enquiries, inspect pending events:

```bash
PYTHONPATH=projects/worthkind-flow/apps/api python -m outbox_worker
```

To exercise replay-safe **local-only** consumption:

```bash
PYTHONPATH=projects/worthkind-flow/apps/api python -m outbox_worker --simulate-local
```

These commands send **zero** email, WhatsApp, SMS or other external notifications.
The simulator logs only event identifiers and type, not guest contact details.

## What is NOT implemented

Production-grade staff authentication/RBAC, live hotel PMS, payment, voice, WhatsApp, LLM API, hotel-specific knowledge CMS, production outbox delivery/worker with retries and dead-letter monitoring, provider webhook signature checks, robust rate limiting, cross-tenant production policy, real hotel data, deployment pipeline and marketing. `WF_ENV=production` explicitly blocks startup to prevent accidental deployment.

## Platform behavior

Never show `Room booked`, `Payment received`, `Kitchen accepted`, `Driver dispatched`, or `Job offer made` unless the authoritative external provider or authorized hotel team verifies it.

Keep this as a path-scoped module. Do not modify the existing root Node site or deploy this Python service using the existing movement site's Vercel settings.
