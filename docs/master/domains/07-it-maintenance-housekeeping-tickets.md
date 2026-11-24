# Domain 07 — IT support, maintenance and housekeeping ticketing

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Separate draft PR #31 adds local IT/hotel ticket lifecycle, history, due times and tests; not production-staff identity or notifications. **Implementation stage:** M1–M2. **Accountable workstream:** Hotel IT/operations + backend/frontend.

## Hotel/customer job and root cause to validate

Make technology outages, broken AC, room cleaning, repairs and guest support requests accountable to real departmental staff.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Reception case, verified in-stay guest, internal staff, automated maintenance alert where authorized.
- **UI/UX screens and controls:** Ticket creation and filters, department queue, claim, start, notes, SLA/overdue, reopen, manager escalation, inventory/asset association and attachments.
- **Primary workflow:** Incident → triage category/severity → open scoped ticket → assigned employee acknowledges → progress and evidence → supervisor escalation if overdue → completion verified → guest status/reopen.

## Domain data and authority boundary

- **Proposed data entities:** service_tickets, ticket_history, ticket_assignments, staff_availability, service_assets, priority_policies, ticket_outbox, escalation_events.
- **Source-of-truth / authorization invariant:** Only authorized staff own/update tickets; hotel defines staffed hours and severity; model suggestions cannot declare issue resolved. Pending event is not a delivered staff alert..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

No staff on shift, wrong department, recurring fault, rejected handoff, duplicate event or notification outage → reassignment/escalation and intact audit.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

Tenant denial, simultaneous claim, in-progress/resolve rules, recovery, priority windows, overdue escalation, note redaction and evidence checks.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **02,08,13,14**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
