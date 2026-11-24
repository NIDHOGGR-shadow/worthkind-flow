# Worthkind Flow — Integrated Engineering Roadmap, Dependencies and RACI

**Date:** 2026-11-17 · **Status:** proposed work and implementation sequence, not 15 delivered modules. GitHub foundation PR #2, ticketing PR #31, waitlist PR #29 and WhatsApp architecture PR #33 are **separate draft branches**, not merged or production proof.

## Delivery principle

We prioritize **end-to-end, source-verifiable and accountable workflows**, not the largest number of UI screens. Every release must preserve a functioning no-AI guest-to-human path, property-level authorization, and honest pending/confirmed outcomes. Avoid huge platform rewrites and 15 microservices before the first real hotel pilot.

## Workstream roles and project owner

| Role | What they lead | Approval responsibility |
| --- | --- | --- |
| Founder/product owner | Discovery, first hotel, value/price, domain scope, offer, pilot and acceptance criteria | Decides target pain/problem, approves hotel-facing claims and commercial rollout |
| Tech lead/architect | Domain ownership, API contracts, dependencies, code reviews, architecture decisions | Technical design, migrations and release readiness |
| Backend/API engineer | Tenant identity, domain state machines, provider integration, audit, workers | Tested business write contracts |
| Frontend/UI engineer | Guest website/forms, staff/owner/Worthkind consoles, accessibility | Human-friendly mobile and browser E2E |
| AI/ML/voice engineer | Existing chat/voice adapter, content versioning, evaluations and budget guard | Model/tool release thresholds, no AI authority creep |
| QA/security/SRE | Roles/RLS, webhook signature, failure injection, privacy, infra, CI/recovery | Security, rollback, production monitoring |
| Business development | Prospect CRM, calls/meetings, evidence, onboarding | Qualified lead, consent, real pilot documentation |
| Hotel owner/reception/IT/finance/F&B | Real service workflow, staff coverage, data and operational authority | Actual domain truth, case resolution, approved SLAs, PMS/PSP access |

If the team lacks these functions, name that gap and limit deployment. Do not silently assign every job to one engineer or infer availability from historical team size.

## Dependency graph

**D02 tenant onboarding and D08 staff roles** → unlock authenticated internal systems (**D04 reception, D07 tickets, D03 CMS, D10 hotel management**).

**D13 platform security/outbox + D14 verified channel contracts** → make communication, handoff and provider synchronization trustworthy.

**D03 approved hotel content + D04 receptionist workflow + D08 staff** → prerequisite for safe D09 chat/voice AI.

**D04 PMS availability + D05 payment/PMS verification + D13 signing/audit** → prerequisite for actual confirmed reservations.

**D06 dining requires real hotel kitchen/POS; D15 HR/procurement/events requires separate departmental approval**.

**D10 analytics depends on reconciled events from every live domain, D11 Worthkind billing depends on usage/cost truth, D12 campaign conversion relies on consent and verified hotel outcomes**.

## Milestone plan

| Milestone | Module scope | Work products | Exit gate / evidence | External blocker |
| --- | --- | --- | --- | --- |
| **M0: source audit and architecture** | All 15 design | Master docs, 9 diagrams, 15 domain contracts, API ownership, roadmap | Tech review and architecture disagreement log | None for design |
| **M1: trusted hotel + human-first service** | 01,02,03 minimum,04,07,08,13 | Property/org migration, invited staff/RBAC, verified guest receipts, tenant-approved FAQ, human queue, ticket ownership, audit/inbox/outbox worker, responsive screens | Two-property isolation, 20 no-AI journeys and staffed handoffs, outbox crash/replay, E2E, signoff | Named hotel staff and authorization for live launch |
| **M2: customer ops and truthful reporting** | 03,04,07,09 optional,10,11,12,14 | CMS approvals, real notifications with provider receipts, hotel SLA reports, Worthkind usage/cost ledger, consented CRM, optional evaluated AI/voice | Source-labelled metrics, provider callback/retry, opt-out and cost caps, model fallback | Provider credentials and hotel staff policy |
| **M3: source-confirmed reservation/payment** | 04,05,10,13,14 | PMS adapter, real dates/inventory/quote, optional holds, secure PSP, idempotent confirmations and finance exception desk | Hotel-approved sandbox and signed transaction reconciliation, no false booked states | Specific hotel's PMS and PSP permission |
| **M4: F&B and other service modules** | 06,07 extensions,09,15 | POS/kitchen flow, room-service ownership, courier if supported, events/HR/supplier modules, optional structured message forms | Department-approved acceptance/rejection/closure, proper private access | Kitchen, HR, sales, procurement and courier contracts |
| **M5: mature multi-property platform** | All 15 | Multi-branch management, usage billing, backup/restore drills, incident SLO, tenant self-service, model/voice scaling, comprehensive analytics | Independent tenant acceptance, cost/margin data, incident exercises, owner review | Multiple approved active hotels; measured value |

**Milestones are dependency and acceptance groups, not guaranteed calendar estimates.** The commercial waitlist's 20/10/3 target remains independent of feature-completion counts.

## Precise first coding slices (M1), by PR

| PR-sized slice | Backend/data work | Frontend/UX | Test evidence |
| --- | --- | --- | --- |
| **M1-A — tenant foundation** | Organizations/properties/migrations, scoped query layer, sign-in invitations, roles/revocation, approval API | Hotel sign-in, staff invite, property switcher | No cross-tenant read/write under all tested roles; invite/revoke |
| **M1-B — hotel and public content** | Property configuration, public FAQ policy version, content approvals and asset metadata | Hotel onboarding wizard, guest direct form, content approvals | Unknown fact abstains; unauthorized content cannot publish |
| **M1-C — case and ticket engine** | Unified property cases, ticket references, staff claim, reassign and escalation, idempotency, immutable audit | Reception inbox, IT board, staff transfer and guest status | Concurrent claim, human takeover, deadline and retry tests |
| **M1-D — reliable communication** | Atomic outbox, worker leases, signed callback inbox, status receipts, retry/dead letter and redaction | Staff actual delivery status, failure/error queue | Crash/replay, wrong provider signature, accepted≠delivered |
| **M1-E — owner visibility** | Initial source-labelled metrics, owner-scoped reporting query | Open cases, assigned staff, missed SLAs, response time | Accurate totals and 2-property isolation |
| **M1-F — pilot signoff** | Provider/hotel config, data-retention policy, backup and ops runbook | Real mobile/browser accessibility tests, clear no-AI route | Hotel manager and technical release gate, rollback drill |

Do not combine all slices in one giant PR. Keep existing Worthkind movement website's root deployment configuration untouched.

## UX flows and outcome evidence

**Guest:** open property page → choose room/service/human → understand enquiry-only vs live booking → submit request idempotently → see receipt → verified progress → staff/direct callback.

**Reception/IT:** authenticated login → property-scoped task board → claim → departmental owner → respond and close with evidence → reopen if disputed → management sees unresolved work.

**Hotel owner:** verify operational hours and staff roles → approve hotel facts → view staff queue and real service performance → authorize providers → review subscription/usage → offboard safely.

**Worthkind team:** confirm hotel contract → provision isolated property → monitor tenant, costs and incidents → support under explicit permission → bill for agreed service, not claimed hotel booking GMV.

**AI/voice:** optional channel calls the same domain handler, evaluated and cost-bound; cannot skip identity or invent payment, reservation, delivery or employee acceptance.

## Service-level and incident model

Define per-hotel business hours, department coverage, severity and response ownership. The ticket demo's 1/4/24/72-hour examples are **not a contract**. Every unassigned case should have a safe alert target or an honest next-hours fallback.

- **Detection:** source-aware health checks, queue age, failed callback signatures, worker attempts, per-hotel cost spikes, and customer-visible unresolved states.
- **Response:** halt unsafe agent/action via feature flags; retain direct/human service; page the authorized engineer and hotel owner according to runbook.
- **Containment:** isolate affected hotel/credentials and preserve audit evidence.
- **Recovery:** restore database, safely replay inbox/outbox, reconcile provider bookings/payments, validate staff notifications and guest states.
- **Postmortem:** actual root cause, owner, tests, prevention and approval to re-enable.

## Architecture/code review gates

Reviewers must confirm:
1. No changes to root Worthkind movement site, unauthorized production deployment, saved credentials or real customer PII in GitHub.
2. Stable interfaces for organization/property, guest receipt, staff permission, idempotency and provider authority across all modules.
3. Honest status semantics (\`enquiry queued\` vs \`booked\`, \`provider accepted\` vs \`delivered\`, \`sent\` vs \`paid\`).
4. A safe no-AI fallback and human coverage for every channel.
5. Model/prompt versions and test sets isolated from domain finance authorization.
6. Signed callbacks, tenant isolation, consent/retention and independent negative-security checks.
7. Cross-platform accessibility, responsive design and low-bandwidth/error states.
8. Sources of metric truth and no mixing of hotel GMV with Worthkind MRR.

## Founder next week

The founder's main parallel work is **not** to implement the whole stack personally. Call the first source-linked hotel prospects, ask managers about recent missed/late enquiries, actual current software and response shifts, and request a 15-minute process walkthrough. Track explicit permissions in issue #28's private CRM workflow. One willing hotel with a named receptionist, actual process and authority is a stronger input than additional speculative features.

## Open engineering decisions for tech review

- Shared backend and DB choice for all domains (FastAPI reference vs TypeScript/Node Hotel OS integration); propose modular API with well-defined adapters, but do not silently port payment code without review.
- Authentication and RLS strategy for support and chain-group hotel owners.
- Hotel-owned domain, public booking provider, actual inventory and price authority.
- Privacy/controller responsibilities and real consent storage/retention for hotel data.
- Provider options and pricing for voice, SMS, WhatsApp, email, POS, PMS.
- Non-production sandbox integrations and canary/release/rollback ownership.

Links: [MASTER_PLATFORM_ARCHITECTURE.md](MASTER_PLATFORM_ARCHITECTURE.md) · [DATA_AND_API_CONTRACTS.md](DATA_AND_API_CONTRACTS.md) · [nine diagrams](diagrams/) · [15 domain specs](domains/).
