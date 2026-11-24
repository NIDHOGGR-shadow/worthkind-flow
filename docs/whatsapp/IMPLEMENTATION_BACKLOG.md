# Worthkind Flow — WhatsApp Delivery Plan and RACI

**Design status:** proposed, not production. All work scoped under existing private \`NIDHOGGR-shadow/worthkind/projects/worthkind-flow\`; reference code from \`NIDHOGGR-shadow/verodesk\` may be adapted following review, not blindly merged.

## Code reuse assessment (real repository inspection, 2026-11-17)

| Existing component | Actual source | Reuse decision | Changes required |
| --- | --- | --- | --- |
| Meta Cloud API adapter | [verodesk channels/whatsapp.py](https://github.com/NIDHOGGR-shadow/verodesk/blob/main/packages/core/novaxis_core/channels/whatsapp.py) | **Adapt** signature checks, batch parser, media normalization, sender | Expose and process \`statuses[]\`; phone-ID/tenant credential isolation; upgrade current webhook schemas and errors |
| Twilio WhatsApp adapter | [verodesk channels/twilio_whatsapp.py](https://github.com/NIDHOGGR-shadow/verodesk/blob/main/packages/core/novaxis_core/channels/twilio_whatsapp.py) | **Alternative sandbox/provider** when approved | Twilio signature/canonical URL, onboarding number, status callbacks, price/overage; templates outside 24h not built |
| Outbound message policy | [verodesk outbound.py](https://github.com/NIDHOGGR-shadow/verodesk/blob/main/packages/core/novaxis_core/outbound.py) | **Refactor before reuse** | Source marks \`delivered_at\` immediately after API acceptance; must separate accepted/sent/delivered/read/failed; revise October 2026 pricing |
| Voice note/media/STT | [verodesk docs/voice-notes.md](https://github.com/NIDHOGGR-shadow/verodesk/blob/main/docs/voice-notes.md) | **Reuse with tests** | Limit MIME/size/retention, real consented transcription, Nigerian English/noise eval, staff fallback and dedicated budget |
| Agent/business-pack pattern | [verodesk agent.py](https://github.com/NIDHOGGR-shadow/verodesk/blob/main/packages/core/novaxis_core/agent.py) | **Evaluate only as optional** | Hotel-specific, tenant-scoped knowledge, no unrestricted API authority; don't copy HVAC scripts as hotel policy |
| Worthkind Flow enquiry API | \`projects/worthkind-flow/apps/api/main.py\` (foundation PR #2) | **Retain domain reference** | Production staff auth, DB migrations, rate limit, real hotel config required |
| Worthkind Flow service ticket desk | [ticket PR #31](https://github.com/NIDHOGGR-shadow/worthkind/pull/31) | **Attach WhatsApp as channel after safety review** | Real staff ownership/RBAC, escalation/SLAs and delivery need work |
| Hotel OS | [hotel-os](https://github.com/NIDHOGGR-shadow/hotel-os) | **Potential PMS-adapter test source only** | Do not call it live PMS integration for other hotels; validate source availability and authority |

**Reuse invariant:** inspect source code, tests, credential ownership, deployment, and tool contract before a dependency is introduced. Existing mocked API tests are not proof the live Meta, Twilio or hotel's WABA sends messages successfully.

## Team ownership — functional RACI

R = responsible for implementation; A = final accountable signoff; C = consulted; I = informed.

| Workstream | Founder / product | Tech lead | Backend | Frontend/UX | AI/voice | QA/security | Hotel manager/reception |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Define first hotel's problem and outcome | A/R | C | I | C | I | I | C |
| Hotel/WABA onboarding and contract | A | C | R | I | I | C | A/R for their account |
| Inbound webhook + tenant router | I | A | R | I | C | C | I |
| Inbox/outbox and delivery status | I | A | R | C | I | C | I |
| Human ownership, SLA, escalations | A on product | C | R | R | C | C | A on real operation |
| Guest WhatsApp interaction UX | A on messaging | C | C | R | C | C | C |
| Existing chat agent adapter/FAQ | C | A | C | C | R | C | A on hotel facts |
| Voice note and live call (later) | C | A | C | C | R | C | C |
| PMS/PSP/POS integration (later) | C | A | R | C | C | C | A on hotel authority |
| Privacy/consent and data retention | A on contract | C | R | C | C | A on technical risk | A on data controller duties |
| Test/pilot release and incident response | A on launch | A on technical | R | R | C | R | A on hotel operation |

One person may fill multiple roles for a narrow pilot, but **accountability cannot be skipped**. A 6–9-person active core with explicit hotel-side reception and management is plausible; verify actual team availability rather than assume all existing members are free.

## Exact founder responsibilities

1. Interview and sign up **one** actual design-partner hotel, not merely a public WhatsApp contact.
2. Confirm hotel owns or can authorize a WhatsApp Business Account / sending number and has access to decision-maker and privacy policy.
3. Document existing reception process: service hours, accepted request types, actual response times, number of guest messages, who is on shift.
4. Get an approved one-page pilot scope, operational staff owner and terms for accessing customer data.
5. Prioritize only the first slice, approve guest wording, budget caps and launch/rollback conditions.
6. Monitor business impact from **real** conversations and verify willingness to pay, separate from technical API test success.

The founder should **not** personally maintain app secrets, sign provider webhooks, design every SQL table or serve as the only incident responder.

## Milestones and dependencies

| Stage | Suggested execution window* | Deliverables | Go/no-go |
| --- | --- | --- | --- |
| M0 — architecture/design | Already researched | 13 diagrams, source audit, 126 steps, backlog and risk gates | Review technical accuracy; update if Meta changes API |
| M1 — signed channel stub | 1 week | Meta app sandbox, raw HMAC verification, GET handshake, test \`wamid\` inbox, batch dedupe and tenant mapping | No forged/cross-hotel event |
| M2 — full message round trip | 1 week | Outbox worker, actual Graph API test sends, provider \`statuses[]\`, 24h and approved-template checks, honest UI status | Accepted never shown as delivered |
| M3 — human-first pilot | 1–2 weeks | Hotel approval, verified FAQ, enquiry/case, staff inbox claim/takeover, hours/SLA, guest reply, privacy/consent | Hotel manager signs test results |
| M4 — optional AI+voice note | 1–2 weeks, after M3 | Reuse existing chat adapter with scoped knowledge, optional STT; fixed eval/safety and spend gates | Agent can fail without breaking service |
| M5 — broader hotel product | Separate later plan | PMS/payment/food/WhatsApp Flows, multi-property embedded signup, live Calling API where eligible | Each external provider/finance SLA passes |

*Time windows are **indicative development estimates**, assuming ready contributors, test credentials and one authorized hotel. They are not committed dates or measured productivity. Real onboarding or verification delays can dominate.

## P0 engineering backlog — atomic tasks

**P0/W01 Meta setup:** obtain authorized test WABA, phone-number ID, app secret, verify token, scoped messaging token and subscription; store securely in non-production environment. No keys in GitHub.

**P0/W02 Webhook verification:** exact raw-body HMAC SHA256; GET challenge; body size/type; TLS; negative spoof/empty/malformed tests.

**P0/W03 Tenant routing:** WABA and receiving phone ID map to the right hotel; disabled tenant and wrong sender produce no leak. Design multi-sender per organization carefully.

**P0/W04 Durable inbound:** batch parser, text/media/interactive/status distinction; inbox unique keys; DB commit before HTTP 200; dead-letter and recovery.

**P0/W05 Conversation:** stable scoped identifiers, consent, last inbound user timestamp and 24h window. Never rely on number alone to expose private guest booking data.

**P0/W06 Human takeover:** atomic claim, staff messages, SLA/shift escalation, pause AI, staff release/reopen, clear guest confirmation and failure path.

**P0/W07 Hotel FAQ/enquiry:** tenant-approved public content, honest enquiry-only status, link to existing Worthkind case and ticket services.

**P0/W08 Message outbox:** async sender, idempotency, retry with unknown send outcome safety, template approval and category/consent, messaging budgets.

**P0/W09 Provider receipts:** ingest \`statuses[]\`, match accepted \`wamid\`, state machine accepted/sent/delivered/read/failed, out-of-order/duplicate tests.

**P0/W10 Staff UI:** status badges, live communication state, human claim/release and ticket/context view, mobile and keyboard QA.

**P0/W11 Security/privacy:** threat model, secrets vault, tenant isolation, guest ID proof for sensitive actions, retention, consent/opt-out, incident/backup.

**P0/W12 Test and release:** signed fixtures, provider sandbox, 24-hour window boundaries, no-LLM paths, outage chaos, per-tenant billing caps and hotel acceptance.

## P1/P2 backlog gated by external business readiness

- **P1/W13** Government/privacy/legal review and hotel data-processing terms.
- **P1/W14** Production PostgreSQL RLS, staff invite-only auth, audit log and security hardening.
- **P1/W15** Managed hotel knowledge content approvals and per-hotel retrieval indexes.
- **P1/W16** Voice-note STT integration, accent/noise evaluation and alternative text/human paths.
- **P1/W17** Embedded Signup / coexistence / BSP account and per-property secret rotation.
- **P1/W18** WhatsApp interactive forms/Flows for enquiries, with encrypted payload validation if dynamic.
- **P2/W19** PMS quote/holds/bookings, PSP webhook verification, finance reconciliation.
- **P2/W20** POS/kitchen/courier status integrations, no fake delivery.
- **P2/W21** Events, HR and procurement departmental work, restricted records.
- **P2/W22** Live WhatsApp Calling API and existing real-time voice agent (separate voice contract).
- **P2/W23** Marketing template governance, referral/ads attribution and hotel consent.
- **P2/W24** Margin controls: Meta messaging categories + provider markup + infra + STT/LLM; Worthkind MRR kept separate from hotel booking GMV.

## Examples of release-blocking negative tests

1. Valid HMAC with **unmapped phone_number_id** cannot read any hotel content.
2. One customer's identical \`wamid\` repeated 10 times creates one inbound case/message.
3. \`statuses[]\` event **must not** become an AI guest turn.
4. Meta accepts send and never issues delivery; UI shows **accepted/unknown**, not delivered.
5. Meta sends delivered before sent; status monotonic, raw evidence retained.
6. Guest says "human" or emergency: zero LLM calls, real staff case queue.
7. Staff claims and AI queue has an in-flight response: in-flight AI reply suppressed.
8. Unapproved template beyond 24 hours: **no send** and a human exception.
9. Wrong hotel account secret/token or revoked permission: refuse send, alert and do not retry infinitely.
10. Audio cannot transcribe: request typed input or a staff response, not a guessed booking.
11. PMS unavailable while guest asks for room: enquiry-only message; no confirmed booking.
12. Staff response outside 24 hours with an approved utility template: send only if category/purpose and applicable messaging policy permit.
13. Customer withdraws marketing: no promotional send, while permitted service communication follows policy.
14. Rate/spend threshold reached: hold noncritical outbound; human escalation remains available.
15. Hotel offboards: disable channel, rotate tokens and honor retention/deletion.

**Current decision:** create a new independent WhatsApp architecture PR, no production code or credentials until source review and hotel authorization.
