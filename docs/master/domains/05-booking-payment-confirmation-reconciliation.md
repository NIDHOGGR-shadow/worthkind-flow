# Domain 05 — Booking, payment, confirmation and reconciliation

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Hotel OS has Paystack/Supabase public-booking code and tests; no proven cross-hotel PMS/payment adapter or live Worthkind Flow transactions. **Implementation stage:** M3. **Accountable workstream:** Payments backend/security + hotel finance/PMS operator.

## Hotel/customer job and root cause to validate

Create real room reservations with exact source quotes, secure full-payment checkout, signed verification and trustworthy confirmations/reconciliation.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Approved guest booking intent, hotel PMS quote, registered payment processor webhook, finance staff.
- **UI/UX screens and controls:** Availability result with fees, terms, secure checkout, pending verification, confirmed booking reference, failed/expired payment recovery and manage reservation.
- **Primary workflow:** Quote by PMS → guest accepts total/cancellation → hold if supported → backend checkout intent → PSP redirect/hosted form → signed callback + server verification → PMS reservation confirmation → idempotent receipt, else finance exception.

## Domain data and authority boundary

- **Proposed data entities:** availability_snapshots, rate_quotes, holds, bookings, booking_events, payment_intents, payment_transactions, payment_inbox, finance_exceptions, refunds.
- **Source-of-truth / authorization invariant:** PSP verifies exact amount/currency/reference; PMS verifies booking ID. Paid but PMS-unknown is an unresolved exception, never a confirmed stay. No card/PIN/OTP collection in chat..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

Late callback, expired hold, duplicate charge, partial provider outage, mismatched amount, wrong tenant webhook → quarantine/reconcile and assigned finance response.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

Provider-signature, wrong amount/currency, replay, idempotent reservation, concurrent inventory, payment success/PMS failure, refund authorization and no false booking.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **02,04,08,11,13,14**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
