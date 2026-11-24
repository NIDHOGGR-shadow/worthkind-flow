# Domain 10 — Hotel management, analytics, revenue and reporting

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Hotel OS has marketing/report API tests; Worthkind Flow lacks proven multi-hotel operational and financial reporting. **Implementation stage:** M2–M4. **Accountable workstream:** Data/finance engineering + hotel manager.

## Hotel/customer job and root cause to validate

Provide owners real visibility into leads, occupancy/booking sources, staff response, open tickets, guest outcomes, cost and performance.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Source events from hotel operations/PMS/PSP, consented marketing attribution, staff and admin dashboards.
- **UI/UX screens and controls:** Executive KPI overview, property switcher, booking/enquiry conversion, ticket/SLA reports, dining, cost/usage, source links, reconciliation exceptions and exports.
- **Primary workflow:** Ingest tenant-scoped source events → dedupe/validate → reconcile to PMS/PSP → compute reported period metrics → authorise per-role aggregation → owner drills into exceptions → corrective action.

## Domain data and authority boundary

- **Proposed data entities:** metric_definitions, event_facts, source_attribution, occupancy_metrics, finance_reconciliations, per_tenant_usage, reporting_snapshots, report_exports.
- **Source-of-truth / authorization invariant:** Hotel gross booking value must never be conflated with Worthkind subscription revenue; bookings require PMS truth and revenue requires finance source. Staff performance must have lawful and fair access policy..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

Missing status events, partial provider billing, stale data or wrong property filter → show last updated timestamp, confidence/source and missing-data warning, not false precision.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

Cross-tenant aggregate denial, source/reference trace, dedupe, currency and timezone, accounting period, access restrictions and report totals parity.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **02,04,05,07,08,11,12,13,14**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
