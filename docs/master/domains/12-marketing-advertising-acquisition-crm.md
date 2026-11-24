# Domain 12 — Marketing, advertising, customer acquisition and CRM

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Hotel waitlist research and dev-only consent form in PR #29; Hotel OS has separate marketing dashboard/code, not verified linked to Flow. **Implementation stage:** M0–M3. **Accountable workstream:** Founder/sales + growth engineering + privacy.

## Hotel/customer job and root cause to validate

Acquire hotels as B2B clients and help hotels measure lawful guest acquisition without fabricated bookings or unwanted outreach.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Permission-based sales outreach, hotel early access landing, hotel-owned campaigns, partner referrals, approved ad/analytics API.
- **UI/UX screens and controls:** Worthkind pipeline, follow-up reminders, explicit lead consent, pilot agreements, hotel marketing overview, tagged campaigns, sourced conversions and opt-out.
- **Primary workflow:** Find relevant hotel → verify entity and decision-maker → discover specific pain → explicit opt-in → product demo → nonbinding pilot → measured outcome → contract. Guest ads: consented attribution → actual hotel lead → source-verified booking outcomes..

## Domain data and authority boundary

- **Proposed data entities:** prospect_accounts, prospect_contacts, sales_activities, consent_events, pilot_interest, campaigns, attribution_events, marketing_optouts, customer_acquisition_costs.
- **Source-of-truth / authorization invariant:** A listing or answered call is not a waitlist signup; a click or enquiry is not booking revenue; promotional outreach requires proper consent and platform rules..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

Bad contact data, unavailable buyer, duplicate branch, consent withdrawal, unattributed booking, ad API outage → honest unknown/no-contact state.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

Pipeline counting, duplicate hotels, opt-in/opt-out, marketing role restrictions, webhook attribution dedupe and no PII in GitHub.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **01,02,10,11,13,14**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
