# Worthkind Flow v5 — Architecture decision record

**Scope:** multi-tenant hospitality AI and operations infrastructure. **State:** approved design proposal, not proof of live PMS, payments, WhatsApp, voice, AI model, or food-dispatch integration.

## What problem are we solving?

Hotels often handle enquiries, reservations, staff tasks and post-stay communication in disconnected channels. Worthkind Flow aims to preserve guests' choice of direct service, human help or optional AI, while making permitted work trackable and verifiable.

**Primary proof of value:** hotel-approved enquiries that reliably become acknowledged staff cases and (only when a PMS integration is authorized and proven) actual reservations. We measure enquiry-to-case completion, time to staff acceptance, resolved requests, source-verified bookings, cost per resolution and failures.

## Trust boundaries

1. **Public hotel resolution** maps a verified property slug/domain to a tenant. This identifies the property; it does **not** authenticate a guest.
2. **Guest proofing** uses per-conversation secrets or an authenticated booking reference before revealing private details. Never rely on room number or name alone.
3. **Staff authentication and RBAC** restricts finance, reception, housekeeping, HR, procurement and managers by tenant, property and role.
4. **Provider ingress** is separate from guest ingress: signed messages and payment/PMS callbacks require signature verification, replay controls, tenant routing, idempotency, error handling and rate limits.
5. **Scoped knowledge** is indexed by tenant, property, content version, approval and access purpose. Public information cannot expose private rates, staff notes or guest records.
6. **Read and write authorization** are separate. Public FAQs and permitted booking searches can be cheap, but writes require domain-specific authorization and explicit confirmation when money or another material commitment is involved.
7. **Action policy** lives in backend code, not just prompts. The LLM cannot approve refunds, hire staff, contract vendors or invent payment success.

## Logical modules

- Channel ingress: website widget, direct forms, authenticated staff dashboard, future WhatsApp/voice integrations.
- Auth and scopes: property resolution, guest session ownership, staff RBAC, provider ingress and audit.
- Router: deterministic human/emergency paths first, optional evaluated intent model, clarification as fallback.
- AI concierge: knowledge retrieval, tool selection, grounded response; no unrestricted SQL/API credentials.
- Reservation coordinator: PMS is source of truth; quote, hold, payment, confirmation, failed-payment reconciliation.
- Task orchestrator: human case ownership and SLAs for reception, housekeeping, maintenance and other departments.
- Other domain modules: food/kitchen, careers/HR, suppliers/procurement, events/sales; designed but deferred from first release.
- Communications: event-driven transactional messages, explicit marketing consent and opt-out.
- Analytics: service and conversion metrics with deduplicated ad events; guest and hotel financial metrics kept separate.
- Platform control: tenant onboarding, configuration, usage limits, billing, incident logs and model/prompt version gating.

## Reliability and audit

A domain write, immutable audit record and outbox event must commit in **one database transaction**. A worker publishes pending outbox items with idempotent processing, retry and dead-letter handling. A queue without a transactional outbox is **not** sufficient audit proof.

Webhook order may vary, duplicates will occur, and late payment success after hold expiry may require human reconciliation. Never display `confirmed` on the basis of an LLM answer or browser redirect.

## AI/ML stages

**P0:** deterministic rules for human, safety and domain routing; property-scoped curated FAQ; optional LLM for wording only; fixed evaluation suite for rules, prompts, knowledge and tool schemas. Do **not** use the low-accuracy synthetic classifier for production.

**Later:** production transcripts with proper permissions and privacy controls; human-labeled intent data; compare ML models against rule baseline; shadow deploy; offline and online evaluation; explicit rollback. Speech recognition and text-to-speech are adapters, not separate business authority.

## Platform decisions

Start with one modular FastAPI backend, one PostgreSQL database with scoped access, and background worker/outbox once implemented. Scale services separately only when reliability/throughput justifies it. A pilot hotel must identify its real booking provider and authorize integration. If unavailable, use **enquiry-only** mode rather than pretending to book.

## Non-goals of P0

Live PMS reservations, payment collection, auto refunds, real food delivery, marketing outreach, staff hiring, supplier contracts, production voice, and self-improving models. Each requires independent provider contracts and release gates.

## First release

Guest website → property resolution → direct/AI/human choice → scoped approved FAQ or enquiry → queued staff case → staff claim and response → guest status update → audit. See FLOWS.md and RELEASE_GATES.md.
