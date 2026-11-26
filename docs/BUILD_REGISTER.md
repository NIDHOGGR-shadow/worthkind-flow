# Worthkind Flow — Master Build Register
Updated 2026-11-20. This register extends docs/master/IMPLEMENTATION_ROADMAP.md, docs/PROJECT_STATE.md, and docs/OPERATIONS_FLOW_AND_TEST_TRACE.md. All deliveries are tracked on feature branches, not automatically merged or deployed.

## Current end-to-end execution tracker

[**16-stage, 15-domain master checklist**](EXECUTION_MASTER_CHECKLIST.md) is the authoritative status-by-status implementation and release tracking register, with exact PR/CI evidence and independently visible blockers. [CI issue #68](https://github.com/NIDHOGGR-shadow/worthkind/issues/68) records real-browser CI's no-steps failures. Treat milestone labels here as short summaries; use the detailed checklist for acceptance/remaining work.

## Working rules
A discussion or design is NOT implementation. Statuses: NOT STARTED, DESIGNED, IMPLEMENTED UNVERIFIED, VERIFIED IN TEST, READY FOR REVIEW, DEPLOYED, LIVE VALIDATED, BLOCKED. Verify role/tenant permissions, DB transactions, provider status, failure handling, retries, accessibility and negative tests before calling a vertical slice complete.

Preserve Worthkind movement site and the no-AI human contact path. No fabricated bookings, payments, AI answers, real notifications, room availability or KPI data. Hotel guest money and Worthkind subscription money have separate owners and processors.

## Owner-approved execution constraint (2026-11-19)

**LOCAL DATABASE FOR DEVELOPMENT; NOT AN OFFLINE-ONLY APPLICATION.** The owner clarified that the product remains a normal web application. Use existing SQLite locally instead of provisioning Supabase/PostgreSQL yet. Continue implementing web/UI, backend, safe API contracts, integrations behind replaceable adapters, and tests. Live provider calls, real hotel data and financial operations still require appropriate authorization, credentials and security validation. See [LOCAL_FIRST.md](LOCAL_FIRST.md).

- PostgreSQL draft PR #49 (and any child SQL work) is **PAUSED BY OWNER, NOT MERGED**. It is not a dependency for current local builds.
- No real customer PII in local SQLite (existing guest details are plaintext); no claim of deployment or customer service. The local runner must bind loopback-only.
- Current order: reproducible local SQLite development → guest/staff flows and UI → departmental tickets → source-based hotel operations view → browser QA and approved content workflows → adapter contracts → managed database migration when requested.

## UI foundations adopted
- Reuse patterns from our original dashboard-preview: compact navigation, clear hierarchy, status chips, KPI count cards, filters, empty/loading/error states and responsive panel layouts. Never pass illustrative numbers off as live.
- Keep the current vanilla HTML/CSS/JS plus FastAPI for the first operational screen. Do NOT introduce React solely to use shadcn/ui. Consider selected MIT shadcn components only if the future owner console actually uses React and passes license/dependency review.
- Study Chatwoot's agent ownership/conversation statuses; do not copy its source or host Rails solely for a basic reception queue.
- Every control gets clear labels, keyboard focus, mobile support, no unsafe innerHTML from guest input, honest pending states and no storage of dev staff credentials.
- Original Worthkind visual style, not copied upstream brand assets. UI implementation targets existing working endpoints first.

## Active execution sequence

| Order | ID | Outcome | Evidence / status | Acceptance |
| --- | --- | --- | --- | --- |
| 0 | WF-BASE | Recover GitHub branches, docs, CI and source reviews | Draft PR #37, prior CI passed | Reviewed dependencies; no root website changes |
| 1 | WF-UI-01 | Responsive local reception workspace: SQLite API counts/filter/search/claim/reply | TESTED IN CI on PR #48, run #46; browser/manual QA remains | JavaScript/UI tests, visual a11y follow-up |
| 2 | WF-LOCAL-01 | Loopback-only local runner, private dev keys, SQLite synthetic fixture queue | TESTED IN CI on PR #54, run #70; live host/manual launch unverified | CLI setup, seed rerun idempotence, local-only refusal checks |
| 3 | WF-LOCAL-02 | Guest → staff → receipt, local-only service journey verification across both demo properties | TESTED IN CI on PR #54, run #70 (24 journeys) | 24 full no-AI local flows, unauthorized and idempotency failures |
| 4 | WF-UX-02 | Manual guest receipt recovery after reload, safe submit retries and privacy-safe form behavior | TESTED IN NODE UI SIMULATION on PR #55, run #71; actual browser/manual accessibility still pending | Missing/wrong token denial, no storage, retry and new-enquiry tests |
| 5 | WF-TKT-01 | Integrate existing dev ticket PR #31 into local SQLite service/UI | TESTED IN CI on draft PR #56, run #73 (not deployed) | Ticket create/claim/start/resolve/reopen, tenant, rollback and stale UI tests |
| 6 | WF-OWN-01 | Operational dashboard sourced from local SQLite case/ticket/audit/outbox records | TESTED IN CI, draft PR #61 run #88; browser/manual QA pending | Accurate zero/changed counts, wrong-hotel denial, no fake external metrics, source/date labels |
| 7 | WF-KNOW-01 | Reviewable hotel FAQ facts, drafts, version history and withdrawal on local SQLite | TESTED IN CI, draft PR #63 run #102; manual browser QA pending | No unapproved answer leakage, stale version conflict, tenant separation and audit rollback |
| 8 | WF-HANDOFF-01 | Create actual property-scoped department tickets directly from claimed reception cases | TESTED IN CI draft PR #64 run #107; browser QA pending | Only claimed/responded cases; duplicate/foreign-property denial and stored ticket status |
| 9 | WF-SLA-01 | SQLite property-scoped overdue/due-soon/invalid-date human attention queue | IMPLEMENTED PR #69; six pure-rule + seven isolated API/SQLite contract assertions PASS locally; complete app/UI/browser CI UNVERIFIED due issue #68 | Accurate deadline/tenant calculations, human priority queue, no fake alerts |\n| 10 | WF-DELIVERY-01 | Internal outbox → explicitly simulated provider acceptance → synthetic receipt, retry/backoff and terminal dead-letter | Draft [PR #70](https://github.com/NIDHOGGR-shadow/worthkind/pull/70): 9 isolated SQLite/FastAPI tests passed locally; full app/CI UNVERIFIED, production provider NOT CONNECTED | Authenticated hotel review, 3 attempts, 60/120s backoff, replay/rollback, strict accepted != delivered |
| LATER | WF-SEC-01/02 | Hosted PostgreSQL, individual invited staff auth, roles/revocation | **PAUSED by owner**; isolated PR #49 separate | Resume only on user instruction |
| LATER | WF-AI-01 | Optional AI/voice/WhatsApp adapters, contracts and model evaluations | Contract development possible now; live provider calls need credentials and authorization | Grounded evaluation and human fallback |
| LATER | WF-PMS-01 | PMS inventory, hotel PSP booking/payment verification | BLOCKED by hotel/provider permission | Authoritative source receipts |
| LATER | WF-PILOT-01 | Production pilot, real employees and customer data processing | BLOCKED by contract/auth/security | Written permission and live operational signoff |

## Comprehensive domain backlog (15 areas)
| Domain | Work to deliver, including UI + backend + verification | Status |
| --- | --- | --- |
| 01 Guest experience | Hotel-branded mobile landing; service navigation; direct enquiry; receipt tracking; slow-network/error/accessibility | Synthetic guest/staff/receipt and retry TESTED IN CI PRs #54/#55; brand/visual and browser WCAG remain IN PROGRESS |
| 02 Hotel onboarding | Verify organization/owner/property/domain; agreement, pilot approval, setup wizard; hotel creation, pause and exit | DESIGNED / owner authority BLOCKED |
| 03 Content and website | Rooms and services CMS; approved knowledge revisions; media rights; public publishing and rollback | SQLite draft/review/publish/withdraw TESTED IN CI PR #63; real hotel owner approvals, media and full CMS still NOT STARTED |
| 04 Reception | Property-scoped inbox, case ownership, transfer, shift handover, case response; PMS availability lookup | Dev staff queue, claim/reply and linked ticket handoff TESTED IN CI PRs #48/#64; staff transfer/PMS still PLANNED/BLOCKED |
| 05 Booking and payments | Expiring quote/hold; PSP checkout; signed callbacks; PMS confirmation; cancellation, refund, disputes | DESIGNED / provider authority BLOCKED |
| 06 Dining and room service | Restaurants, menus, service orders, kitchen acceptance, delivery, cancellation/exception reports | DESIGNED / restaurant/POS authority BLOCKED |
| 07 Tickets and department operations | Reception, housekeeping, IT, maintenance ticket create/claim/resolve/reopen; SLA, routing, overdue/escalation | Ticket lifecycle and handoff TESTED IN CI #76/#107; deadline attention queue IMPLEMENTED PR #69, pure rule checks pass but integrated CI UNVERIFIED; roles/actual alerts NOT STARTED |
| 08 Staff and roles | Invite-only auth, department scopes, shifts, manager approval, staff audit, revocation | DESIGNED / NOT STARTED |
| 09 AI and knowledge | Hotel-approved FAQ, grounded chat, typed tools, model evaluations, cost limits, voice, WhatsApp and handoff | Deterministic FAQ and SQLite approve/withdraw TESTED IN CI PR #63; actual AI/voice/notices NOT STARTED |
| 10 Hotel manager analytics | Staff/case KPIs, rooms, arrivals, SLA, revenue exception, sources, export and drill-down | SQLite source-backed case/ticket/event management dashboard TESTED IN CI PR #61 #88; revenue/occupancy, real manager auth, data export NOT STARTED |
| 11 Worthkind commercial platform | Tenant support, subscription, entitlements, metered usage, provider status, platform invoices and internal ops | DESIGNED / NOT STARTED |
| 12 CRM, marketing and ads | Hotel lead pipeline and consented waitlist; guest opt-in/out, attribution, campaign ROI verified against real outcomes | Dev waitlist PR #29; integrations NOT STARTED |
| 13 Security and platform operations | Tenant isolation/RLS, secrets, API abuse, backup/restore, CI, alerting, privacy rights, incident runbooks, rollback | Earlier CI dev tenant/no-store/idempotency tests passed; browser CI issue #68 OPEN, individual staff auth, rate limits, encrypted PII, production controls NOT STARTED |
| 14 Integrations and notifications | Signed webhook inbox, outbox, provider retries, email/SMS/WhatsApp, PMS, PSP, AI and callback receipt contracts | Local sink tested earlier; fake-provider retry/receipt/dead-letter contract locally tested 9/9, integrated on draft PR #70 but GitHub CI UNVERIFIED; real provider integrations NOT STARTED |
| 15 Events, HR and suppliers | Event venue quotations, career/supplier enquiries, private recruitment/vendor access, approvals and retention | Synthetic enquiry route exists; full workflow NOT STARTED |

## Cross-cutting release gates
| Gate | Required evidence | Status |
| --- | --- | --- |
| R0 source and license | Inspect upstream source/path/license, dependency risks; root site tests | SOURCE/LICENSE RESEARCH DOCUMENTED; production license/dependency review pending |
| R1 tenant and staff | Two-property scope, invite/revoke, RLS/authorization, cross-role negative cases | DEV tenant separation TESTED; production staff RBAC/RLS NOT STARTED |
| R2 human-first | 20 completed no-AI guest->staff journeys, concurrency, signed receipt and timeout | 24 synthetic guest→staff journeys tested; actual staff/notification and signed external proof NOT VERIFIED |
| R3 reliable delivery | Provider accepted vs delivered, retry and dead-letter, crash/replay, actual backup restore | PARTIAL: synthetic SQLite provider contract 9/9 isolated checks PASSED PR #70; real signed receipts, full-app CI, background lease and backup/restore NOT VERIFIED |
| R4 usability | 320px, 390px, tablet/desktop, keyboard/screen reader, low-network/error and no fabricated data | Real browser suite IMPLEMENTED PR #66 but CI #114/#119/#122 fail with no steps; screen reader/mobile acceptance NOT VERIFIED |
| R5 AI activation | Approved hotel content, budget, privacy, 100 eval/adversarial fixtures and off switch | NOT STARTED |
| R6 booking/payment | PMS source ID, PSP signing/independent lookup, mismatch, duplicate, refund/dispute | BLOCKED |
| R7 commercial/live | Authorized hotel, staff, signed terms, incident runbook, monitoring and rollback | BLOCKED |


## Latest CI evidence — 20 November 2026

- [PR #70 Actions run #44810292008](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44810292008) failed all 5 jobs and the inspected Python 3.11 job reported `steps: []`; [run #44810102808](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44810102808) also failed all five with zero inspected Python and web steps. [WF-CI-01 #68](https://github.com/NIDHOGGR-shadow/worthkind/issues/68) updated. **No new full-app test has been demonstrated.** The delivery contract still has **nine isolated local passes**, not a successful original-app execution.
- An additional source-level cross-module test in `test_integrity.py` now requires the legacy local worker to leave managed fake-provider retries/dead letters untouched; this particular integration test has **not executed in the failed GitHub workflow**.

## Local-first verification checkpoint (2026-11-19)
- [PR #54](https://github.com/NIDHOGGR-shadow/worthkind/pull/54) introduces local-only startup/SQLite synthetic seed and 24 guest→staff→receipt tests; [GitHub Actions run #70](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44569138411) passed Python 3.11/3.12, Node reception UI and root movement website tests.
- [PR #55](https://github.com/NIDHOGGR-shadow/worthkind/pull/55) adds manual receipt recovery without storing secret tokens in cookies/localStorage/URL, safe idempotent submit retries and private token controls; [GitHub Actions run #71](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44570004313) passed all four jobs including guest simulated-DOM tests. This does not replace real-browser/assistive technology verification.
- Both PRs remain **draft and unmerged**; no external provider, managed database or production release is involved.

## Fake-provider event recovery contract — WF-DELIVERY-01, 20 November 2026

- [Draft PR #70](https://github.com/NIDHOGGR-shadow/worthkind/pull/70), based on pending PR #69, implements a **development-only fake** provider contract: `queued`, `retry_due`, `accepted`, `delivered` after **synthetic** receipt and `dead_letter`. Real messages sent: **zero**.
- Durable attempts and fixed error codes live in SQLite; transactional fake acceptance, retry timing, max-attempt budget, explicit synthetic receipts and tenant-isolated staff read API are implemented. The legacy local sink is prevented from bypassing events already tracked by the fake provider simulator.
- **Actual local proof:** 9/9 isolated Python pytest tests passed with synthetic FastAPI+SQLite fixtures; CLI syntax compiled. The combined Worthkind Flow app, old worker interlock and real Chromium checks **remain UNVERIFIED in Actions** because [WF-CI-01 issue #68](https://github.com/NIDHOGGR-shadow/worthkind/issues/68) has no executed job steps/logs. This proof does **not** demonstrate actual hotel messages or webhook signatures.
- Implementation/limitations: [DELIVERY_SQLITE.md](DELIVERY_SQLITE.md). Next: full integrated QA when CI runs; then operational redrive, signed inbound webhook tests and hotel-authorized adapters without inventing delivery.

## Latest local departmental workflow evidence

- Draft [PR #56](https://github.com/NIDHOGGR-shadow/worthkind/pull/56) integrates existing service ticket code from PR #31 into the current SQLite FastAPI app with ticket board at /staff/tickets; [Actions run #73](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44571070545) passed both Python versions, imported ticket tests, guest/staff/ticket UI tests and root site checks. No merged or live deployment. Staff roles and notification providers remain intentionally deferred.


## Hotel knowledge milestone acceptance (WF-KNOW-01)
- [Draft PR #63](https://github.com/NIDHOGGR-shadow/worthkind/pull/63) implements SQLite property-scoped draft, versioned approval, rejection and withdrawal; public FAQ reads only approved fact versions, with no model inference.
- [GitHub Actions run #102](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44580266898) passed Python 3.11/3.12 API tests, JS staff/guest/tickets/operations/knowledge UI tests and original website regression on code head `53637e0794d7a2562400f096a43afd51395aeda0`.
- Rejected/stale drafts cannot be published, unpublished facts are not public, wrong-property key does not grant access, and an audit write failure rolls back the operation.
- **Development-only review:** the same per-property demo key can submit/approve. Real hotel owner verification, separated content-approval roles, browser accessibility and production data policy remain unresolved.
- [Implementation and manual QA](KNOWLEDGE_SQLITE.md).

## Dashboard milestone acceptance (WF-OWN-01)
- Backend: `apps/api/operations.py` is a property-scoped **read-only** development endpoint; all numbers come from local SQLite within a transaction, not from mock JSON or the static owner-preview file.
- Frontend: `apps/web/operations.html` and `operations.js` render source-labelled figures, zero and error states, overdue work and a recent activity feed. Hotel/key changes erase previous private data from DOM; no localStorage or third-party scripts.
- Truthfulness: no booking, occupancy, revenue, successful payment, genuine delivery or AI metrics are invented; pending outbox is never described as delivered.
- Tests: `apps/api/tests/test_operations.py` verifies SQLite counts, two-property exclusion, denied access, overdue status and invalid dates; `apps/web/tests/operations-ui.test.cjs` checks safe rendering, stale responses, reset and provenance. **Verification:** [GitHub Actions run #88](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44577901026) passed on functional code head 317f2883c26949025d3b378a7a484cafba9a0866. State is **TESTED IN CI** only. Manual UI/browser, actual hotel data, deployment and production are still unverified.


## Reception-to-department handoff (WF-HANDOFF-01)
- [Draft PR #64](https://github.com/NIDHOGGR-shadow/worthkind/pull/64) changes the existing reception queue to return the actual linked ticket ID/status from SQLite and to create department work for already-claimed cases.
- [Actions run #107](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44581524385) completed successfully for Python 3.11/3.12 APIs, all JS behavior checks, and Worthkind movement site regressions on functional head ff727f8730b2787ba7e0f2aee3e8c47495db3130.
- Backend rejects an unclaimed case, a second linked ticket or an ID from another hotel. Client retains the same idempotency key after a lost reply, and does **not** copy guest names or contact details into departmental task payloads.
- Shared developer keys and synthetic records remain the only actors; real employee identity, department-level role policy and actual hotel notifications are not implemented.
- **Next priority:** unblock GitHub Actions [issue #68](https://github.com/NIDHOGGR-shadow/worthkind/issues/68), verify browser PR #66 and SLA PR #69 in actual executed CI, then complete responsive/keyboard and operational recovery gates.


## Latest CI visibility — development-blocking test infrastructure

[Run #130](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44808232421) on latest SLA PR #69 again reported all five jobs failed **with no available recorded steps**. [Issue #68](https://github.com/NIDHOGGR-shadow/worthkind/issues/68) is OPEN. This is not evidence that the application code's tests were executed or passed. Maintain browser and integrated SLA status as **IMPLEMENTED / FULL CI UNVERIFIED** until a run executes jobs with logs and succeeds. Earlier app head #64 CI #107 remains the last previously confirmed green integrated set.

## Update protocol
Record every task as proposed/implemented/tested/deployed/live-validated separately. For each change: PR/commit, files, exact tests/CI run, failed scenarios, security/privacy risk, owner blocker and next dependency. Keep draft branch ancestry visible. NEVER merge/deploy or alter live financial/security settings without owner authorization.

Next: investigate Actions issue #68 and obtain executed passing CI for browser PR #66 and local deadline attention PR #69. Then continue SQLite-based web integrations, staff roles and provider contract simulators. Keep cloud database provisioning paused until owner authorizes it; **this is not an offline-only product**.

## 2026-11-26 — Backend AI policy reconciliation
- Backend PR #3 baseline a330693623f5c181d5c46b504f132aafc9277803: all four jobs in Actions run 45715767428 and the separate database recovery run 45715767273 passed. This is disposable CI evidence, not hosted production acceptance.
- Ported PR #1's deterministic urgent/human/support/sensitive-request bypass to the existing Modal gateway; no second inference architecture or NVIDIA activation. Text requests bypass provider and retrieval; voice transcripts bypass chat inference and synthesis after consented ASR, and the reserved quota entry is finalized as abstained. Handoff is a routing result, not a confirmed staff connection or dispatch. Conservative regex checks may over-route and are not comprehensive emergency detection or DLP.
- Malformed Modal URL configuration now fails closed. Regression coverage added to test_ai_boundaries. New revision requires GitHub Actions confirmation; live Modal chat/voice, approved knowledge, real identity and hosted deployment remain unverified. PR #1 remains open for review of any other useful differences.

## 2026-11-26 — Guest resolution confirmation and reopening
- Migration 047 records receipt-authorized guest decisions separately from staff resolution. A specific staff resolution ID is required; immutable decisions, case row locking and replay handling prevent stale retries or double events. Reopening returns the case to the reception queue and clears the old assignee. Guest and authorized reception staff can read current confirmation status. Audit/outbox entries do not imply external delivery.
- Added versioned guest GET/POST /guest/cases/{case_id}/resolution and staff GET /staff/cases/{case_id}/resolution (under /api/v1/properties/{slug}). PostgreSQL regression covers invalid proof, cross-property access, suspended/invited identities, replay, conflicting decisions, new resolution cycles and restricted grants. New revision requires CI and hosted migration acceptance; no frontend or production changes.

### Verification addendum — 2026-11-26
- AI reconciliation commit 934f09aaf02140be65d6da51581690eb7b79af12: Actions runs 45844557230 and 45844557600 completed successfully.
- Guest resolution commit 6c00df4e97d9b66eff978f0a297a0a57d1eeca8a: all four jobs in run 45844790929 passed; separate restore run 45844791246 passed. This supersedes the pending CI note above.
- Hosted staging project xfxqlcmsfkbvbybkrppq: before migration 047, properties, guest cases and case control events each counted zero. Applied the exact committed migration 047 in the existing private worthkind_flow schema. Postflight confirmed 79/79 ordinary Flow tables with forced RLS, zero anon/authenticated SELECT grants, and no anon/authenticated EXECUTE grants on the four new functions. Only wf_guest_api can invoke receipt read/decision functions; only wf_operations can invoke the staff read function; neither role can invoke the internal snapshot helper directly. No real data or credentials changed.
- Hosted API process and end-to-end guest journey remain unverified. No production deployment, live inference or financial transactions performed. All three engineering PRs remain unmerged.

## 2026-11-26 — Deferred model candidates and staff property discovery
- Added docs/AI_MODEL_SHORTLIST.md. Candidate research only; Modal activation explicitly deferred, no model selection hard-coded or external resources provisioned.
- Migration 048 and GET /api/v1/staff/properties provide paginated identity-scoped active and invited memberships. Invited state is not an access grant. Revoked memberships, suspended identities, inactive properties and unverified organizations are omitted. Existing per-operation authorization remains authoritative. Added signed-token PostgreSQL/API regression coverage. CI and hosted migration acceptance pending; frontend integration not changed.

### Verification addendum — migration 048
- Commit 70465f7c868f6c94a66aef425f1ab1d2f550cacc: backend runtime run 45853509689 and database recovery run 45853509658 passed. Exact migration 048 applied to existing staging xfxqlcmsfkbvbybkrppq. Verified wf_operations EXECUTE only (anon/authenticated denied), unknown subject returned zero rows. Hosted HTTP acceptance pending.

## 2026-11-26 — Reception handovers
- Migration 049 and staff endpoints /handover-recipients, /handovers, /handovers/{id}/decision (under /api/v1/properties/{slug}/staff) persist encrypted notes and optional same-property active case links. Recipient acknowledgement only; sender/manager cancellation; idempotent create and decision, serialized terminal transitions, audit trail. No change to actual case assignment; use existing transfer command separately. No claim of external notification or scheduled shift attendance. Recipient selection limited to active reception roles; paginated UUID cursor, optional pending-only filter. Signed-token PostgreSQL regression added; CI and hosted acceptance pending. Frontend integration separate.

### Verification addendum — migration 049
- Functional commit 1ce8da8111aea0952fc08f0165a34da3f09d593b: all four jobs in backend run 45854565329 and separate database recovery run 45854565356 passed. Applied exact committed migration 049 to the existing staging project xfxqlcmsfkbvbybkrppq. Verified 80/80 ordinary Flow tables forced RLS; zero direct anon/authenticated table grants and zero EXECUTE grants for both client roles on the four handover functions; wf_operations has the intended EXECUTE grants. Handover table empty; no real staff or guest data inserted. Security advisor INFO for intentionally policy-less private tables reflects default deny architecture; shared-project findings outside Flow not modified. Hosted HTTP and frontend acceptance, notification delivery and release merge remain unverified.

## 2026-11-26 — Native management and financial evidence reports
- Migration 050 adds owner/manager operational snapshot and owner/manager/finance payment evidence summary. Real persisted property counts for reception, overdue work, rooms, native stays, holds, dining, stock, handovers, venues and pending/failed outbox. Financial summary separates test/live and currency, includes only independently verified recorded provider transaction evidence and processed refunds, returns exact minor units as strings. Not a profit, revenue or bank settlement report; no external PMS coverage or historical trend series. No live provider calls. Signed-token PostgreSQL regression tests cover role/tenant boundaries, zero state, pending payment exclusion, partial/full refunds and currency/mode separation. CI and hosted migration pending.

## 2026-11-26 — Guest event and recruitment status
- Migration 051 adds receipt-scoped paginated venue and application tracking, and idempotent withdrawal of submitted/reviewing/shortlisted applications. No cross-case metadata or internal application notes returned. Venue creation retry now returns recorded current state rather than hardcoded requested. Withdrawal is a workflow state, not deletion of personal information; accepted event cancellation and application retention remain separately governed. Tests verify same-case proof, cross-property denial, no duplicate audit and no staff progression after withdrawal. CI and hosted acceptance pending.

### Verification addendum — migrations 050 and 051
- Management reporting commit 863ff53e9a957bd0b01a5c6191a51eed07ac8708: runs 45862339081 and 45862338933 completed successfully. Guest department tracking commit 8a64c6e28a0a395c406040b3df72f0cca0d27e2b: all four backend jobs in run 45862486786 and separate recovery run 45862486631 completed successfully. Exact migrations 050 and 051 applied to existing staging project xfxqlcmsfkbvbybkrppq. Verified the two reporting functions are executable by wf_operations, four guest tracking/withdrawal functions by wf_guest_api, with no anon/authenticated EXECUTE for any of these six. Hosted postflight 80/80 forced RLS tables, zero direct anon/authenticated table grants. Advisor reports INFO for 75 intentionally policy-less private tables, no Flow finding in the anon SECURITY DEFINER executable warning. No provider calls, model activation, production deployment or customer data changes. Hosted HTTP acceptance and frontend integration remain unverified.

## 2026-11-26 — Staff shift attendance
- Migration 052 adds self-only shift check-in/out with server timestamps, check-in during scheduled window, serialized and idempotent transitions, audit and cancellation guard. Owner/manager/HR can report scheduled shifts and recorded attendance, other staff see only their own. No location proof, payroll calculation or manual correction workflow claimed. Signed-token PostgreSQL test added. CI and hosted acceptance pending.

## 2026-11-26 — Guest dining orders
- Migration 053 enables receipt-scoped order creation and history using authoritative menu prices and the existing kitchen state machine. Guest actor recorded explicitly, not a fabricated staff identity. Room service requires native checked-in occupancy linked to the same booking case; food cases may order without a room. No automatic payment or POS claim. Regression covers receipt, room denial, price, replay, state visibility and tenant isolation. Positive native room service acceptance and hosted HTTP remain pending; CI pending.

## 2026-11-26 — Staff leave requests
- Migration 054 adds self-service leave, independent owner/manager/HR decisions, withdraw before decision and manager cancellation before start. Approved leave blocks overlapping scheduled shifts and requires preexisting shifts resolved before approval; no payroll or entitlement calculation. Request and decision replay is idempotent and audited. Signed-token PostgreSQL/API regression added; CI and hosted acceptance pending.

## 2026-11-26 — Platform B2B CRM
- Migration 055 creates separate platform CRM runtime/admin roles (not hotel ownership), explicit operator provisioning/revocation, prospect deduplication by operator-supplied account key, encrypted contact, evidence-backed consent and revocation, revisioned/idempotent sales stage changes and pagination. No automatic outreach, public waitlist, contract signature, attribution or billing claimed. Consent must precede waitlist/pilot stage; closing or revocation disables outreach. Dedicated runtime login and operator enrollment required for hosted use. PostgreSQL/API regression added; CI and hosted acceptance pending.
