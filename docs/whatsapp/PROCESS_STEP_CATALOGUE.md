# Worthkind Flow — WhatsApp Process Catalogue

**Status:** design catalogue, not implemented code or observed performance. Date: 2026-11-17.

**Quantified inventory:** **15 major processes**, **126 proposed system steps**. Each action has an explicit business/technical reason, a failure/policy boundary, an accountable workstream, and a proposed test signal. This is a design inventory, not a claim that 126 production steps currently run.

**Priorities:** P01–P04, P09, P11 and P12 form the first channel and human handoff slice. PMS/payments (P06), department systems (P07/P08), AI (P05), voice/Flows (P15) are gated by provider/real-hotel authority. Documentation of status is separate from actual implementation.

## Process summary

| Process | Name | Steps | Responsible workstream |
| --- | --- | ---: | --- |
| P01 | Consumer discovery | 8 | Guest/UX |
| P02 | Meta inbound transport | 10 | Channel backend |
| P03 | Hotel and guest identity | 8 | Backend/security |
| P04 | Rules, access and handoff | 8 | Orchestrator/hotel operations |
| P05 | AI and retrieval | 8 | AI/ML engineer |
| P06 | Reservation and payment | 10 | Hotel PMS + finance |
| P07 | Dining, events and suppliers | 7 | Department leads |
| P08 | IT and hotel service desk | 8 | IT/reception |
| P09 | Outbound and delivery status | 10 | Messaging backend |
| P10 | Hotel and Worthkind interfaces | 8 | UX / frontend |
| P11 | Multi-hotel onboarding | 9 | Founder + platform team |
| P12 | Security, recovery, governance | 8 | Security/SRE |
| P13 | Engineering release | 8 | Tech lead/QA |
| P14 | Growth and finance | 8 | Sales/product/finance |
| P15 | WhatsApp voice and Flow forms | 8 | Voice/UX specialist |

## Step-by-step process contract

| Step | Process | Action | WHY | Gate / failure handling | Owner | Evidence / test metric |
| --- | --- | --- | --- | --- | --- | --- |
| P01.01 | Consumer discovery | Tap hotel WhatsApp link/QR | Make entry possible without AI | Verify originating hotel and prevent spoofed referral attribution | Guest/UX | Referral link opens correct hotel |
| P01.02 | Consumer discovery | Send guest text/button/list | Give low-friction entry option | Unsupported payload must offer plain-text fallback | Guest/UX | Intent received or fallback shown |
| P01.03 | Consumer discovery | Recognize correct hotel identity | Avoid replying under wrong hotel's brand | Display hotel legal/display name before service | Guest/UX | Correct brand in 100% fixture chats |
| P01.04 | Consumer discovery | Show direct human option | Don't lock service behind an agent | Human button/keyword skips model | Guest/UX | 20/20 bypass tests |
| P01.05 | Consumer discovery | Show concise scope/privacy notice | Give informed contact-processing context | Do not ask for sensitive details upfront | Guest/UX | Notice visible and version recorded |
| P01.06 | Consumer discovery | Gather dates/guest count only when needed | Minimize required input | User may cancel/decline without penalty | Guest/UX | Request completion and drop-off |
| P01.07 | Consumer discovery | Return case/reference with honest status | Make progress verifiable | No booking or delivery success without source proof | Guest/UX | Reply linked to audit case |
| P01.08 | Consumer discovery | Handle STOP / opt-out | Respect guest preference | Disable marketing immediately and apply purpose policy | Guest/UX | 100% opt-out fixtures enforced |
| P02.01 | Meta inbound transport | Accept GET verification | Register webhook legitimately | Wrong hub token rejects | Channel backend | Challenge contract test |
| P02.02 | Meta inbound transport | Receive POST over HTTPS | Receive platform-originated event | Malformed body and request-size guards | Channel backend | All valid fixtures ingested |
| P02.03 | Meta inbound transport | Verify HMAC on raw bytes | Stop spoofed sender events | Constant-time compare, no parsed-body recompute | Channel backend | 100% forged fixtures rejected |
| P02.04 | Meta inbound transport | Iterate every entry/change | Support batched events | No first-item-only parsing | Channel backend | All messages in batch counted |
| P02.05 | Meta inbound transport | Separate messages and statuses | Don't lose delivery evidence | Status update never invokes customer AI | Channel backend | Sent/delivered/read/failed recognized |
| P02.06 | Meta inbound transport | Dedupe provider event IDs | Prevent duplicate side effects on Meta retry | Unique ID per receiving phone + event | Channel backend | 100 replays one domain effect |
| P02.07 | Meta inbound transport | Persist inbox before 200 response | Prevent acknowledged/lost messages | Fail transiently when storage unavailable | Channel backend | No lost committed messages |
| P02.08 | Meta inbound transport | Queue bounded async processing | Keep webhook fast and reliable | Conversations serialized per tenant+guest | Channel backend | Out-of-order test suite |
| P02.09 | Meta inbound transport | Handle unknown phone-number ID | Never leak cross-tenant content | Quarantine or safe no-op with metric | Channel backend | Cross-tenant negative suite |
| P02.10 | Meta inbound transport | Record provider correlation ID | Enable diagnosis and disputes | Redact message content from traces | Channel backend | Trace from inbound to response |
| P03.01 | Hotel and guest identity | Lookup WABA and phone number ID | Bind event to authorized property | Missing/stale mapping cannot route | Backend/security | No wrong hotel tests |
| P03.02 | Hotel and guest identity | Check tenant activation | Respect suspension/offboarding | Disabled hotel returns no business reply | Backend/security | Kill-switch test |
| P03.03 | Hotel and guest identity | Create scoped channel conversation | Keep accounts and conversations separate | No cross-property merges on same wa_id | Backend/security | Tenant isolation tests |
| P03.04 | Hotel and guest identity | Record last user message time | Compute customer service window | Provider statuses do not reset 24h window | Backend/security | Boundary checks |
| P03.05 | Hotel and guest identity | Check contact opt-in by purpose | Avoid unauthorized marketing | Transactional service and promotional consent separate | Backend/security | Explicit evidence per purpose |
| P03.06 | Hotel and guest identity | Verify booking ownership before private read | Phone ID not sufficient identity | Use secure hotel proof, not room number alone | Backend/security | Negative private-lookup tests |
| P03.07 | Hotel and guest identity | Check staff RBAC for action | Protect guest and financial data | Invitation, role and current property scope | Backend/security | Role denial tests |
| P03.08 | Hotel and guest identity | Allow consent withdrawal and retention | Give privacy rights operational effect | Stop future messaging where applicable | Backend/security | Deletion/opt-out audit |
| P04.01 | Rules, access and handoff | Run deterministic urgent/human keywords | Guarantee bypass of AI | Emergency/anger/ask-person routes to staff | Orchestrator/hotel operations | 100% critical test-set recall |
| P04.02 | Rules, access and handoff | Classify FAQ vs enquiry vs departmental service | Select authoritative workflow | Unknown defaults to clarification/human | Orchestrator/hotel operations | Intent confusion matrix |
| P04.03 | Rules, access and handoff | Check staffed hours | Avoid promising 24/7 staff support | Outside hours show alternatives and realistic timing | Orchestrator/hotel operations | Hours/holiday fixture tests |
| P04.04 | Rules, access and handoff | Create case on missing evidence | Own unresolved work | Assigned owner and due state | Orchestrator/hotel operations | Every case traceable |
| P04.05 | Rules, access and handoff | Staff claims conversation atomically | Avoid two-person or AI conflict | First-claim wins with version check | Orchestrator/hotel operations | Concurrent claim tests |
| P04.06 | Rules, access and handoff | Pause automated responses during takeover | Respect exclusive human control | Only authorized utility reminders allowed | Orchestrator/hotel operations | No mixed AI/human messages |
| P04.07 | Rules, access and handoff | Escalate unclaimed cases | Prevent silent loss | Supervisor/rescue route tested | Orchestrator/hotel operations | Overdue case alarm |
| P04.08 | Rules, access and handoff | Reopen and close after evidence | Don't mark resolved on promise alone | Audit reason and responsible actor | Orchestrator/hotel operations | Resolved state evidence |
| P05.01 | AI and retrieval | Choose no-LLM rules first | Control cost/latency and preserve fallback | FAQ direct path remains functional offline from LLM | AI/ML engineer | Rule vs model cost baseline |
| P05.02 | AI and retrieval | Filter approved KB by hotel | Protect tenants and prevent stale facts | Content version, effective date, visibility | AI/ML engineer | Zero other-hotel answer fixtures |
| P05.03 | AI and retrieval | Evaluate retrieval sufficiency | Reduce fabricated answers | Missing facts abstain | AI/ML engineer | 100 missing-fact cases |
| P05.04 | AI and retrieval | Prepare model context minimization | Minimize sensitive information | No unrelated guest data or credentials | AI/ML engineer | Prompt/PII audit |
| P05.05 | AI and retrieval | Generate optional grounded text reply | Improve clarity without changing authority | Constrained tools only | AI/ML engineer | Fact correctness and citations |
| P05.06 | AI and retrieval | Authorize proposed actions in code | Prevent prompt-directed illegal actions | Never let LLM confirm money/booking | AI/ML engineer | Unsafe tool result 0 |
| P05.07 | AI and retrieval | Capture corrections for review only | Improve from real evidence safely | No auto-training on guest messages | AI/ML engineer | Consented redacted labeling ledger |
| P05.08 | AI and retrieval | Version prompt, model, KB and tools | Gate every moving component | Shadow compare before rollout | AI/ML engineer | Release gate thresholds |
| P06.01 | Reservation and payment | Ask for stay dates, guest count, room type | Get necessary availability dimensions | Validate date/time and property | Hotel PMS + finance | Input completeness |
| P06.02 | Reservation and payment | Read only authorized PMS availability | Avoid imaginary room inventory | PMS unavailable => enquiry only | Hotel PMS + finance | No false availability |
| P06.03 | Reservation and payment | Retrieve source price and cancellation policy | Quote actual terms | Taxes/currency/version required | Hotel PMS + finance | Quote match tests |
| P06.04 | Reservation and payment | Show guest review and confirmation | Get explicit consent before commitment | No model-only confirmation | Hotel PMS + finance | Guest approved state stored |
| P06.05 | Reservation and payment | Create provider hold only when supported | Prevent oversell | Expiry and correlation ID documented | Hotel PMS + finance | Hold state test |
| P06.06 | Reservation and payment | Use secure PSP checkout | Keep card data away from WhatsApp | Only authorized hosted flow | Hotel PMS + finance | No card/PIN in chat |
| P06.07 | Reservation and payment | Verify webhook signature and exact payment | Establish financial truth | Amount/currency/ref/merchant checked | Hotel PMS + finance | Fraud/duplicate fixtures |
| P06.08 | Reservation and payment | Reconcile PMS reservation idempotently | Avoid double booking/charge | Provider ref and recovery workflow | Hotel PMS + finance | 0 duplicate reservation effects |
| P06.09 | Reservation and payment | Handle payment success but PMS fail | Provide truthful exception handling | Finance owns refund/retry decision | Hotel PMS + finance | Finance case opened |
| P06.10 | Reservation and payment | Send confirmed reference only after PMS proof | Avoid misrepresenting booking | Message carries source confirmation ID | Hotel PMS + finance | Zero unsupported confirmed replies |
| P07.01 | Dining, events and suppliers | Read approved menu and allergen information | Avoid wrong pricing/health risk | Missing allergen data asks staff | Department leads | Correct FAQ/menu tests |
| P07.02 | Dining, events and suppliers | Capture food order request | Create a staff-relevant lead | No kitchen promise until POS accepts | Department leads | Order state truth |
| P07.03 | Dining, events and suppliers | Confirm POS/kitchen acceptance | Distinguish request vs actual order | Kitchen rejection or closure safe path | Department leads | Acknowledgment latency |
| P07.04 | Dining, events and suppliers | Treat delivery as separate fulfillment | Avoid false delivery claim | Courier acceptance and proof required | Department leads | Fulfillment reconciliation |
| P07.05 | Dining, events and suppliers | Route wedding/meeting enquiry | Get sales manager to quote | No venue hold without staff approval | Department leads | Event lead follow-up |
| P07.06 | Dining, events and suppliers | Route job enquiries to HR | Limit CV access | No AI hiring or offer | Department leads | Restricted applicant test |
| P07.07 | Dining, events and suppliers | Route vendors to procurement | Avoid invented contracts | No unsolicited attachments accepted blindly | Department leads | Procurement acknowledgement |
| P08.01 | IT and hotel service desk | Create issue from authorized guest request | Turn complaint into accountable work | Guest stay ownership validated for private details | IT/reception | Ticket ID linked to case |
| P08.02 | IT and hotel service desk | Classify IT, housekeeping, maintenance etc | Find responsible department | Unknown routes supervisor not arbitrary team | IT/reception | Category accuracy |
| P08.03 | IT and hotel service desk | Set hotel-approved severity and SLA | Meet actual staffing coverage | Demo 1/4/24/72h must be signed off | IT/reception | SLA policy evidence |
| P08.04 | IT and hotel service desk | Assign an available staff member | Have an accountable person | No fake assignment when staff offline | IT/reception | Acceptance timestamp |
| P08.05 | IT and hotel service desk | Record work started and staff notes | Track progress | Notes role-restricted and auditable | IT/reception | Time to start |
| P08.06 | IT and hotel service desk | Escalate overdue tickets | Catch unhandled problems | Supervisor and backup route | IT/reception | Overdue alerts observed |
| P08.07 | IT and hotel service desk | Require proof before resolved | Avoid imaginary completion | Staff text/evidence and guest update | IT/reception | Resolution outcome rate |
| P08.08 | IT and hotel service desk | Allow reopen/dispute | Handle recurrence honestly | History retained without duplicate ticket | IT/reception | Reopen rate |
| P09.01 | Outbound and delivery status | Commit business event with audit and outbox | Survive API crashes | Atomic DB transaction | Messaging backend | No unaudited changes |
| P09.02 | Outbound and delivery status | Lease outbox job | Avoid duplicate workers | Lease TTL and worker recovery | Messaging backend | Single active attempt |
| P09.03 | Outbound and delivery status | Check 24-hour window based on user message | Enforce platform policy | Do not use business sends as reset | Messaging backend | Window boundary tests |
| P09.04 | Outbound and delivery status | Check template category/approval/consent | Prevent spam and wrong template type | Approved utility/marketing/auth only | Messaging backend | Template policy pass |
| P09.05 | Outbound and delivery status | Enforce per-hotel spend and rate cap | Limit accidental costs | Kill-switch and alerts | Messaging backend | Max spend respected |
| P09.06 | Outbound and delivery status | Send with correct tenant credentials | Protect WABA isolation | Credential store and owner approval | Messaging backend | Wrong token denied |
| P09.07 | Outbound and delivery status | Store Meta accepted ID separately | Avoid delivered false claim | provider_accepted != delivered | Messaging backend | State machine tests |
| P09.08 | Outbound and delivery status | Consume sent/delivered/read/failed callback | Observe transport outcome | Status may be out of order | Messaging backend | 30 status fixtures |
| P09.09 | Outbound and delivery status | Reconcile timeout/unknown outcome | Prevent repeated charge or spam | No blind retry until evidence checked | Messaging backend | Unknown outcome queue |
| P09.10 | Outbound and delivery status | Escalate permanent delivery failure | Give human alternate contact | Do not claim guest saw reply | Messaging backend | Exception SLA |
| P10.01 | Hotel and Worthkind interfaces | Design guest WhatsApp quick-entry menu | Reduce cognitive effort | Human always visible | UX / frontend | Usability completion |
| P10.02 | Hotel and Worthkind interfaces | Design reception shared inbox | Show hotel ownership and state | No cross-tenant content | UX / frontend | Role test |
| P10.03 | Hotel and Worthkind interfaces | Provide claim/takeover/release controls | Make who speaks clear | AI paused under staff | UX / frontend | Takeover test |
| P10.04 | Hotel and Worthkind interfaces | Show status chips accepted vs delivered | Avoid operational misunderstanding | Unknown state distinct from delivered | UX / frontend | UX comprehension testing |
| P10.05 | Hotel and Worthkind interfaces | Link original chat to case/ticket | Give context without dumping PII | Redaction and guest authorization | UX / frontend | Case retrieval test |
| P10.06 | Hotel and Worthkind interfaces | Build hotel-admin setup | Manage roles, SLA, templates, costs | Approval and audit for config writes | UX / frontend | Config change tests |
| P10.07 | Hotel and Worthkind interfaces | Build Worthkind tenant support view | Diagnose with privacy | Only redacted metadata for support | UX / frontend | Support role test |
| P10.08 | Hotel and Worthkind interfaces | Build engineer trace/incident console | Resolve failures quickly | No sensitive content in logs | UX / frontend | Incident drill |
| P11.01 | Multi-hotel onboarding | Sign discovery and channel authorization | Establish legitimate hotel relationship | No connected WABA without explicit hotel consent | Founder + platform team | Onboarding record |
| P11.02 | Multi-hotel onboarding | Confirm physical property and owner | Avoid wrong sender ownership | Verify document/admin access | Founder + platform team | Owner signoff |
| P11.03 | Multi-hotel onboarding | Choose Meta direct, BSP or coexistence path | Avoid unintended migration/downtime | Check number eligibility and restrictions | Founder + platform team | Mode recorded |
| P11.04 | Multi-hotel onboarding | Create/associate hotel WABA and phone ID | Guarantee proper routing | One sender mapped to authorized hotel | Founder + platform team | Phone mapping tests |
| P11.05 | Multi-hotel onboarding | Issue least-privilege credentials | Reduce breach blast radius | Vault + rotation/revocation | Founder + platform team | Key rotation drill |
| P11.06 | Multi-hotel onboarding | Configure webhook subscriptions | Receive authorized events | Live signed echo+delivery test | Founder + platform team | Callback test |
| P11.07 | Multi-hotel onboarding | Create and approve hotel-specific templates | Meet policy and branding | No generic unapproved placeholder | Founder + platform team | Approval evidence |
| P11.08 | Multi-hotel onboarding | Obtain privacy/consent/SLAs | Set legal/operational terms | Human contact and DPA | Founder + platform team | Hotel signoff |
| P11.09 | Multi-hotel onboarding | Complete synthetic and live pilot drills | Catch wrong property and outage | Go/no-go gates | Founder + platform team | Pilot acceptance record |
| P12.01 | Security, recovery, governance | Threat-model trust boundaries | Find attack paths early | Webhook/public/staff/provider separated | Security/SRE | Reviewed threat model |
| P12.02 | Security, recovery, governance | Keep app secrets and tokens out of code | Protect client WABAs | Secrets manager, scoped permission | Security/SRE | Secret scan |
| P12.03 | Security, recovery, governance | Protect media fetch/egress | Avoid SSRF and malicious attachments | Only provider media APIs, MIME and size gates | Security/SRE | Media adversarial tests |
| P12.04 | Security, recovery, governance | Encrypt/limit stored customer information | Reduce retention and legal risk | NDPA and contracted retention | Security/SRE | Privacy audit |
| P12.05 | Security, recovery, governance | Rate-limit per property and sender | Prevent bot abuse/cost spikes | Burst and abuse detection | Security/SRE | Load test |
| P12.06 | Security, recovery, governance | Log correlation without raw PII | Support incident forensics | Trace IDs and redaction | Security/SRE | Incident rehearsal |
| P12.07 | Security, recovery, governance | Test Meta downtime and queue recovery | Avoid lost conversations | Dead-letter, backoff, re-drive policy | Security/SRE | Chaos test |
| P12.08 | Security, recovery, governance | Offboard and revoke phone integration | Honor hotel exit | Stop sends, erase per policy, rotate keys | Security/SRE | Offboarding audit |
| P13.01 | Engineering release | Audit reusable Zuvamo code and license | Prevent unsafe copy and stale assumptions | Check ownership and tests | Tech lead/QA | Reuse decision ADR |
| P13.02 | Engineering release | Write typed channel/domain contracts | Make adapter swappable | No LLM business authority | Tech lead/QA | Schema review |
| P13.03 | Engineering release | Build signed webhook fixtures | Prove real message shapes | Text/status/audio/batch/dedupe | Tech lead/QA | Fixture suite |
| P13.04 | Engineering release | Run cross-hotel negative tests | Prevent a tenant leak | No wrong-hotel response | Tech lead/QA | 100% scope tests |
| P13.05 | Engineering release | Run 24h/template pricing tests | Prevent policy and bill surprises | Current pricing checked against Meta | Tech lead/QA | Cost gate |
| P13.06 | Engineering release | Run voice-note and STT failure tests | Keep audio safe and useful | Human/text fallback | Tech lead/QA | Speech test |
| P13.07 | Engineering release | Review deployment with hotel owner | Enforce controlled rollout | Pilot business number only | Tech lead/QA | Signoff |
| P13.08 | Engineering release | Monitor and rollback | Keep pilot reliable | Alerts, switch-off and manual routing | Tech lead/QA | Drill within target |
| P14.01 | Growth and finance | Tag source: QR, site, ad or listing | Understand acquisition channel | Only allowed referral data stored | Sales/product/finance | Attribution coverage |
| P14.02 | Growth and finance | Ask for messaging/marketing permission | Separate service from promotional use | No unwanted marketing | Sales/product/finance | Consent proof |
| P14.03 | Growth and finance | Track enquiry → staff acceptance | Measure whether platform helps | Do not call every lead a booking | Sales/product/finance | Conversion denominator |
| P14.04 | Growth and finance | Verify real room/order outcomes | Avoid inflated hotel revenue | Provider-verified source reference | Sales/product/finance | Reconciliation |
| P14.05 | Growth and finance | Separate hotel GMV and Worthkind ARR | Avoid accounting confusion | Monthly subscription is not booking value | Sales/product/finance | Financial model |
| P14.06 | Growth and finance | Measure provider category costs | Avoid unprofitable messaging | Template/service/bsp/stt/llm costs | Sales/product/finance | Cost per resolved case |
| P14.07 | Growth and finance | Track failure, unsubscribe and block feedback | Protect channel quality | Pauses outbound when negative signals rise | Sales/product/finance | Quality alert |
| P14.08 | Growth and finance | Review ROI with hotel owner | Validate willingness to pay | No fabricated uplift | Sales/product/finance | Pilot go/no-go |
| P15.01 | WhatsApp voice and Flow forms | Distinguish voice note from live call | Avoid wrong technology architecture | Different provider interface | Voice/UX specialist | Feature inventory |
| P15.02 | WhatsApp voice and Flow forms | Fetch voice-note media with token | Enable authorized transcription | Max size/type and retention | Voice/UX specialist | Download fixture |
| P15.03 | WhatsApp voice and Flow forms | Transcribe and confidence-check audio | Understand customer intent | No guessing if no transcript | Voice/UX specialist | Word error/eval |
| P15.04 | WhatsApp voice and Flow forms | Offer text/human fallback | Preserve service on STT outage | Handoff visible | Voice/UX specialist | Failure test |
| P15.05 | WhatsApp voice and Flow forms | Verify WhatsApp Calling API eligibility | Avoid assuming call support | Region, BSP, number capability | Voice/UX specialist | Provider proof |
| P15.06 | WhatsApp voice and Flow forms | Obtain outbound calling consent | Comply with call rules | Permission recorded | Voice/UX specialist | Consent test |
| P15.07 | WhatsApp voice and Flow forms | Route live audio to approved voice service | Keep low latency and human help | Separate SIP/WebRTC contract | Voice/UX specialist | Live call test |
| P15.08 | WhatsApp voice and Flow forms | Offer structured WhatsApp Flows form | Reduce multi-message data entry | Encrypted exchange and input validation | Voice/UX specialist | Form completion audit |

## Interpretation

1. A completed action in a **design** catalogue is not evidence of an integrated provider. Source-of-truth operations require authorized hotel systems.
2. No unverified service window or price claim is included. WhatsApp service-message pricing changed October 2026; use current Meta terms and rate card per hotel/recipient country.
3. Design-internal targets, such as 100% fixed-set signature rejection or 20/20 human-bypass test journeys, are **release criteria to test**, not production results.
4. The same hotel guest may enter via web, voice note, WhatsApp text or staff. Normalize the event and route to **one hotel backend**, preserving the original provider ID for audit.
5. Human takeover should have exactly one conversation owner and release state, not a "handoff" box with no outgoing edge. Missed SLA is a first-class event.

**Architecture:** [Master spec](MASTER_ARCHITECTURE.md) and [13 process diagrams](diagrams/).
