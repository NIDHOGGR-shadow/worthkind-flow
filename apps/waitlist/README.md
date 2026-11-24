# Worthkind Flow — Early-access waitlist preview (NOT live)

This is a **separate development-only app** to validate the product messaging, data fields, permission capture and lead-review process without touching the existing Worthkind website.

## Run locally (Fedora)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r projects/worthkind-flow/apps/waitlist/requirements-dev.txt
export WF_WAITLIST_ENV=development
export WF_WAITLIST_DB=/tmp/worthkind-flow-waitlist-dev.sqlite3
uvicorn api:app --app-dir projects/worthkind-flow/apps/waitlist --reload --port 8001
```

Visit `http://127.0.0.1:8001`; no hotel prospects should be invited to submit real information to this development preview.

## Run checks

```bash
python -m pytest projects/worthkind-flow/apps/waitlist/tests -q
node --check projects/worthkind-flow/apps/waitlist/web/app.js
```

## Consent and states

- Early access requires an **explicit, unchecked** consent box; separate marketing is strictly optional and unchecked.
- Property, contact person, role, contact channel, challenge and timestamp are saved to local SQLite for demonstration only.
- A confirmation produces a unique reference and private withdrawal token; the token is only returned once and stored as a SHA-256 digest.
- Withdrawal revokes both update and marketing permissions; repeated withdrawal is idempotent and doesn't reveal whether the token exists.
- State is **pending_verification**. It does **not** increment the 20 qualified waitlist target.
- No public read/list, emailing, WhatsApp, ad sending or live CRM synchronization is implemented.
- Preview uses hashed client source keys and a small per-hour SQLite rate limiter. This is **not** sufficient distributed anti-abuse.

## Production release blocks

`WF_WAITLIST_ENV=production` raises at import to prevent accidental launch. Before any public waitlist:
1. Owner/legal reviews product privacy notice, controller details and lawful consent, right-to-withdraw and retention/deletion.
2. Engineering replaces dev SQLite with protected hosted storage and legitimate staff auth, per-property dedupe, database migrations, encrypted backups, production anti-abuse and error monitoring.
3. Verify contact email ownership and decision-maker status; complete secure email notification/withdrawal flow with a permitted provider.
4. Provide accessible and mobile E2E tests, authenticated admin review queue, status ledger, audit trail and consent evidence; an opt-in is never a signed pilot.
5. Obtain explicit authorization for domain/deployment and confirm traffic policies.

Engineering reference only. The product is not a live AI receptionist, booking system, payment gateway or hotel integration.
