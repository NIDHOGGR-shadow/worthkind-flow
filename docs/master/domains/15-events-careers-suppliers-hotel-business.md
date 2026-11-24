# Domain 15 — Events, careers, suppliers and other hotel business operations

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Designed in platform v5; separate Hotel OS event/dining pages exist; no verified Flow HR/procurement/events workflows. **Implementation stage:** M4–M5. **Accountable workstream:** Hotel sales/HR/procurement + frontend/backend.

## Hotel/customer job and root cause to validate

Manage event venue enquiries and quotations, vacancy applications and vendor proposals through controlled departmental ownership and documented approvals.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Public hotel pages, direct forms, event buyers, applicants, suppliers and hotel department admins.
- **UI/UX screens and controls:** Event inquiry planner, meeting rooms/capacity and quote request, staff sales board, jobs portal with HR-only tracking, procurement submissions with safe file access.
- **Primary workflow:** Request and consent → classify events/HR/procurement → validate capacity/eligibility/docs → route to authorized owner → review and approve/decline → record contract or next step → notify and close.

## Domain data and authority boundary

- **Proposed data entities:** event_leads, venue_inventory, event_proposals, hr_vacancies, applications, candidate_consent, supplier_profiles, procurement_requests, contract_approvals.
- **Source-of-truth / authorization invariant:** Only sales may approve event quotes/holds; only HR reads applicant data and decides offers; only procurement/authorized manager signs supplier contracts; AI may not commit..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

No available venue, price changed, unsafe file, sensitive CV, applicant withdrawal, supplier fraud or unapproved terms → restricted review and truthful pending status.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

RBAC/PII separation, event quote and venue availability, supplier upload scanning, duplicate lead, consent/retention and approval chain.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **02,03,08,10,11,13,14**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
