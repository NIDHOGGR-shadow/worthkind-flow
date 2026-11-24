# Worthkind Flow — GitHub durable savepoint

**As of:** 2026-11-20  
**Repository:** [NIDHOGGR-shadow/worthkind](https://github.com/NIDHOGGR-shadow/worthkind) (private)  
**Project folder:** `projects/worthkind-flow/`  
**Product:** Worthkind Flow, the reusable multi-hotel hospitality automation platform (distinct from custom client-specific Hotel OS).  
**Goal ID:** WF-CONTINUOUS-2026-11-19  
**Release state:** Development code on saved GitHub feature branches. **NOT merged, NOT deployed, NOT production-verified.**  
**Tracking:** `docs/BUILD_REGISTER.md` and `docs/GOAL_CHECKPOINT_LOCAL.md`. The Goal Setting plugin is instructions-only and does not persist an actual project task database.

## Owner instructions that control all work

1. Worthkind Flow is a normal connected web application, **not an offline-only app**.
2. Continue building against the existing **local SQLite database** for now. Do not provision/require Supabase or managed PostgreSQL until the owner requests it.
3. Real PMS/booking, payment processor, guest messages, voice/AI, production staff logins, hotel owner approvals and any external API require credentials, authorization and separate validation later.
4. Use **synthetic local hotel/guest/employee records only**. The current SQLite dev schema has plaintext guest fields and property-wide development keys; do not collect or import actual guest PII.
5. Keep the main Worthkind movement website intact. Avoid destructive changes, merge and deployment without deliberate release review.
6. Existing working features remain available while individually hardened; completion always means source + successfully executed tests, then deployment and production verification as separate gates.

## GitHub branch chain and evidence

The following are **dependent draft PRs**, not independent branches against main. Each later branch inherits its predecessor's code. Do not merge in reverse order or confuse a passing CI job with production.

| PR | Function | Known verified CI |
| --- | --- | --- |
| [#2](https://github.com/NIDHOGGR-shadow/worthkind/pull/2) | Original human-first FastAPI/SQLite guest enquiries and dev receipt | Earlier baseline CI |
| [#34](https://github.com/NIDHOGGR-shadow/worthkind/pull/34) | 15-domain master hospitality architecture | Docs, review required |
| [#35](https://github.com/NIDHOGGR-shadow/worthkind/pull/35) | Original synthetic standalone owner UI concept | Static preview, not live operational data |
| [#37](https://github.com/NIDHOGGR-shadow/worthkind/pull/37) | Architecture/recovery and private response no-store hardening | Passing earlier CI |
| [#48](https://github.com/NIDHOGGR-shadow/worthkind/pull/48) | Responsive reception inbox, filters/search, claim and reply | [Run #46](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44548138760): pass |
| [#54](https://github.com/NIDHOGGR-shadow/worthkind/pull/54) | SQLite runner, generated local dev keys, two-property synthetic seed, 24 guest/staff journeys | [Run #70](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44569138411): pass |
| [#55](https://github.com/NIDHOGGR-shadow/worthkind/pull/55) | Private receipt recovery, retry/reload and no-storage UI | [Run #71](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44570004313): pass |
| [#56](https://github.com/NIDHOGGR-shadow/worthkind/pull/56) | Full SQLite departmental ticket lifecycle and staff console from earlier ticket work | [Run #76](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44571307144): pass |
| [#61](https://github.com/NIDHOGGR-shadow/worthkind/pull/61) | Source-backed management dashboard from local cases/tickets/audit/outbox | [Run #88](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44577901026): pass |
| [#63](https://github.com/NIDHOGGR-shadow/worthkind/pull/63) | Hotel fact drafts, versioned approval/rejection/withdrawal, public FAQ | [Run #102](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44580266898): pass |
| [#64](https://github.com/NIDHOGGR-shadow/worthkind/pull/64) | Direct case→department ticket handoff with idempotency and tenant scoping | [Run #107](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44581524385): pass |
| [#66](https://github.com/NIDHOGGR-shadow/worthkind/pull/66) | Actual headless Chromium mobile/desktop FastAPI+SQLite integration smoke suite | **CI BLOCKED:** [run #110](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44802619267) failed before job steps, including all legacy tests; no runner assigned or usable logs. Browser tests not executed |

**Separate, not in the active branch chain:**
- [#31](https://github.com/NIDHOGGR-shadow/worthkind/pull/31): original ticket reference work; functionally integrated into local active chain in #56; keep source/history for audit.
- [#49](https://github.com/NIDHOGGR-shadow/worthkind/pull/49): draft PostgreSQL tenant/RLS schema. **PAUSED BY OWNER.** Do not merge/apply it or require it to run SQLite dev app.
- Other waitlist and provider-plan PRs may exist but do not constitute a live pilot or connected platform.

## How to resume code and run locally

From the repository checkout, use **the latest active feature branch** `feat/worthkind-flow-browser-e2e-2026-11-19` (or current successor) rather than `main`, which does not contain this stack of unmerged feature work.

```bash
git fetch origin
git switch feat/worthkind-flow-browser-e2e-2026-11-19
cd projects/worthkind-flow
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r apps/api/requirements-dev.txt
python scripts/local_dev.py start --seed-demo
```

Then open:
- Guest service: `http://127.0.0.1:8765/`
- Reception: `http://127.0.0.1:8765/staff`
- Department tickets: `http://127.0.0.1:8765/staff/tickets`
- Hotel operations: `http://127.0.0.1:8765/staff/operations`
- Hotel FAQ approval: `http://127.0.0.1:8765/staff/knowledge`

The runner prints hotel-specific development keys; the SQLite data and keys are in the gitignored `.local/` folder. The runner is loopback-bound **for safe local development only**, not because the final product is offline-first.

Tests without external providers:
```bash
python -m pytest apps/api/tests -q
node --test apps/web/tests/staff-ui.test.cjs
node --test apps/web/tests/guest-recovery.test.cjs
node --test apps/web/tests/tickets-ui.test.cjs
node --test apps/web/tests/operations-ui.test.cjs
node --test apps/web/tests/knowledge-ui.test.cjs
```

Full real Chromium test (requires installing Playwright and Chromium):
```bash
python -m pip install "playwright>=1.50,<2"
python -m playwright install chromium
python scripts/browser_smoke.py
```
This starts a disposable web server and SQLite test database in a temporary folder. The GitHub `browser-e2e` CI job runs it on every PR change to this project.

## Next unfinished, high-value tasks

1. **Unblock GitHub Actions execution and verify PR #66.** On 2026-11-20, [run #110](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44802619267) completed failure with all five jobs ending within seconds and zero steps/empty runner names; logs returned BlobNotFound. This is an execution failure **before tests**, not proof of a code defect or pass. Re-run once GitHub Actions availability/account execution/billing constraints are resolved, then fix Chromium failures if any and record verified evidence.
2. Browser/manual keyboard and screen-reader review at 320px/390px/768px/desktop; fix any layout and focus issues without changing core app architecture.
3. Complete local-only typed integration adapter interfaces for real provider outcomes (PMS availability, booking, hotel PSP, message events), test false-positive/duplicate callback cases with fixtures; do **not** enable live calls.
4. Build proper tenant and employee role authentication before any pilot uses real hotel/guest data; keep active SQLite development behavior operational while production migration is planned.
5. Add production safeguards: database migration strategy, backups/recovery, tenant security, consent and retention, audit observability, rate limits, provider truth, incident playbooks and formal release checklist.
6. Later, only with owner approval, provision Supabase/managed PostgreSQL, connect approved messaging/payment/PMS/AI providers and verify a real hotel pilot. Confirm provider-backed results end-to-end before commercial claims.

## Known truth and limitations

- No real rooms or availability, hotel payments, booked inventory, guest notifications, real AI models/voice, authorized staff logins, owner sign-off or subscription billing yet.
- All data on active branches is synthetic. Guest reply is a local database state, not actual provider delivery.
- User has not authorized a deployment or production migration merely by asking to **save on GitHub**.
- Draft PRs and GitHub CI are a durable savepoint. They do not execute new work after this conversation stops.
