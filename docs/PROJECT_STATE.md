# Worthkind Flow — Project state and evidence ledger
**As of:** 2026-11-19 (Africa/Lagos)  
**Status:** PRE-PRODUCTION / DESIGN + DEVELOPMENT REFERENCES ONLY  
**Authority:** This evidence ledger records inspected GitHub code and CI; it does not authorize merging, production deployment, access changes, personal-data collection, or external payment/communication charges.

## Product identity and separation
Worthkind Flow is Worthkind's multi-hotel, subscription-oriented hospitality automation platform. Hotel OS is a **separate** hotel-specific implementation and potential future integration reference, **not** the Worthkind Flow product. Zuvamo/verodesk is separately maintained voice/chat capability, not verified as integrated here.

Core modules remain the 15 domains in `docs/master/domains/`: guest journey, hotel onboarding, content, reception, booking/payment, dining, departmental tickets, staff/roles, AI/knowledge, hotel management/analytics, Worthkind platform/billing, growth/CRM, security/infrastructure, integrations/channels, and events/careers/suppliers. This list is **design scope**, not delivered functionality.

## Confirmed source baseline
Repository: `NIDHOGGR-shadow/worthkind` (private); default `main`. `projects/worthkind-flow/` is present on feature branches, not on `main` as inspected 2026-11-19. Existing Worthkind movement website must remain untouched.

Draft/dependent PR structure at inspection:
| PR | Head → base | Actual scope | Confidence |
|---|---|---|---|
| [#2](https://github.com/NIDHOGGR-shadow/worthkind/pull/2) | `feat/worthkind-flow-foundation` → `main` | FastAPI + SQLite, synthetic properties, rules/FAQ, guest enquiry, receipt proof, staff claim/reply, local audit/outbox and tests | Inspected source; dev only |
| [#31](https://github.com/NIDHOGGR-shadow/worthkind/pull/31) | `feat/worthkind-flow-service-tickets` → foundation | Development IT/hotel service tickets with own audit/outbox and tests | Inspected source; **NOT** in the master/dashboard branch |
| [#34](https://github.com/NIDHOGGR-shadow/worthkind/pull/34) | `feat/worthkind-flow-master-platform-architecture` → foundation | 15-domain plans, source-of-truth API contracts, nine diagrams | Documentation only |
| [#35](https://github.com/NIDHOGGR-shadow/worthkind/pull/35) | `feat/worthkind-flow-reuse-and-dashboard-preview` → master | Original static seven-section dashboard and upstream license register | No API/dashboard auth |
| [#29](https://github.com/NIDHOGGR-shadow/worthkind/pull/29) | waitlist branch, dependent on foundation | Consent/withdrawal waitlist preview, research leads | Synthetic/dev only; no real opt-ins established |
| [#33](https://github.com/NIDHOGGR-shadow/worthkind/pull/33) | WhatsApp architecture branch | Channel architecture, provider constraints, process catalogue | Documentation only |

**Branch conflict / integration warning:** PR #31 (tickets) is not ancestor of PR #35 (dashboard). Do not treat dashboard and ticket code as currently one tested branch; reconcile with targeted integration and conflict testing. Do not merge parallel draft branches directly into main.

## Verified checks (GitHub Actions, not local execution here)
- Foundation head `3f0a58ccf90c1ebc0b7cdae1031cb5916ccfe11a`: [run 43969331959](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/43969331959) = completed/success.
- Tickets head `b09a9e2bcf58b95ebed386c4d3f7f6c493c5f6f9`: [run 44087466395](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44087466395) = completed/success.
- Dashboard head `47bf986bbe87e542bb90bfa89cb45d3501bbf10a`: [run 44514189360](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44514189360) = completed/success.
- On those runs, Python 3.11 API, Python 3.12 API, JavaScript syntax and the original Worthkind site regression jobs each reported success. **No browser end-to-end, connected provider, manual hotel, load, security audit or live deployment success is asserted.**
- Source file `apps/api/main.py` explicitly throws when `WF_ENV=production`. SQLite startup seeds synthetic properties. `outbox_worker.py` writes to a local simulation log, not external providers. The web client retains idempotency key and receipt token across retry attempts.
- No direct evidence of a paying hotel, real guest delivery, live room/price/booking authority or paid AI entitlement.

## Current inventory
| Capability | Evidence/status |
|---|---|
| No-AI guest enquiry and receipt | IMPLEMENTED; VERIFIED IN TEST via PR #2 CI, dev-only |
| Rules-only hotel facts and explicit unsupported-answer abstention | IMPLEMENTED; VERIFIED IN TEST, synthetic records |
| Staff shared-key claim/reply | IMPLEMENTED; VERIFIED IN TEST, production auth BLOCKED |
| Local atomic audit/outbox and simulated crash/replay | IMPLEMENTED; VERIFIED IN TEST, **no external delivery** |
| IT/maintenance/reception ticket lifecycle | IMPLEMENTED; VERIFIED IN TEST on separate PR #31 |
| Pilot waitlist | Dev implementation; NOT live-approved |
| Owner dashboard | Static design; no live permissions, source-linked KPI or customer data |
| Staff invitations, revocation, SSO/RBAC, tenant DB policies | NOT STARTED for production |
| PostgreSQL migrations + transaction-safe outbox worker + provider receipts | NOT STARTED |
| Hotel-owned CMS and real hotel configuration | NOT STARTED |
| Subscriptions, agent entitlements, spend/metering, platform billing | DESIGNED; NOT IMPLEMENTED |
| AI runtime / voice / official WhatsApp channel integrated here | DESIGNED / NOT VERIFIED |
| PMS availability, quoted rates, booking, hotel guest checkout, reversal | NOT IMPLEMENTED |
| Real SLA escalation, alerts, backup/restore, privacy operations | NOT IMPLEMENTED |

## Non-negotiable invariants
1. All sensitive records are tenant-scoped **at storage and authorization**, never based on a browser-provided property slug alone.
2. An enquiry is not a reservation; an outbox record is not a delivered message; a provider-accepted payment is not reconciled hotel revenue.
3. Guest proof must not enumerate other guest records; staff accounts must be individual, invited, revocable and least-privileged.
4. Every committed business transition also commits an audit record and a durable outbound event in one transaction.
5. External retries use persisted idempotency keys, signed/authenticated callbacks, deduplicated inbox receipts, bounded backoff and an exception owner.
6. AI must not be the only path to a human, nor gain autonomous room, finance or staff authority.
7. A marketing/agent subscription and a hotel guest payment are different money flows and settlement owners.
8. Do not enable production start until tested migrations, tenant permissions, privacy, operational monitoring and provider authorities are approved.

## Three next actionable deliverables
1. **M1-A: staff/tenant access boundary:** define/authenticate hotel owner + invited individual staff, property memberships, revocation and role permissions; write PostgreSQL migrations and cross-tenant negative tests. Acceptance: unknown/revoked/wrong-hotel staff have zero access; two hotels' staff/cases are isolated.
2. **M1-C/D: one verified human service flow:** integrate ticket branch with foundation after review, ensure staff case→ticket→reply, durable outbox worker and source-labelled delivery outcomes; test duplicate/concurrent operations, lost response and crash/replay. Acceptance: no case lost, duplicate, or falsely shown delivered.
3. **M1-E/F: manager dashboard and pilot release gate:** bind metrics to authorized live data, hotel content approval, observability/runbook, mobile/browser and restore checks; require a named authorized pilot hotel and staff coverage before external launch.

## Decisions pending owner or actual pilot
- First pilot hotel's legal/operational authority, real contact staff and hours; who is responsible for unresolved urgent cases.
- Primary authenticated identity provider and first managed PostgreSQL tenant/storage arrangement (prefer existing stack pending code/contract review).
- Authorized external communication provider (email/WhatsApp/SMS) and status-webhook capability; **no credentials in repo/chat**.
- Separate subscription processor/platform invoices versus hotel-owned PMS/PSP system; defer all live money calls.
- Privacy/controller agreement, retention and incident contacts reviewed for the pilot.

## Resume instructions
1. Inspect [PR #2](https://github.com/NIDHOGGR-shadow/worthkind/pull/2), [PR #31](https://github.com/NIDHOGGR-shadow/worthkind/pull/31), [PR #34](https://github.com/NIDHOGGR-shadow/worthkind/pull/34), [PR #35](https://github.com/NIDHOGGR-shadow/worthkind/pull/35) and their GitHub Actions runs; check branch heads for changes since this snapshot.
2. Use `docs/master/` as the proposed domain specification, `docs/reuse/` as the upstream component selection baseline, and this file for evidence/state.
3. Work on a new feature branch and draft PR; do not silently merge, deploy, contact hotels or enable providers.
4. Add each accepted code change with files, tests, timestamp, actual run evidence, risks, and the next integration dependency to this ledger.

**Last action logged:** recovery/source audit and documentation only. No product source code, real tenant data, secrets or running infrastructure changed by this ledger.


## P0 hardening changes on this review branch (not production)
- Changed \`apps/api/main.py\`: sensitive property-scoped /enquiries and /staff API responses get Cache-Control: no-store and Pragma: no-cache, including rejection responses. This is defense in depth against accidental HTTP response caching; it does **not** replace TLS, staff identity, database permissions, or audit.
- Changed \`apps/api/tests/test_integrity.py\`: test validates response status and the above headers for creation receipt, authorized guest lookup, rejected guest lookup, authorized employee listing and rejected employee listing.
- Status at commit: IMPLEMENTED UNVERIFIED until the current branch's GitHub Actions run completes. No production deployment or manual browser test asserted.

## Subsequent vertical UI slice — staff workspace (2026-11-19)
- Branch: feat/worthkind-flow-staff-workspace-2026-11-19 (child of engineering recovery PR #37); intentionally not on main and not live.
- [BUILD_REGISTER.md](BUILD_REGISTER.md) tracks the agreed 15 domains, release gates, and UI source decisions.
- apps/web/staff.html, apps/web/styles.css, apps/web/staff.js: original responsive property-scoped development case queue with real-from-dev-API counts, filters/search, empty/loading/error/credential-change states, key show/hide, claim/reply connected to existing FastAPI routes, textContent-safe case rendering.
- apps/web/tests/staff-ui.test.cjs: Node built-in test fake-DOM behavior tests; workflow adds node --test alongside existing Python and original-site checks.
- **Current verification:** VERIFIED IN TEST on branch head 3c6f7ff187f3f7aca80b5255b2e82ddad6b6e957 via GitHub Actions [run #44](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44547970748) completed/success: Python 3.11 and 3.12 API suites, JS syntax, built-in Node staff interaction tests, original Worthkind website test/build. Documentation updates afterward are not product runtime changes. No external UI code, assets, hotel PII, provider integrations, real staff authentication, main merge or production deployment introduced.
- **Remaining:** actual browser/keyboard/screen reader/mobile viewport, local real-API staff-action walkthrough, individual staff identity, tenant DB and provider delivery; manual UI verification is required before any deployment.

## Owner-approved local-first execution, 2026-11-19

- Owner paused managed databases, hosted authentication, and external APIs. Offline-first local SQLite/synthetic workflows are prioritized. PostgreSQL draft PR #49 remains parked and is NOT in current local branch ancestry.
- PR #54: local runner, private demo secrets and 24 complete SQLite guest-to-staff journeys. [CI #70](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44569138411) passed.
- PR #55: guest receipt recovery across browser restart, loss-safe retry and simulated guest DOM tests. [CI #71](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44570004313) passed.
- PR #56: integrates original dev ticketing PR #31 into local SQLite API and ticket page, includes stale cross-property response protection and additional UI tests. [CI #73](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44571070545) passed.
- No GitHub merge or production deployment; staff keys are still demo-only and SQLite personal details are plaintext. All records must remain synthetic.
