# Worthkind Flow — Full 15-Domain Master Architecture

**One hospitality platform. Not a WhatsApp plan, not a voice-agent-only plan, and not 15 independent applications.**

**Documentation state:** design PR for technical review, dated 2026-11-17. The files do not assert that the modules or hotel integrations are in production.

## Start here

1. [MASTER_PLATFORM_ARCHITECTURE.md](MASTER_PLATFORM_ARCHITECTURE.md) — system scope, the state of source code, overall components, trust boundaries, all domains, UX and release gates.
2. [DATA_AND_API_CONTRACTS.md](DATA_AND_API_CONTRACTS.md) — authoritative ownership, suggested relational entities, endpoint contracts, state machines, idempotency, outbox and integration rules.
3. [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) — team RACI, dependency order, coding slices, release strategy, rollout and review.
4. The domain-specific specs below, and nine editable Mermaid diagrams.

## The 15 agreed domains

| # | Domain | Specification |
| --- | --- | --- |
| 01 | Guest/customer journey and UI/UX | [Read](domains/01-guest-journey-ui-ux.md) |
| 02 | Hotel registration, onboarding and multi-tenancy | [Read](domains/02-hotel-onboarding-multitenancy.md) |
| 03 | Hotel website, rooms, services and content management | [Read](domains/03-website-rooms-services-content.md) |
| 04 | Reception, reservations and availability | [Read](domains/04-reception-reservations-availability.md) |
| 05 | Booking, payment, confirmation and reconciliation | [Read](domains/05-booking-payment-confirmation-reconciliation.md) |
| 06 | Restaurant, kitchen, room service and delivery | [Read](domains/06-dining-kitchen-room-service-delivery.md) |
| 07 | IT support, maintenance and housekeeping ticketing | [Read](domains/07-it-maintenance-housekeeping-tickets.md) |
| 08 | Staff, departments, roles, schedules and approvals | [Read](domains/08-staff-departments-roles-schedules-approvals.md) |
| 09 | Chat AI, voice AI, knowledge retrieval and ML lifecycle | [Read](domains/09-chat-voice-ai-knowledge-ml.md) |
| 10 | Hotel management, analytics, revenue and reporting | [Read](domains/10-hotel-management-analytics-revenue.md) |
| 11 | Worthkind's engineering, administration, billing and customer support | [Read](domains/11-worthkind-platform-engineering-billing-support.md) |
| 12 | Marketing, advertising, customer acquisition and CRM | [Read](domains/12-marketing-advertising-acquisition-crm.md) |
| 13 | Security, authentication, infrastructure, reliability and incident recovery | [Read](domains/13-security-auth-infrastructure-reliability.md) |
| 14 | Third-party integrations, notifications and communication channels | [Read](domains/14-integrations-notifications-channels.md) |
| 15 | Events, careers, suppliers and other hotel business operations | [Read](domains/15-events-careers-suppliers-hotel-business.md) |

## Nine editable architecture diagrams

| # | Diagram | Purpose |
| --- | --- | --- |
| 01 | [01-whole-platform.mmd](diagrams/01-whole-platform.mmd) | Overall platform boundary, tenants, UI and domains |
| 02 | [02-guest-journey-to-accountable-outcome.mmd](diagrams/02-guest-journey-to-accountable-outcome.mmd) | Guest choice, staff ownership and verified outcome |
| 03 | [03-booking-payment-reconciliation.mmd](diagrams/03-booking-payment-reconciliation.mmd) | PMS and PSP source-of-truth sequence |
| 04 | [04-hotel-department-workflows.mmd](diagrams/04-hotel-department-workflows.mmd) | IT, kitchen, housekeeping, HR, events and procurement |
| 05 | [05-knowledge-ml-and-human-control.mmd](diagrams/05-knowledge-ml-and-human-control.mmd) | Rules-first AI, authorized tools and human takeover |
| 06 | [06-infrastructure-incident-and-release.mmd](diagrams/06-infrastructure-incident-and-release.mmd) | Engineering deployment, outage, recovery and incident |
| 07 | [07-data-ownership-and-events.mmd](diagrams/07-data-ownership-and-events.mmd) | Domain data and auditable event relationships |
| 08 | [08-platform-personas-ui.mmd](diagrams/08-platform-personas-ui.mmd) | Guest, hotel staff, hotel owner and Worthkind interfaces |
| 09 | [09-commercial-and-service-value.mmd](diagrams/09-commercial-and-service-value.mmd) | B2B acquisition and real hotel value validation |

## Code branches (reviewed references only)

- [P0 foundation PR #2](https://github.com/NIDHOGGR-shadow/worthkind/pull/2): synthetic hotel enquiry and direct human case code, not production.
- [Hotel waitlist PR #29](https://github.com/NIDHOGGR-shadow/worthkind/pull/29): development-only opt-in prototype and research.
- [IT/maintenance tickets PR #31](https://github.com/NIDHOGGR-shadow/worthkind/pull/31): development staff ticket queue.
- [WhatsApp channel diagram PR #33](https://github.com/NIDHOGGR-shadow/worthkind/pull/33): subordinate communication-channel design, not master platform.
- [Hotel OS](https://github.com/NIDHOGGR-shadow/hotel-os): separate hotel storefront/availability/payment implementation with tests; no automatic multi-tenant Flow integration.
- [Zuvamo / verodesk](https://github.com/NIDHOGGR-shadow/verodesk): separate agent/voice/channel codebase to audit for reuse.

## Non-negotiable product rules

- A guest can request a real human without using any model.
- No property can read another's guest/staff/financial information.
- A provider's accepted message is not verified delivered; a request for a room is not confirmed booked.
- PMS/hotel booking engine authorizes inventory and reservation; PSP/finance confirms money; human staff authorize their own work.
- Every meaningful business write has audit, idempotency and durable follow-up logic.
- No model is a hotel owner, money approver, source of availability, HR hiring officer or kitchen confirmation.
- Original Worthkind movement site and production credentials are out of this PR's scope.

**Next engineering action** after design review: M1 trusted hotel/roles + a complete direct guest enquiry → reception/IT ticket → verified staff reply, with all agents disabled. Grow to bookings, dining, multi-hotel billing and AI/voice only after operational acceptance.
