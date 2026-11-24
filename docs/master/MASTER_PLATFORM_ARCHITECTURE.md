# Worthkind Flow — MASTER Platform System Architecture

**Version:** 1.0 architecture proposal · **Date:** 2026-11-17 · **Status:** review required; documents are not production deployments.

## Executive decision

**Worthkind Flow is a multi-tenant hospitality operations platform serving hotels and their guests, staff, managers, and the Worthkind team.** It encompasses all **15 agreed product domains**, not one app, WhatsApp integration, AI chat, voice agent or hotel website.

It should begin as a **modular monolith with strict domain boundaries** (one hotel-operations API, tenant-scoped database, outbox workers and adapter interfaces). Split into multiple services only after real tenant scale and operational evidence justify the new coordination cost.

**Product purpose:** help hotels handle guest enquiries, actual reservations when authorized, department work, staff responsibility, and business reporting reliably. The user interface must function through direct forms and people **without requiring any AI**; chat and voice are optional channels.

**First measurable business outcome:** guests can submit a legitimate hotel enquiry, a real authorized hotel employee can own it and respond, and hotel management can see time-to-acknowledgement, resolution and unresolved work. Booking/payments become separate release gates requiring the hotel's actual provider.

## Evidence from exact repositories (not inferred production state)

| Repository and current branch/PR | Observed code or test | Inference that is NOT permitted |
| --- | --- | --- |
| [Worthkind Flow P0 PR #2](https://github.com/NIDHOGGR-shadow/worthkind/pull/2) (draft; base main) | FastAPI local SQLite enquiry queue, tenant-scoped synthetic properties, direct/human path, public demo FAQ, receipt tokens, audit/outbox and tests; production guard blocks launch | Cannot claim real hotel enquiries are being accepted or bookings confirmed |
| [Service tickets PR #31](https://github.com/NIDHOGGR-shadow/worthkind/pull/31) (draft; base PR #2 branch) | Internal IT/housekeeping/maintenance/reception ticket states, history, due clock, idempotency, development dashboard and tests | Not a deployed ticketing system with employee accounts, live alerts or approved SLAs |
| [Waitlist PR #29](https://github.com/NIDHOGGR-shadow/worthkind/pull/29) (draft; base PR #2 branch) | Development-only signup/withdrawal preview; research ledger and opt-in policy | Screening a prospect is not a waitlist signup; public CRM hosting is not ready |
| [WhatsApp design PR #33](https://github.com/NIDHOGGR-shadow/worthkind/pull/33) (draft; base PR #2 branch) | Channel-specific diagrams, policy and adapter audit | Not a connected hospitality WhatsApp account |
| [Hotel OS](https://github.com/NIDHOGGR-shadow/hotel-os) (separate repository) | \`server/public-booking.js\` implements date validation, Supabase-based availability RPC and Paystack hosted checkout initiation; \`tests/public-booking.test.mjs\` includes mocked source checkout/amount validation; webhook files exist | Not automatically a generic PMS connector or proof that a particular real hotel has successfully processed a booking |
| [Zuvamo / verodesk](https://github.com/NIDHOGGR-shadow/verodesk) (separate repository) | Existing web/voice/chat/WhatsApp adapters, tools and tests designed around its own tenant/business environment | Not already integrated with Worthkind Flow hospitality tenant, content, roles or financial truth |

A draft PR and passing synthetic tests are **code-level progress**, not signed hotels, production operations or verified customer outcomes. The first commercial checkpoint has 106 screened physical-property candidates, but **0 explicitly opted-in waitlist hotels, 0 interviews and 0 written pilot commitments** in its evidence ledger; see [commercial Goal Setting checkpoint](https://github.com/NIDHOGGR-shadow/worthkind/blob/feat/worthkind-flow-waitlist-pilot/projects/worthkind-flow/planning/acquisition/GOAL_CHECKPOINT.md) on its dedicated branch.

## 1. Fifteen domains: role, scope and realistic status

| # | Domain | Owner | Current source status | First actionable next step |
| --- | --- | --- | --- | --- |
| 01 | [Guest/customer journey and UI/UX](domains/01-guest-journey-ui-ux.md) | UX + product | Development reference | Mobile/keyboard direct-to-case E2E |
| 02 | [Hotel registration, onboarding, multi-tenancy](domains/02-hotel-onboarding-multitenancy.md) | Platform/security + founder | Synthetic tenants only | Verified property, domain, owner and invite model |
| 03 | [Hotel website, rooms, services, content](domains/03-website-rooms-services-content.md) | CMS/frontend + hotel | Separate site; demo public FAQ | Approved/versioned hotel content CMS |
| 04 | [Reception, reservations, availability](domains/04-reception-reservations-availability.md) | Reception/backend | Local enquiry queue, separate Hotel OS | Responsible staff, availability/PMS capability discovery |
| 05 | [Booking, payment, confirmation, reconciliation](domains/05-booking-payment-confirmation-reconciliation.md) | Finance/integrations | Separate Hotel OS checkout source/tests | Define real PMS/PSP contract; verify sandbox before launch |
| 06 | [Restaurant, kitchen, room service, delivery](domains/06-dining-kitchen-room-service-delivery.md) | Hotel F&B + backend | Design | Manual dining enquiry and kitchen approval state |
| 07 | [IT, maintenance and housekeeping tickets](domains/07-it-maintenance-housekeeping-tickets.md) | Hotel IT/operations | Draft development service desk | Connect real user/role identity and shift escalation |
| 08 | [Staff, departments, roles, schedules, approvals](domains/08-staff-departments-roles-schedules-approvals.md) | Security + hotel manager | Shared dev keys only | Invited identity and scope-based RBAC |
| 09 | [Chat AI, voice AI, knowledge and ML](domains/09-chat-voice-ai-knowledge-ml.md) | AI/ML + approved hotel content | Existing agent repo separate | Adapter boundary; rules-only fallback and evaluation |
| 10 | [Hotel management, analytics and revenue](domains/10-hotel-management-analytics-revenue.md) | Data/finance + hotel manager | Separate marketing reports only | Source-labelled case/SLA and usage metrics |
| 11 | [Worthkind engineering, admin, billing, support](domains/11-worthkind-platform-engineering-billing-support.md) | Worthkind platform | Engineering plans/reference | Tenant support and approved subscription/cost model |
| 12 | [Marketing, ads, customer acquisition, CRM](domains/12-marketing-advertising-acquisition-crm.md) | Founder/growth | Research + dev waitlist PR | Real opt-in evidence; no fake conversion |
| 13 | [Security, auth, infrastructure, recovery](domains/13-security-auth-infrastructure-reliability.md) | Security/SRE | Local tests; production blocked | PostgreSQL tenant policy, secret handling and reliable workers |
| 14 | [Integrations, notifications, channels](domains/14-integrations-notifications-channels.md) | Integrations/SRE | Adapters in separate app, channel design | Verified provider abstraction and audit/status truth |
| 15 | [Events, careers, suppliers and hotel operations](domains/15-events-careers-suppliers-hotel-business.md) | Hotel sales/HR/procurement | Design | Department intake and privacy/approval boundaries |

## 2. The complete systems map

See [whole-platform diagram](diagrams/01-whole-platform.mmd). The five layers:

1. **Experience:** branded hotel website, mobile guest screens, direct forms, staff ticket/case board, owner/finance dashboard, Worthkind B2B and support console; voice, text and messaging adapters.
2. **Identity and policy:** verified hotel/organization, property, guest scope, employee memberships and role, provider signature, purpose/consent, approval and spend limits.
3. **Business/domain services:** reception/enquiry, rooms/catalog, availability/booking, payment exceptions, dining, hotel service tickets, staffing/approvals, events/HR/procurement, marketing.
4. **Shared platform:** tenant-isolated relational data, transactional audit/inbox/outbox, background workers, event/usage metrics, knowledge index and AI release registry.
5. **External authorities:** approved hotel PMS/CRS, finance/payment providers, POS/kitchen, courier, phone/messaging, email and ad systems; Never trust an integration without an approved contract and provider-verifiable result.

**No central "agent brain" owns hotel operations.** A model can propose an action, but the domain handler authorizes and records it under verified hotel and customer state.

## 3. Seven cross-cutting workflows

**A. Hotel onboarding:** legal hotel/manager proof → organization/property record → verified domains and business hours → staff invitations/departments → approved public policies and services → explicit integration grants → synthetic test → secure staged activation → incident/usage monitoring → offboarding.

**B. Guest direct path:** hotel-branded page → resolve property → no-AI option → enquiry/service request → dedupe/receipt → real staff queue → acknowledge/work/resolve → truthful status → audit/report.

**C. AI-assisted path:** optional chat/voice → tenant+purpose scope → emergency/human override → approved content or typed proposed domain action → backend policy and guest confirmation → authoritative result → response or human abstention. Provider outage must not block direct service.

**D. Reservation and money:** PMS-backed quote → guest terms approval → optional provider hold → secure PSP checkout → signed+server-verified payment → idempotent PMS booking → confirmation. On ambiguity, hold as finance exception, not "paid and booked."

**E. Staff/departments:** authorized employee/guest request → category/priority → department and shift-aware owner → acknowledgement → work status and evidence → supervisor escalation → resolution/reopen → management reporting.

**F. Outbound/integrations:** business state + audit + outbox transaction → authenticated, policy-checked worker → provider accepted → provider status callback → receipt/reconciliation → guest/staff view. "Accepted" is not "delivered".

**G. Hotel contract/value:** relevant prospect → discovery with real pain → explicit contact opt-in → demo → nonbinding pilot interest → approved operator/metrics → controlled pilot → evaluate actual results/cost → commercial agreement or stop.

## 4. Human-centered UI/UX architecture

The [personas map](diagrams/08-platform-personas-ui.mmd) defines five front-end products sharing a design system:

- **Guest experience:** home, rooms/services, availability or enquiry, checkout only if authorized, guest request tracking, manage booking, dining/events, policies, support and always-visible human path.
- **Reception/department workspace:** scoped inbox, conversation ownership, cases and tickets, assignments, response templates, reservations lookup and handover. IT, maintenance, kitchen, HR and finance see only approved work.
- **Hotel management:** property configuration, staff roles/shifts, content approval, service policy/SLA, operational performance, verified bookings and finance exceptions, costs.
- **Worthkind operations:** partner onboarding, agreements, product plans, tenant health, subscriber billing, service desk, feature flags and consented account support.
- **Engineering/QA:** sanitized traces, provider event retries, release matrices, model/prompt evaluation, incident/rollback, logs and cost limits.

**Responsive UI** begins with explicit status clarity, keyboard/screen-reader operation, low-bandwidth recovery, consistent authentication and no unactionable "contact support" promises.

## 5. One data and integration contract

See [Data and API Contracts](DATA_AND_API_CONTRACTS.md) for proposed entities, typed commands, events, authority rules and failure states.

Every privileged action needs **tenant identity + actor authorization + explicit purpose + idempotency + evidence of result**. Every transaction that changes a business state needs its audit and pending notification committed atomically. External payment and hotel PMS status remain separate verifiable records until reconciliation.

Hotel gross booking value is **not** Worthkind recurring revenue. Conversion clicks are **not** source-confirmed bookings. Chat "resolved" is **not** verified staff completion. A phone number or hotel slug is **not** a password. A webhook HTTP 200 is **not** proof that a guest saw a message.

## 6. Production software and risk decisions

- **Initial application structure:** modular FastAPI or equivalent domain backend, PostgreSQL with enforced tenant policy, direct HTML/React/Flutter as appropriate for each user surface, one migration pipeline and independently running durable worker. Do not create 15 independent microservices at pilot stage.
- **Authentication:** invite-only staff accounts with least privilege, signed-in hotel managers, separate Worthkind internal roles and guest proof-based private record lookup.
- **Provider credentials:** hotel-owned business authority, encrypted per-provider secrets, signing and rotation, scoped callback ingress. The customer's bank/PMS/payment provider always authorizes its own side effects.
- **AI:** existing agents can be adapters. Keep deterministic human and emergency rules, scoped knowledge approval, constrained typed tools, model/eval version gates and tenant spend ceilings.
- **Privacy/compliance:** Nigeria Data Protection Act (as applicable), hotel-controller responsibility, informed consent for communications, purpose limitation and deletion/retention policies; reviewed contracts before collecting live hotel guest data.
- **Reliability:** backup/restore, inbox/outbox replay, dead-letter alarms, per-tenant kill switches, operational hours, incident owner and no fake "always available" claim.
- **Operations cost:** separate messaging/voice/model usage, platform infrastructure, subscription invoices and hotel payment/revenue reports.

## 7. Measurable release gates, not current claims

**Gate 0 — scope:** pilot hotel and authorized owner agree what specific manual failure we are testing, with baseline counts and source system.

**Gate 1 — identity:** no unauthorized cross-tenant access, invite/role permission coverage and verified customer privacy proof.

**Gate 2 — human first:** at least 20 scripted guest enquiries (direct and AI-off), 20 staffed handoffs, one unclaimed-escalation test set, outcome recorded and independently checked.

**Gate 3 — durability:** deliberate power/process failure and duplicate webhook tests show no lost committed business record, no unaudited state and no duplicate charge or ticket.

**Gate 4 — UI/accessibility:** mobile 320/390/768/desktop, keyboard/screen reader, interrupted network, truthful status and human route.

**Gate 5 — knowledge/AI:** at least 100 real hotel-approved FAQ and unsafe-prompt fixtures before enabling the model, with rollback if the grounded rule baseline is better.

**Gate 6 — authorized booking:** only after actual PMS and PSP integration with expiry, idempotency, signed verification, amount/currency, provider booking ref and finance exception tests.

**Gate 7 — live service:** staff shift coverage, owner-approved SLAs, privacy/security review, call/message provider permission, monitoring and rollback signed off.

These are **proposed acceptance criteria**, not test results; actual counts must be recorded in CI/pilot run reports.

## 8. Implementation strategy

[Implementation roadmap and RACI](IMPLEMENTATION_ROADMAP.md) prioritizes: scope and buyer validation → tenant/staff security → direct guest-to-human service → trustworthy tickets/notifications → hotel CMS and analytics → optional agents → PMS/payment → dining/events/HR/vendors → multi-property operations.

### Why not build all 15 simultaneously?

The bottleneck is not the number of screens or AI models. It is the **real ownership and authoritative integrations** behind them. Without staff roles and a hotel-owned process, notifications go nowhere; without a PMS, a booking screen cannot truthfully reserve inventory; without a consented hotel, marketing and real guest data are premature.

**Recommended first complete vertical slice:** one hotel + direct guest enquiry + reception/IT staff ticket + accountable claim/response + delivery evidence + owner status dashboard, running with agents disabled and synthetic data initially. This proves the shared platform works and provides the control plane to add later modules safely.

## Existing reference docs

- [v5 design record](../ARCHITECTURE_V5.md) and [existing flows](../FLOWS.md) remain valid as the first-slice design; they are a **subset** of this master map.
- [Non-AI ticket build plan](https://github.com/NIDHOGGR-shadow/worthkind/blob/feat/worthkind-flow-service-tickets/projects/worthkind-flow/planning/NON_AI_BUILD_PLAN.md), draft PR #31, is a separate code path on top of the foundation branch.
- [Waitlist Goal Setting work](https://github.com/NIDHOGGR-shadow/worthkind/blob/feat/worthkind-flow-waitlist-pilot/projects/worthkind-flow/planning/acquisition/GOAL_CHECKPOINT.md) is on draft PR #29, not merged into this architecture.
- [WhatsApp channel design](https://github.com/NIDHOGGR-shadow/worthkind/blob/feat/worthkind-flow-whatsapp-architecture/projects/worthkind-flow/docs/whatsapp/README.md) is a **subordinate channel design** on draft PR #33.
- [Hotel OS](https://github.com/NIDHOGGR-shadow/hotel-os) and [Zuvamo/verodesk](https://github.com/NIDHOGGR-shadow/verodesk) are independent codebases to audit and adapt, not implicitly merged.

**The next decision is whether the user wants to review the master design first or explicitly authorize implementation of M1 production-grade tenant/RBAC and human-first workflows.**
