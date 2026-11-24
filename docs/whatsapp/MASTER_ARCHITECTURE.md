# Worthkind Flow — WhatsApp End-to-End Architecture (v1 research design)

**Date:** 2026-11-17 · **Status:** architecture and integration proposal · **Product:** Worthkind Flow (hospitality, multi-tenant) · **Not:** a connected hotel WhatsApp account, production messaging gateway, payment system or hotel-confirmed reservations.

## Executive technical decision

WhatsApp is an **internet-delivered business messaging channel**, not a SIM-specific banking USSD protocol. The user's mobile network and SIM provide cellular connectivity if Wi-Fi is unavailable, but Worthkind Flow never selects a SIM, controls the device's WhatsApp encryption or opens a private WhatsApp session. **Meta owns the transport and provider rules.** Each hotel supplies an authorized business sending identity; Worthkind supplies controlled software, policy, staff workflow and optional AI **behind** the signed webhook.

**First useful slice:** hotel guest messages a configured WhatsApp test/business number → signed webhook → phone-number ID resolves property → authenticated/authorized message intake → deterministic rules/FAQ → (when needed) accountable reception case → hotel staff claims and responds → authorized outbound sender → Meta acceptance → actual delivered/failed status webhook → staff can see true status. A live PMS or payment provider is not a prerequisite for **enquiry-only**, and cannot be faked.

**Primary architecture:** modular FastAPI domain backend; PostgreSQL + row-level policy after migration, transactional inbox/audit/outbox, durable per-conversation workers, tenant-scoped message configuration, provider adapter (Meta direct / optional approved Twilio path), deterministic human and emergency bypass, **existing** chat/voice agent integrations as optional adapters. Design for one pilot hotel/one sender before many hotels.

## Evidence reviewed and what is actually implemented

| Source | Observed code / evidence | Design implication |
| --- | --- | --- |
| [Worthkind Flow v5 design](../ARCHITECTURE_V5.md) and [flows](../FLOWS.md) | Scoped tenant identity, deterministic routing, authorised domain actions, audit/outbox and explicit human bypass. P0 FastAPI is synthetic local SQLite; no live WhatsApp or PMS/PSP. | Use Worthkind Flow as hotel domain authority. Chat/voice are not source of operational truth. |
| [Zuvamo / verodesk WhatsApp docs](https://github.com/NIDHOGGR-shadow/verodesk/blob/main/docs/whatsapp.md) | Implements Meta and Twilio adapters, 24-hour check, tenant resolution, media and voice-note path, signed webhook tests. | Audit and adapt existing code rather than copy wholesale or build another transport stack. |
| [Zuvamo Meta adapter](https://github.com/NIDHOGGR-shadow/verodesk/blob/main/packages/core/novaxis_core/channels/whatsapp.py) | HMAC-SHA256 checks raw body, parses bundled inbound messages by \`metadata.phone_number_id\`, but **does not convert provider \`statuses\` into delivery events**. Uses one configured access token in shared settings, while the phone-number ID is tenant-configurable. | Preserve signature/normalization approach; build status reconciliation and tenant-scoped credential vault, consider Meta app-level vs hotel-specific credential ownership. |
| [Zuvamo outbound](https://github.com/NIDHOGGR-shadow/verodesk/blob/main/packages/core/novaxis_core/outbound.py) | Enforces 24-hour free-form window, otherwise approved template or handoff. Sets \`msg.delivered_at = now\` after provider returns an ID. | Rename state to **provider_accepted** and update delivered/read only on provider status callbacks. Existing docs wrongly imply window messages necessarily remain free under Oct 2026 pricing. |
| [Zuvamo Twilio adapter](https://github.com/NIDHOGGR-shadow/verodesk/blob/main/packages/core/novaxis_core/channels/twilio_whatsapp.py) | Signed Twilio form/inbound and outbound to Twilio Messages API; tests for tenant identity and 24-hour flow. | Possible pilot sandbox path. Twilio number onboarding, policy, billing and status callbacks must be rechecked for hotel's own sender. |
| [Zuvamo voice notes](https://github.com/NIDHOGGR-shadow/verodesk/blob/main/docs/voice-notes.md) | Audio message is downloaded, transcribed, then safety/intent routing occurs. Some tests use mock Whisper transcripts. | Distinguish **voice note** (asynchronous media) from **live WhatsApp voice call** (separate real-time Calling API and permissions); mock tests do not prove live audio quality. |
| [Official Meta Business Platform overview](https://developers.facebook.com/documentation/business-messaging/whatsapp/overview/) | Message send endpoint \`/{phone-number-id}/messages\`, WABA management, Embedded Signup/coexistence and partner setup. | Keep a verifiable business-number/WABA onboarding and transport boundary. |
| [Official Meta webhooks](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/) | Signature \`X-Hub-Signature-256\` and HTTP callback verification; events can repeat/batch. | Verify **raw bytes**, persist idempotent inbox before HTTP success, differentiate messages and statuses. |
| [WhatsApp business messaging policy](https://whatsappbusiness.com/policy/) | Customer service window, approved outbound templates, direct human escalation and lawful consent requirements. | Policy enforced by outbound code; human handoff is mandatory, not an agent prompt. |
| [WhatsApp pricing and current FAQ](https://whatsappbusiness.com/resources/faq/) | Per-message pricing, including service messages charged after a per-number free allowance from October 2026. | Update older "all service replies are free" assumptions; meter service, utility and marketing separately. |
| [WhatsApp Business Solution Terms](https://www.whatsapp.com/legal/business-solution-terms/) | Restricts general-purpose AI assistant distribution as the **primary** product in most markets; hospitality customer support is a distinct use case but needs review. | Keep the assistant narrowly hotel-service oriented, not an unrestricted chat bot. |
| [Meta's official WhatsApp Postman collection](https://www.postman.com/meta/whatsapp-business-platform/overview) | Sends, media, phone IDs and subscriptions are concrete API operations. | Build sandbox contract tests against documented API shapes. |
| [Stack Overflow: repeated inbound callbacks](https://stackoverflow.com/questions/72894209/whatsapp-cloud-api-sending-old-message-inbound-notification-multiple-time-on-my) | Developer reports of retries and duplicate replies. These are anecdotes, not incidence measurements. | Unique \`(tenant, channel, provider_event_id)\` inbox and no duplicate business side effects. |
| [Stack Overflow: API accepted != delivered](https://stackoverflow.com/questions/79349286/whatsapp-cloud-api-messages-accepted-but-never-delivered) | Accepted send does not prove device delivery. | Maintain statuses and reconciliations as independent events; never mark delivered at HTTP 200. |
| [WhatsApp Business Calling API](https://whatsappbusiness.com/blog/whatsapp-business-calling-api/) | WhatsApp supports optional voice calls via separate Calling API. | Verify region/provider eligibility, call permissions, voice stream integration and costs before enabling existing voice agent for live WhatsApp calls. |

## 1. Domain boundaries and who owns the truth

| Party | Owns and is accountable for | Does NOT own |
| --- | --- | --- |
| Guest/consumer | Opt-in, message content and preferences, cancellation requests, whether to ask for a person; choosing when to communicate | Permission to force hotel actions or mark room paid |
| Meta / WhatsApp | Business messaging transport, sender identity, platform policy, message ID, delivery/read events, templates, usage charges | Room inventory, hotel payments, staff acceptance, hiring |
| Hotel's Meta Business Account | Approved WABA/business number, compliance/phone ownership and approved templates; signs off hotel use | Other hotels' WABAs, Worthkind general platform IP |
| Worthkind platform | Tenant-isolated gateway, workflow, audit, inbox/outbox, optional orchestration, reporting and platform billing | Unapproved access to guest data, inventory/payments, sending as a hotel without authorization |
| Hotel reception / staff | Guest handoff, actual SLA, legitimate service decision and status updates | Cross-property conversations without role authorization |
| Hotel PMS / booking engine | Real rooms, rates, holds, booking reference and cancellation state | AI-generated availability |
| Payment service provider / hotel finance | Payment authorization, amount, currency, receipt and reconciliation | "Success" based on a WhatsApp chat or browser redirect |
| Restaurant POS / kitchen / dispatch | Menu/stock, accepted order, preparation, rider and delivery status | LLM-made order fulfilment |
| AI/ML and voice processors | Advisory classification, answer composition from permitted content, transcription and confidence; transparent fallback | Autonomous financial action, HR offer, refund, staff approval |
| Regulators and policy | NDPA/NDPC, WhatsApp policy, contractual limitations, deletion and privacy handling | Operational features implemented without hotel permission |

## 2. Source diagrams — 13 editable Mermaid files

1. [Platform and transport context](diagrams/01-system-context.mmd)
2. [Inbound message and outbound response sequence](diagrams/02-inbound-and-return-sequence.mmd)
3. [One hotel's WABA/phone setup and onboarding](diagrams/03-hotel-onboarding.mmd)
4. [Exclusive human takeover state machine](diagrams/04-human-handoff-ownership.mmd)
5. [Room, F&B, support, events, careers, supplier workflows](diagrams/05-domain-business-workflows.mmd)
6. [Rules, chat AI, voice notes, agent evaluation](diagrams/06-ai-and-voice-notes.mmd)
7. [WhatsApp message acceptance vs actual delivery states](diagrams/07-message-delivery-states.mmd)
8. [Security policy, failure and recovery](diagrams/08-security-and-failure-recovery.mmd)
9. [UX for guest, hotel staff, owner, Worthkind admin, engineering](diagrams/09-ui-ux-and-five-personas.mmd)
10. [Engineering build/release/QA](diagrams/10-engineering-and-release.mmd)
11. [Ads/referrals, opt-in, cost and ROI attribution](diagrams/11-marketing-and-money.mmd)
12. [WhatsApp voice-note vs live calling](diagrams/12-whatsapp-voice-call-options.mmd)
13. [Optional WhatsApp Flows interactive in-chat forms](diagrams/13-structured-whatsapp-flows.mmd)

**Terminology:** "WhatsApp Flow" here is the overall business-messaging process. *WhatsApp Flows* (plural) is also Meta's separately documented product for structured in-chat forms; diagram 13 treats it as one optional user-interface component, NOT as the entire integration.

## 3. WhatsApp ingress-to-egress contracts

### Inbound gateway

**GET** \`/webhooks/whatsapp/meta\`: verify the configured setup token and return Meta's challenge only for a valid subscription. Never expose the token.

**POST** \`/webhooks/whatsapp/meta\`:
1. Enforce HTTPS, body-size limits, known content type, timeouts and rate controls.
2. Read exact unmodified bytes; compute HMAC-SHA256 using the **Meta app secret** for the subscribed app and compare with \`X-Hub-Signature-256\` in constant time.
3. Parse \`object == whatsapp_business_account\`, iterate **all** \`entry[].changes[]\`, and handle **both** \`value.messages[]\` and \`value.statuses[]\`.
4. Resolve the receiving business \`value.metadata.phone_number_id\`, with WABA linkage, into ONE active hotel tenant. Do not route by display name or guess from \`from\` alone.
5. Store raw event envelope only if required and protected, normalized event, canonical provider id, tenant id, correlation id and processing status. Enforce unique dedupe keys: \`(provider, phone_number_id, event_type, provider_message_id, status, status_timestamp)\` as appropriate.
6. Commit all inbox rows (including benign duplicates as no-op) before returning HTTP 200; do not call an LLM or PMS synchronously inside provider webhook.
7. Worker leases event, resolves authorized conversation and handles content or status separately.
8. If storage fails before commit, return temporary failure and alert; avoid acknowledging an event that would disappear.

**Payload normalization:** text, button/list choice, reaction if supported, photos/documents, optional locations (privacy-sensitive), audio/voice notes, status receipt, unknown type. A missing/unsupported type gets a safe fallback and telemetry, not a hallucinated user instruction.

### Outbound sender

**Internal command:** \`enqueue_outbound(tenant, conversation, purpose, body_or_approved_template, idempotency_key)\`

- Recheck tenant status, recorded purpose/consent, human ownership, privacy, budget and receiver eligibility **at send time**.
- Inside an active 24-hour customer service window, eligible free-form service reply; outside it only approved templates under applicable policy. 24h opens/resets on user's inbound message, not on ours.
- Template categories **utility / authentication / marketing** must be approved, language-compatible and used only for actual designated purpose. A generic "put arbitrary text in a utility placeholder" template may be reclassified or rejected.
- Submit via \`POST https://graph.facebook.com/{supported-version}/{phone_number_id}/messages\` with a tenant-authorized token, or use the selected BSP adapter. API acceptance + \`wamid\` = \`provider_accepted\`, **not** \`delivered\`.
- Signed \`statuses[]\` callback drives \`sent\`, \`delivered\`, \`read\`, \`failed\`; events can arrive out of order and a status may never be observed. Store raw evidence and derive a monotone user-facing status.
- On timeout after an unknown send outcome, **do not blindly resend**. Reconcile provider ID/operation and use a dedupe strategy before sending again.
- Store per-message quoted/priced category metadata when available and reconcile to provider invoice; budget must account for templates, service messages, BSP charges, model/STT and network costs.
- Worker retry/backoff, dead-letter queue and human escalation are mandatory. An outbound event with \`queued\` status must not be displayed as "received by guest".

## 4. Guest privacy and conversation authority

A WhatsApp sender ID generally identifies the messaging account/number in that channel; it **does not automatically prove** the person is the hotel reservation owner, cardholder, room guest or employee. Asking "what is my booking?" needs reservation ownership proof appropriate to hotel sensitivity, e.g. one-time secure hotel confirmation mechanism, never room number + surname alone.

**Conversation namespace:** \`tenant_id + property_id + channel + wa_id\`; cross-channel account linking (voice/SMS/email) requires an explicit identity/consent policy. Do not merge different hotels' guests just because the same number appears.

**Human takeover:** state machine controls exclusive conversation ownership. When staff claim, automatic generation must cease for that conversation. Operational utility events may still be sent only when policy and human override allow. The guest sees an honest "assigned/pending" state and staffing hours; no claim that a person answered before the person acts.

**Emergency/abuse:** always bypass the model and direct to a human or clear external emergency route, without promising 24/7 response where no staff coverage exists. Avoid sending sensitive health, employment or financial details into general language models or advertising tools.

## 5. Scope of WhatsApp agent vs voice agent

- **Chat AI agent:** optional, hotel-specific question answering, concise clarification and typed proposed actions. Build on existing component **only after** auditing its tool contracts and enforcing tenant-scoped retrieval. Rule-based FAQ and forms must remain available when no LLM works.
- **WhatsApp voice note:** webhook arrives as *media message*, secure download → optional STT → language/intent and safety processing → text or voice reply where supported. Existing Zuvamo \`docs/voice-notes.md\` and tests show a design and mocked processing. No model should guess incomprehensible audio.
- **WhatsApp live voice call:** completely separate **Calling API** capability, involving call signaling, real-time audio/WebRTC or provider SIP, call policy/permissions and live human transfer. Existing Twilio telephony or website voice components cannot simply be assumed compatible. Keep disabled until provider/number support and live call quality are verified.
- **Optional in-chat WhatsApp Flows:** Meta structured forms for dates, guests, menus and enquiry contact. Such forms require Meta-side configuration and, for data-exchange forms, validated encrypted exchange; submitting a form does **not** reserve an actual room.

## 6. Necessary data model — preliminary Postgres schema

| Table | Core minimum attributes | Constraint / why |
| --- | --- | --- |
| \`hotel_properties\` | id, org_id, policies, hours, timezone, active | Actual business identity and authority |
| \`whatsapp_accounts\` | id, tenant_id, property_id, waba_id, phone_number_id, provider, encrypted credential ref, state, token expiry, onboarding evidence | Unique active sender mapping; never write secrets in app DB unencrypted |
| \`channel_consent\` | tenant_id, contact_id, purpose, category, source, timestamp, withdrawn_at | Separate transactional and promotional opt-in |
| \`guest_contacts\` | tenant_id, channel, wa_id, verified_guest_ref if any | Phone is not proof of ownership |
| \`conversations\` | id, property_id, wa_id, owner_type, owner_id, opened_at, last_user_at, status | Enforces exclusive staff takeover and 24-hour window |
| \`inbound_events\` | id, tenant_id, phone_id, provider_ref, event_type, status, received_at, processed_at | Idempotent signed ingress and statuses |
| \`messages\` | id, conversation_id, direction, type, body_ref, provider_ref, state, acceptance_at, delivery_at, read_at | Accepted != delivered; avoid storing sensitive raw media unnecessarily |
| \`hotel_knowledge_versions\` | tenant_id, doc_id, scope, checksum, approved_by, effective_at, superseded_at | Tenant-filtered policy and source lineage |
| \`cases\`, \`tickets\` | tenant_id, assignee, SLA, status, origin_message_ref, resolution | Guest/staff domain authority |
| \`domain_actions\` | request_id, tenant_id, provider, idempotency, attempt_status, source_ref | No duplicate financial/business actions |
| \`audit_events\` | tenant, subject, actor, action, before/after hash, outcome, created_at | Immutable accountability and privacy review |
| \`outbox_events\` | tenant, event, causal id, priority, attempts, lease, delivered_at, dead_letter | Durable outbound worker + crash recovery |
| \`usage_ledger\` | tenant, provider_msg_id, category, country, provider_amount, model_cost, overage, billing_period | True unit economics and enforcement |

Prefer PostgreSQL tenant-scoped RLS plus backend authorization; never expose a raw multi-tenant database/query tool to an LLM.

## 7. Proposed measurable release gates (NOT achieved results)

| Gate | Proposed check | Hard stop |
| --- | --- | --- |
| End-to-end | 25 signed synthetic inbound events, 10 sandbox live messages, 10 staff replies | Any unhandled or lost **committed** request |
| Signature | 100% of malformed/missing/forged signatures rejected in fixtures | One forged command accepted |
| Isolation | 100% wrong-tenant read/write negative tests denied | One cross-property leak |
| Dedupe | 100 replay/double-delivery fixtures, one domain effect | Duplicate cases or booking attempt |
| Handoff | 20 scripted human takeover/outage cases with staff ownership | AI continues speaking while person owns conversation |
| Delivery status | 30 scenarios incl. accepted, delivered, failed, out-of-order, no callback | Provider acceptance falsely displayed as delivered |
| 24h/template | Boundary tests at 23h59m / 24h00m and approved/unapproved categories | Disallowed free-form send outside window |
| Model | 100 hotel-approved FAQs, missing-fact and prompt-injection cases | Invented room confirmations or unsafe tool access |
| Spend | Tenant-specific monthly ceiling and on-call alerts; provider costs reconciled | Unbounded messaging, STT/LLM or marketing spend |
| Hotel staff | Pilot named manager; staffed response SLA and escalation tests | No accountable recipient for forwarded messages |
| Privacy | Hotel and provider DPAs, retention/deletion, least privilege and marketing opt-out | Unconsented promotional outreach or unauthorized raw data |
| Operational | Backup/restore, token expiry, revoked channel and provider outage drill | Silent lost messages with no retry/alert |

Proposed SLOs are **test targets**, not industry averages. Actual 24-hour messaging price and country category require the current Meta rate card **at time of launch**, including the October 2026 service-message policy and any BSP markup.

## 8. First pilot vs full platform

**V0 (pilot design):** one hotel, one authorized Meta test/sender, text messages, direct human bypass, public FAQ with staff-approved content, booking enquiry **only**, internal ticket creation, staff queue/claim/reply, delivery status, failure recovery, 24h/template policy, consent, audit and per-tenant limits.

**V1:** approved production staff login/RBAC, production database, real hotel knowledge CMS, per-department routing, official WhatsApp templates and monitoring, consented voice-note STT and hotel-specific comparison of AI vs deterministic baseline. Still no automatic confirmed booking without PMS.

**V2:** authorized PMS/booking/payments, dining POS, WhatsApp Flows, events, HR and supplier leads, live WhatsApp Calling where technically and contractually eligible, marketing/outcome attribution and multi-hotel embedded onboarding.

For team ownership and engineering order, see [implementation backlog](IMPLEMENTATION_BACKLOG.md) and [quantified process catalogue](PROCESS_STEP_CATALOGUE.md).
