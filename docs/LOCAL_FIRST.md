# Worthkind Flow — Local database development (SQLite now, Supabase later)

**Corrected owner decision (19 November 2026):** Use SQLite as the **development database** while the owner defers Supabase/managed PostgreSQL setup. **Worthkind Flow is still a normal connected web application — it is not required to work offline.** Keep building backend APIs, real frontend features, data contracts, UI and local tests. Build integration adapters safely when useful; live provider calls and customer data still require authorized credentials and service agreements. Preserve the PostgreSQL draft PR #49 as a separate paused option, not a current dependency.

## Quick start

Requires Python 3.11+. No PostgreSQL, Supabase, npm, AI key, SMS, PSP or PMS account.

From the Worthkind repository root, run these commands:

    cd projects/worthkind-flow
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r apps/api/requirements-dev.txt
    python scripts/local_dev.py doctor
    python scripts/local_dev.py start --seed-demo

On Windows PowerShell, activate with .venv\Scripts\Activate.ps1 and use python rather than python3. The development runner binds to 127.0.0.1 for safe testing. **That restriction applies to the local runner, not to the final deployed web product.**

- Guest: http://127.0.0.1:8765/
- Reception: http://127.0.0.1:8765/staff
- Hotel operations dashboard: http://127.0.0.1:8765/staff/operations
- Department tickets: http://127.0.0.1:8765/staff/tickets
- Local health: http://127.0.0.1:8765/health

Use the printed local development staff key for the selected demo hotel. Keys are generated on first run and stored in .local/staff-keys.json (owner-only POSIX file permissions). These are not real individual employee credentials. Do not put them in screenshots, issues or GitHub.

SQLite resides at .local/worthkind-flow-dev.sqlite3. All .local files and SQLite journals are gitignored.

## Local commands

| Command | What it does |
| --- | --- |
| python scripts/local_dev.py doctor | Validate local dependencies and initialize isolated local secrets without provider calls |
| python scripts/local_dev.py start | Run current local SQLite application, with no automatic fake cases |
| python scripts/local_dev.py start --seed-demo | Add 16 repeatable synthetic cases and start the local guest and staff pages |
| python scripts/local_dev.py seed | Seed synthetic cases without starting the server |
| python -m pytest apps/api/tests -q | Run local API, adversarial, runner and human-first journey tests |
| node --test apps/web/tests/staff-ui.test.cjs | Run dependency-free staff UI behavior tests if Node is installed |

Seed runs are idempotent; the 16 synthetic cases include queued, claimed and responded states across both synthetic hotels. None represent bookings, payments, notifications or real guests.

## Manual guest-to-reception check

1. Start with --seed-demo and open the guest page. Choose a synthetic hotel, then submit a new enquiry with **fake** name/contact only.
2. Copy the case ID and receipt token. Treat the token as private.
3. Open /staff, choose the same hotel, enter the matching local key and load the case queue.
4. Claim the new case, write a response, then refresh the original guest receipt. It should display responded and the locally recorded reply.
5. Switch to the other hotel. The queue must clear immediately; the original hotel's key must not unlock its records.
6. Test incorrect receipt, duplicate submission, unsupported FAQ and a network interruption. Unknown answers must offer human help; no guest data should leak.
7. Check /health and /api/properties/demo-hotel/booking-capabilities: no live booking, payment or availability should be claimed.
8. Manually validate keyboard focus and layouts at 320px, 390px, tablet and desktop widths. Automated simulated DOM tests are not browser or screen-reader proof.

## Explicit security and provider limitations

- Local SQLite provides real persistence on the computer, **not** production tenancy/security. The existing development case schema stores guest name/contact/details in **plaintext**. Use only synthetic contact details such as guest@example.invalid and never process real guest PII.
- Local shared staff keys are not production login, MFA or role-based access control. This runner binds to loopback only but cannot replace proper security review.
- The database outbox is local and pending. A staff reply records state only; it does not deliver email, SMS, WhatsApp or a phone call.
- The deterministic route engine is not a trained AI model. Public facts are explicitly synthetic hotel fixtures; unsupported answers abstain.
- There is no live inventory, reservation, payment, dining dispatch, job offer or hosted booking claim.

## Next local-database development work

Reception enquiry, receipt recovery, local departmental tickets and the SQLite-backed operational overview have source implementations on dependent draft branches. Continue actual responsive browser QA, accessibility, local staff roles or approved-content workflows, and stable provider adapter contracts tested with fixtures. Do not send real payments/messages or claim PMS booking truth until credentials and hotel authorization are provided.

**Future switch:** user will provide or approve actual managed database and provider APIs later. Do not silently connect online accounts, migrate customer records or release without their direction.

## Department ticketing (local development)

From the reception workspace, open Department tickets, or navigate to http://127.0.0.1:8765/staff/tickets. The page uses the same local SQLite database and demo hotel key. Create a synthetic IT/housekeeping/maintenance/reception ticket; claim, start work, record a note, resolve and reopen. A ticket may link to a guest enquiry only after reception claims that originating enquiry. No real provider sends messages. Read [TICKETING_LOCAL.md](TICKETING_LOCAL.md).

Guests can now also recover a local enquiry after browser reload with their hotel, case ID and private receipt token. The token is not stored in the URL or browser storage.

## Draft → review → publish hotel knowledge

Open **/staff/knowledge** with the same development hotel key. Draft answers are not visible through the public guest FAQ until explicitly approved; withdrawn content is no longer public, and versions are recorded. This is a **local SQLite-backed web workflow**, not an offline-only product requirement. The same demo key currently handles submit/review, so no real hotel authorization or separated approver roles are implied. See [knowledge workflow](KNOWLEDGE_SQLITE.md) and [draft PR #63](https://github.com/NIDHOGGR-shadow/worthkind/pull/63).

## Hotel operations dashboard (SQLite-backed)

Open **/staff/operations** using the same selected demo hotel's development staff key. Metrics are calculated from current local case, ticket, audit and event records; no static dashboard-preview figures are copied into the real view. Changing the hotel or key scrubs the previous hotel's data. The page reports queued/responded cases, ticket status and overdue counts, recent local actions and pending internal events. **Pending events are not notifications delivered.** Bookings, occupancy, revenue and AI usage remain explicitly unavailable without their authoritative integrations. [PR #61](https://github.com/NIDHOGGR-shadow/worthkind/pull/61) is draft and not deployed.
