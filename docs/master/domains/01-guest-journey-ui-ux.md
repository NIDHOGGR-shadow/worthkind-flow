# Domain 01 — Guest/customer journey and UI/UX

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Reference guest website and direct enquiry flows in PR #2; actual end-to-end live hotel journeys not verified. **Implementation stage:** M0–M1. **Accountable workstream:** Frontend/UX + hotel product owner.

## Hotel/customer job and root cause to validate

Discover a hotel, compare rooms and policies, ask questions, make a request, choose a human, track what happened, manage a verified booking or a complaint.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Hotel-branded website, mobile browser, future approved messaging/voice, QR/referral links.
- **UI/UX screens and controls:** Mobile-first home, rooms, room details, rates/policies, enquiry/availability, checkout when verified, confirmation, manage booking, service request, FAQ, human contact, accessible status.
- **Primary workflow:** Arrive → resolve hotel domain → choose direct/AI/human path → verify minimal guest context → ask permitted question / create enquiry → get receipt token → staff or PMS source update → accessible status and human escalation.

## Domain data and authority boundary

- **Proposed data entities:** guest_contacts (purpose-scoped), guest_sessions, consent_events, enquiries, booking_links, case_receipts, page_events (consented).
- **Source-of-truth / authorization invariant:** Property resolution never authenticates a guest; guest private records need possession proof or verified login. A click, redirect or LLM output is never booking confirmation..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

No availability integration → enquiry-only. Agent outage → direct forms. Staff unavailable → honest hours and queue. Duplicate submit → idempotent receipt. Weak network → preserve draft/retry.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

320–1440px responsive, screen reader/keyboard, no-AI 20/20, 2-property private read denial, interrupted/repeated submission, translated/error messages, user comprehension of enquiry vs booking.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **02,03,04,07,08,13,14**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
