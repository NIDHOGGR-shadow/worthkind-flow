# Worthkind Flow

**Status: pre-production engineering project.** Worthkind Flow is a modular hospitality automation platform within the [Worthkind](../../README.md) organization repository.

## Purpose

A hotel can embed Worthkind Flow alongside its existing website and booking provider. Guests can use **direct forms, AI assistance, or an actual human**. The system routes verified requests to reception, dining, events, HR and procurement; connects to a hotel's authorized reservation/PMS and payment systems only after those integrations pass contract and security tests. After-stay messaging and advertisements are later modules with explicit consent and cost controls.

**This repository folder does not represent a live hotel booking, payment or food-delivery integration.** Do not promise confirmed room inventory, payments, dispatch or staff acceptance without the authoritative system returning proof.

## First release (P0)

1. Resolve the hotel/property; display direct human and self-service paths even if the AI is down.
2. Answer from **hotel-scoped approved** information or decline and escalate when evidence is missing.
3. Accept a booking **enquiry**, not an unverified booking; collect dates and guest contact details with authorization.
4. Create a human-owned staff case; show queued / accepted / resolved states and notify the guest.
5. Enforce tenant isolation, staff permissions and audited state transitions.
6. Test outage, prompt-injection, duplicate actions, cost ceilings and human bypass before launch.

## Folder layout

- `apps/api/` — FastAPI backend and tests (reference first slice; not production)
- `apps/web/` — optional-AI guest experience
- `docs/` — v5 architecture, flows, security and ML design
- `planning/` — prioritized engineering backlog and acceptance criteria
- `ml/` — rules-first evaluation plan; custom model training deferred
- `.github/workflows/worthkind-flow-ci.yml` (repository root) — scoped CI

## Ownership

- Product owner: Worthkind founder — pilot discovery, roadmap, hotel relationships and release acceptance.
- Technical lead: architecture, code review and reliability.
- Backend/Integrations: tenant access, cases, PMS/payment connectors and audit/outbox.
- Frontend/UX: mobile-first hotel widget, self-service, staff operations.
- AI/ML: grounded answers, eval sets, voice when validated; avoid untested model claims.
- QA/Security: cross-tenant tests, incident recovery and adversarial evaluation.
- Hotel manager/reception: guest-service authority, operating policies and response SLAs.

## Master architecture — all 15 domains

**Start with [the full Worthkind Flow Master Architecture](docs/master/README.md).** It includes the [platform-wide system specification](docs/master/MASTER_PLATFORM_ARCHITECTURE.md), [domain data and API contracts](docs/master/DATA_AND_API_CONTRACTS.md), [phased engineering roadmap](docs/master/IMPLEMENTATION_ROADMAP.md), 15 domain-level designs, and nine editable Mermaid system diagrams.

The existing `docs/ARCHITECTURE_V5.md`, `docs/FLOWS.md` and `docs/RELEASE_GATES.md` still document the **first human-assisted enquiry slice**. They are complementary, not the full platform's scope. Booking, payment, dining, agent channels and operations must pass their own source-of-truth and hotel-authorization gates.

> This is an isolated project folder in the existing Worthkind repo. Do **not** replace the movement website, its API, root package.json, Vercel configuration or application data.

## Research-led dashboard and paid agent design preview

- [Original hotel owner dashboard preview](apps/dashboard-preview/README.md) — dependency-free static HTML navigation covering hotel KPIs, staff work, optional agents and distinct Worthkind billing. Data is visibly synthetic; it is not deployed or connected.
- [Open-source intake and license register](docs/reuse/SOURCE_AND_LICENSE_REGISTER.md) — recommended, license-gated component sources and code-reuse restrictions.
- [Platform integration and routes blueprint](docs/reuse/PLATFORM_BLUEPRINT.md) — hotel/guest/owner/Worthkind interfaces and paid-agent subscription-to-embed contract.
- [Paid-agent guest journey diagram](docs/reuse/diagrams/01-paid-agent-to-guest-outcome.mmd) — hotel verification, entitlement, installation, bounded agent, verified authority and human fallback.

This feature remains a design and source intake package, not production payment, PMS, booking, metering or AI implementation. It does not copy vendor code or touch the existing Worthkind movement site.

## Development delivery-recovery contract (WF-DELIVERY-01)

[Draft PR #70](https://github.com/NIDHOGGR-shadow/worthkind/pull/70) adds a **synthetic SQLite fake-provider** contract with retry/backoff, dead letters, explicit acknowledgement vs fake delivery receipt, an isolated CLI and property-scoped staff read endpoint. Nine isolated FastAPI/SQLite tests passed locally; full combined CI and browser verification are still blocked by [GitHub issue #68](https://github.com/NIDHOGGR-shadow/worthkind/issues/68). **No real guest messages or provider deliveries occur.** See [full development contract](docs/DELIVERY_SQLITE.md).

## Current SQLite SLA attention queue

The hotel operations page has a development **Review deadline queue** action. It shows property-scoped overdue, due-soon and invalid-date tickets from SQLite, without sending or claiming staff alerts. [Draft PR #69](https://github.com/NIDHOGGR-shadow/worthkind/pull/69) contains the implementation; six pure rule checks and seven isolated FastAPI/SQLite assertions passed locally (see `scripts/sla_isolated_smoke.py`), while full API/UI/Chromium CI remains blocked by [issue #68](https://github.com/NIDHOGGR-shadow/worthkind/issues/68). See [SLA behavior and test limitations](docs/SLA_SQLITE.md).

## Continue execution and monitor progress

**[Full project execution checklist](docs/EXECUTION_MASTER_CHECKLIST.md)** tracks all 16 engineering stages and 15 product domains, marking researched, implemented, actually tested, blocked and production-verified conditions separately. It retains the normal web app goal, with SQLite used only for development until Supabase is requested. [GitHub CI blocker #68](https://github.com/NIDHOGGR-shadow/worthkind/issues/68) tracks live Chromium verification where current Actions jobs execute no visible steps.

## Current execution tracker and UI slice

- [Master Build Register](docs/BUILD_REGISTER.md): all 15 hospitality domains, P0-P2 priority queue, UI decisions and production release gates. Statuses distinguish development code and source/CI checks from real deployment.
- [Reception workspace](apps/web/staff.html) (served by the local FastAPI development API at `/staff`): property-scoped case counts, filters, search and existing API claim/reply operations with accessible loading/empty/error states. This is a **development-only interface** using per-property demo keys. It is not a substitute for individual staff authentication or a live hotel.
- [Reception UI tests](apps/web/tests/staff-ui.test.cjs) run in the path-scoped GitHub CI. Source code and tests require CI evidence before they are marked verified.
- [Operational failure/role flow](docs/OPERATIONS_FLOW_AND_TEST_TRACE.md) and [source reuse diligence](docs/UPSTREAM_REUSE_AUDIT_2026-11-19.md) are proposed architecture/selection evidence, not a live feature.

**Owner clarification, 2026-11-19:** continue developing the **normal web-based Worthkind Flow product**, using local SQLite instead of Supabase/PostgreSQL for now. This does **not** mean the final app must be offline. We can implement working UI, APIs, local persistence and integration contracts without provisioning a cloud database. [SQLite development guide](docs/LOCAL_FIRST.md) includes local startup, private demo keys, repeatable fixtures and 24 guest/staff journeys. PostgreSQL/RLS draft PR #49 is parked, not a dependency. Individual staff identities, authorized provider connections and production safeguards remain necessary before real hotel/customer data.

## Reception-to-department handoff (SQLite)

A receptionist can now claim a guest enquiry and create one linked maintenance/IT/housekeeping/reception/dining/billing/general task directly in the same reception queue. Its persisted ticket status is shown on the case card; the department console remains at `/staff/tickets`. Unclaimed/foreign-property cases and duplicate ticket links are rejected by SQLite-backed API rules. No guest name or contact is automatically transferred into the ticket. [Draft PR #64](https://github.com/NIDHOGGR-shadow/worthkind/pull/64), [passing CI run #107](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44581524385). Not deployed.

## Local SQLite hotel knowledge management

[Knowledge review](apps/web/knowledge.html), served at **/staff/knowledge**, supports an unpublished draft, explicit local approval, version history, withdrawal and public guest FAQ preview. Approved facts are read through the same [FastAPI](apps/api/knowledge.py) backend; unapproved/withdrawn content abstains instead of inventing an answer. This is **not** real hotel owner approval or an AI model. [Draft PR #63](https://github.com/NIDHOGGR-shadow/worthkind/pull/63) passed [CI run #102](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44580266898). See [SQLite knowledge guide](docs/KNOWLEDGE_SQLITE.md).

## SQLite-only operational extensions

The development-only Department Tickets console is at /staff/tickets and is linked from the reception workspace. It integrates existing ticketing source work from draft PR #31 into current local SQLite and keeps example SLA hours, local history and pending outbox records distinct from real hotel action. See [local ticketing](docs/TICKETING_LOCAL.md) and [local setup](docs/LOCAL_FIRST.md).

## Source-backed hotel management dashboard

[Operations dashboard](apps/web/operations.html), served at **/staff/operations** by the development FastAPI app, aggregates the current hotel's locally persisted enquiries, departmental tickets, overdue counts and pending internal events. Data is calculated from property-scoped SQLite queries in [operations.py](apps/api/operations.py), not copied from the original static concept. [Draft PR #61](https://github.com/NIDHOGGR-shadow/worthkind/pull/61) passed [CI run #88](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44577901026); no deployment, actual hotel customer or production manager sign-in is implied. Source permissions still use development-only per-hotel keys, and the dashboard deliberately reports no verified PMS/payment/AI metrics.
