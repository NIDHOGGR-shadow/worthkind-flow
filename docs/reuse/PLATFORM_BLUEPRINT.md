# Worthkind Flow — integration blueprint and dashboard route contract

**Status:** proposed implementation contract, not deployed capabilities. Complements, rather than replaces, docs/master/MASTER_PLATFORM_ARCHITECTURE.md and its 15-domain design.

## The product in one sentence

Worthkind Flow is a multi-hotel subscription platform that lets each hotel manage a branded guest experience, staff workflows and optional paid AI agents, with verifiable reservation/payment authority, usage ceilings and a human fallback.

## Five user-facing surfaces

1. Worthkind sales and customer onboarding (marketing, comparison, sign-up, commercial agreement).
2. Hotel owner / manager console (configuration, content, reservations, operations, agents, finance and subscriptions).
3. Hotel employee workspace (front desk, case/ticket queue, housekeeping, dining, events and handoff).
4. Guest hotel-branded website, mobile-friendly forms, chat widget or voice channel; human path remains.
5. Worthkind internal support/engineering console (tenant health, incidents, billing exceptions, sanitized events, audits and release switches).

## Suggested route map

| Surface | Proposed route | Purpose | Authority |
| --- | --- | --- | --- |
| Public | / | Worthkind Flow product | public |
| Public | /features, /pricing, /demo, /contact | What is included; explicit quoted vs metered price | public |
| Account | /login, /onboarding | Sign in; verify property/owner; invite staff | identity service |
| Owner | /app/overview | Cases, SLA, arrivals, revenue with each source labelled; no invented numbers | hotel-scoped read |
| Owner | /app/agents, /app/agents/new, /app/agents/install | Assistant configuration, channel activation, safe embed preview | subscription + hotel manager |
| Owner | /app/knowledge, /app/content, /app/website | Hotel-approved material and branded pages | scoped editors/approval |
| Owner | /app/rooms, /app/reservations, /app/payments | Source-labelled inventory and verified money state | approved PMS and PSP |
| Owner | /app/inbox, /app/tickets, /app/dining | Human-owned work queue and department handoff | staff scopes |
| Owner | /app/staff, /app/roles, /app/integrations | Invite/role/shift and provider grants | authorized manager |
| Owner | /app/analytics, /app/usage, /app/billing | Reconciliation, agent costs, invoices, consumption and limits | hotel manager/finance |
| Owner | /app/settings, /app/security | Properties, domain ownership, retention, auth, audit | authorized manager |
| Guest | /h/:property, /h/:property/rooms, /h/:property/contact | Branded page and direct service | public, approved content |
| Guest | /h/:property/availability, /h/:property/checkout | Authoritative quote and confirmed provider checkout only | PMS / PSP |
| Guest | /h/:property/requests/:receipt | Privacy-preserving status proof; no enumeration | guest receipt credential |
| Widget | /embed/:publicWidgetId | Branded AI or direct contact widget; public ID is not an auth credential | tenant resolver + entitlement |
| Internal | /internal/tenants, /internal/support, /internal/usage, /internal/incidents | Internal Worthkind operational admin; not hotel owner UI | Worthkind authorized staff |

Paths are design targets, not routes claimed to exist. Names are adjustable at implementation.

## Data and interfaces

Minimum core tables/entities: organization, property, verified_domain, staff_identity, staff_membership, role_permission, subscription, plan_entitlement, agent_configuration, knowledge_revision, channel_installation, message_thread, guest_request, case_ticket, assignment, booking_quote, reservation, payment_attempt, provider_event_inbox, event_outbox, usage_event, tenant_cost_budget, audit_event.

All tenant-owned records use a property_id and an organization_id where appropriate. Never trust those IDs from a client-submitted body as authorization. Repository-wide security review must confirm Row Level Security where PostgreSQL/Supabase is used and service-layer scoped checks everywhere.

Typed adapter contracts:
- HotelPmsAdapter: capability discovery, availability, quote, create/confirm/cancel/query reservation, and staff reconciliation evidence.
- PaymentAdapter: hosted checkout, independently verified callback/transaction, refund, dispute and reconciliation. Separate Worthkind subscription PSP versus hotel guest PSP accounts.
- AgentAdapter: model selection, scoped knowledge retrieval, propose typed actions, run evaluate/abstain, report token/time/cost usage.
- ChannelAdapter: verified ingress, provider event state (accepted/sent/delivered/read/failed when supported), scoped replies and explicit opt-in/out.
- BillingMeter: signed/event-identity deduplication, cost rating, daily/monthly budget and entitlement checks; never expose server secrets to browser.
- EventOutbox: transactional enqueue and retry; observable delivery failures.

## Paid AI agents: purchase-to-embed contract

A hotel may subscribe to a plan and optionally activate paid chat, voice or channel agents. Feature entitlement is server-enforced, not only a hidden button.

Sequence:
1. Verify hotel owner, organization, property and installation domain. Create an audit record.
2. Choose a plan. Display actual recurring fee, any usage charges, limits and cancellation/renewal terms before purchase. No invented plan price.
3. Start checkout through the approved Worthkind payment processor. The payment processor does not automatically own hotel guest bookings.
4. Verify signed provider webhook AND perform independent provider lookup; reconcile amount/currency, reference, customer, interval and plan; enforce idempotency and handle late/out-of-order events.
5. Grant a time-bounded, versioned entitlement only after authoritative subscription state is reconciled; retries and cancellations must revoke or degrade safely.
6. Hotel manager approves agent scope, knowledge content, domains, operating hours, escalation path and spend ceiling.
7. Generate a public widget identifier and domain-limited installation snippet. The snippet contains no secret and cannot choose a foreign hotel or change privileges.
8. Every widget request resolves installation -> property -> active entitlement server-side; enforce rate limit, PII policy, abuse checks, budget and idempotent usage events.
9. Agent answers approved knowledge or proposes an explicitly authorized typed tool; guest approves any side effect. Human/direct form is available if agent is off, out of budget or unavailable.
10. Owner sees active agent, spend, usage by channel, failure/handoff count and billing provenance; suspension/offboarding disables future agent invocation without concealing human support.

Important: Agent answered does not mean booking made, and webhook accepted does not mean provider delivered. The agent cannot independently charge a card, issue a refund, guarantee inventory, promise dining acceptance or hire staff.

## UI composition recommendation

Use a calm, premium, responsive design:
- Left rail: Overview; Guest Inbox; Reservations; Rooms; Dining; Tickets; AI Agents; Knowledge; Website; Analytics; Usage & Billing; Integrations; Staff; Settings.
- Top: active property, alerts with explicit severity, account and global search.
- Overview: six sourced KPI cards, operational trend, occupied/available/maintenance room status, pending work and audit timeline; don't show sample data as live.
- Agents: clearly labelled Enabled/Paused/Trial/Not configured, voice/chat channel, last usage, spend against ceiling, approved domains, install/config button and human handoff SLA.
- Billing: base subscription, metered AI charge, included allowance, rate and spending cap, invoice status; separate hotel guest payment/revenue.
- Owner can turn AI off without breaking booking enquiries or staff support.
- All controls keyboard operable, mobile 320px+, low-bandwidth fallback; error and empty states intentional.

## Build batches and acceptance gates

B0 — preserve draft hierarchy; run existing foundation/test CI; verify no main-site changes.
B1 — original read-only dashboard shell, property context, tenant permissions, explicit provenance labels. No real data.
B2 — real invited staff identities + authenticated property access; direct enquiry -> human case -> ticket -> staff reply -> audit/outbox.
B3 — approved hotel content editor, room catalog, service menus and hotel-branded page builder.
B4 — agent settings and embed widget with human fallback. Begin with deterministic approved FAQ; production AI requires eval, cost guard, tenant controls and model safety.
B5 — Worthkind subscription checkout, server-side entitlements, live metering/invoicing, charge reconciliation, offboarding and spend ceilings.
B6 — PMS/PSP integration for verified guest quote, booking and separate payment reconciliation with refunds/exceptions.
B7 — dining, housekeeping, CRM, events, voice/WhatsApp and multi-property reporting as authorized modules.

Every batch needs: scoped integration test, cross-tenant negative test, adversarial request test, operational rollback, source license/notice ledger and accurate status documentation. B5 and B6 may run in parallel only if payment-domain isolation is independently proved.

## Current implementation distinction

Existing PR #2 is a local synthetic enquiry reference and intentionally refuses production startup; PR #31 is a dev ticketing slice; PR #34 is the master architecture. This document adds an integration selection and UI design target only. It does not make these routes, providers, paid agents or tenant security functional.
