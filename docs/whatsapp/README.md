# Worthkind Flow — WhatsApp Architecture Source Pack

**Version:** 2026-11-17 research/design proposal, no live hotel WhatsApp channel connected. Intended as the WhatsApp equivalent of the [USSD Flow research architecture](https://github.com/NIDHOGGR-shadow/SignalBridge) at the level of externally controlled transport, app policy, source-of-truth systems, security, lifecycle, consumer, business, engineering and UI/UX.

The difference: WhatsApp uses Meta's internet-connected Business Platform, not the user's SIM-selected USSD gateway. WhatsApp Flows (plural) are optional interactive in-chat forms, not the channel itself.

## Read these three files in order

1. [MASTER_ARCHITECTURE.md](MASTER_ARCHITECTURE.md) — data, user/provider boundaries, design decisions, source-of-truth contracts, privacy and release gates.
2. [PROCESS_STEP_CATALOGUE.md](PROCESS_STEP_CATALOGUE.md) — **15 processes / 126 proposed steps**, each with reason, failure boundary, accountable role and acceptance measurement.
3. [IMPLEMENTATION_BACKLOG.md](IMPLEMENTATION_BACKLOG.md) — audited code reuse from existing Zuvamo/verodesk, founder and team RACI, phased execution, negative tests, unimplemented blockers.

## 13 editable diagrams

| No. | Diagram | Question it answers |
| --- | --- | --- |
| 01 | [Full system/transport](diagrams/01-system-context.mmd) | How does customer WhatsApp communicate with Meta, Worthkind Flow, staff and hotel systems? |
| 02 | [End-to-end sequence](diagrams/02-inbound-and-return-sequence.mmd) | Exactly what happens to an inbound message, reply and delivery status? |
| 03 | [Hotel WhatsApp onboarding](diagrams/03-hotel-onboarding.mmd) | How does each property connect its own WABA, sender, secrets, permissions and templates? |
| 04 | [Human ownership](diagrams/04-human-handoff-ownership.mmd) | Who owns the chat, when is the AI paused and what happens after handoff? |
| 05 | [Business departments](diagrams/05-domain-business-workflows.mmd) | Booking, food, IT tickets, events, jobs and suppliers: who confirms what? |
| 06 | [Chat AI/ML/voice note](diagrams/06-ai-and-voice-notes.mmd) | How do rule routing, knowledge, AI and transcription work and fail safely? |
| 07 | [Delivery state machine](diagrams/07-message-delivery-states.mmd) | Why Meta accepting a message does not mean the guest received it |
| 08 | [Security and recovery](diagrams/08-security-and-failure-recovery.mmd) | What happens on forged webhook, outage, wrong hotel, unknown outcome or budget limit? |
| 09 | [Customer/staff/admin/engineer UX](diagrams/09-ui-ux-and-five-personas.mmd) | Which interfaces do five user groups see and control? |
| 10 | [Engineering build and release](diagrams/10-engineering-and-release.mmd) | How to build, test, gate and roll out a single hotel channel |
| 11 | [Marketing, consent and unit economics](diagrams/11-marketing-and-money.mmd) | How do ads, referrals, service outcomes, messaging costs and ARR relate? |
| 12 | [Live calls versus voice notes](diagrams/12-whatsapp-voice-call-options.mmd) | Where is the line between asynchronous speech-to-text and the real Calling API? |
| 13 | [WhatsApp Flows form screens](diagrams/13-structured-whatsapp-flows.mmd) | How to collect structured guest request data without pretending a room is booked |

## Important facts from code review

[Verodesk/Zuvamo](https://github.com/NIDHOGGR-shadow/verodesk) already implements WhatsApp via **Meta directly and Twilio**, with media/voice-note parsing and test fixtures. Its current send path incorrectly equates HTTP-accepted with delivered (setting `delivered_at` immediately), and the Meta adapter ignores `statuses[]` delivery/read/failed callbacks. The proposed architecture corrects those paths before adding hotels.

[Worthkind Flow base PR #2](https://github.com/NIDHOGGR-shadow/worthkind/pull/2) remains a development-only FastAPI enquiry backend. [IT/service ticket PR #31](https://github.com/NIDHOGGR-shadow/worthkind/pull/31) remains a development reference. Nothing in this documentation authorizes production Meta/Twilio connection, hotel messages or confirmed bookings.

## Gate before first real sender

One hotel owner authorizes access; its real business number and account mode are known; staff response ownership and policy are approved; signed callbacks and strict tenant mapping are tested; secure storage, release rollback, consent and current Meta billing are reviewed. A safe no-AI human-first channel must work before enabling either existing chat agent or voice integrations.

## Primary outside sources

- [Meta WhatsApp Business Platform API](https://developers.facebook.com/documentation/business-messaging/whatsapp/overview/)
- [Meta Cloud API Postman source](https://www.postman.com/meta/whatsapp-business-platform/overview)
- [Meta webhook signature documentation](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/)
- [WhatsApp Business Messaging Policy](https://whatsappbusiness.com/policy/)
- [WhatsApp pricing and updated service message FAQ](https://whatsappbusiness.com/resources/faq/)
- [WhatsApp Business Solution Terms / general-purpose AI constraint](https://www.whatsapp.com/legal/business-solution-terms/)
- [Meta WhatsApp Business Calling](https://whatsappbusiness.com/blog/whatsapp-business-calling-api/)
- [Stack Overflow: redelivery of webhook events](https://stackoverflow.com/questions/72894209/whatsapp-cloud-api-sending-old-message-inbound-notification-multiple-time-on-my)
- [Stack Overflow: accepted does not mean delivered](https://stackoverflow.com/questions/79349286/whatsapp-cloud-api-messages-accepted-but-never-delivered)

**Only source-grounded interfaces are described as existing; no simulated adapter test is characterized as a verified live hotel integration.**
