# Domain 04 — Reception, reservations and availability

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Enquiry and staff claim prototype PR #2; Hotel OS separately has availability adapter code, not yet an authorized Worthkind Flow multi-hotel integration. **Implementation stage:** M1–M3. **Accountable workstream:** Reception domain backend + hotel reservations manager.

## Hotel/customer job and root cause to validate

Let reception own incoming stay requests and provide authoritative inventory, correct rates, alternatives and cancellations.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Direct guest enquiry, reception desk, authorized PMS/CRS/booking engine, channel adapter.
- **UI/UX screens and controls:** Reception queue, claim/assign, availability calendar, property/room filters, guest status, exceptions, handover notes and source reservations.
- **Primary workflow:** Guest stay dates and party size → tenant + booking rights check → query PMS or create enquiry → staff claim → verified quote/response → reservation coordinator only after integration and guest approval → audit/handover.

## Domain data and authority boundary

- **Proposed data entities:** enquiries, case_assignments, availability_quotes, booking_requests, room_type_refs, pms_sync_cursor, staff_handoffs.
- **Source-of-truth / authorization invariant:** Only PMS/hotel-authorized booking engine can assert availableRooms/rate, cancellation conditions or confirmed reservation; no manual receptionist click can fabricate external PMS state..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

PMS down/overbooked/stale rate, no staffed receptionist or duplicate enquiry → honest pending case, safe retry and escalation.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

Date/occupancy boundaries, concurrent holds, timezone, source-expiry, outage fallback, reservation privacy proof and claim races.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **02,03,05,08,13,14**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
