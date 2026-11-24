# Worthkind Flow — delivery and ownership

Project folder: `projects/worthkind-flow`. This folder is independent of the existing Worthkind movement website, routes and application data.

## P0 — Guest enquiry and human handoff (first)

1. Product/Hotel: pilot hotel and responsible manager; map existing enquiry/booking processes.
2. UX: self-service buttons, optional AI and accessible human help at every stage.
3. Backend: per-property sessions, consent and scoped public content; staff identities and RBAC.
4. Workflow: idempotent enquiries, case assignment, receipt/status and accountable staff reply.
5. Reliability: audit/outbox, observability, error modes and documentation.
6. QA: adversarial, negative tenant and outage test suite; meet release gates.

## P1 — Authorized hotel booking

Only begin after contractual provider access: real inventory, room quotes, holds if supported, secure checkout, reconciliation, webhook verification and notification.

## P2 — Operational departments

Food/kitchen/dispatch, events and meetings, housekeeping, maintenance, careers and suppliers. Each needs departmental ownership, permissions, SLA and provider capability validation.

## P3 — Post-stay, marketing, growth and voice

Consent-based transactional messages and optional marketing, Google Business Profile review invitations, conversion tracking, capped ad spend, measured repeat bookings, locally-evaluated voice channels.

## Roles

- Product owner (founder): customer discovery, budgets, priority, pricing, acceptance and partnerships.
- Tech lead: architecture decisions, design reviews, threat modeling, versioned release gates.
- Backend/integrations: data model, APIs, auth, PMS/payment contracts, outbox and observability.
- Frontend/UX: public hotel integrations, optional agent widget, mobile, staff/owner dashboards.
- AI/ML: intent/knowledge pipeline, prompt and evaluation gating, fallback, later speech and forecasts.
- QA/security/reliability: end-to-end suites, tenant isolation, incident readiness and costs.
- Hotel manager/staff: approved policies, live inventory authority, guest service fulfillment, refunds/HR/contract approvals.

## Non-negotiable

No demo data in production; no public admin registration; no claim of booked/paid/delivered on an unverified status; no AI-only path; no hotel-wide leaked information or cross-tenant access. Preserve the existing Worthkind website.
