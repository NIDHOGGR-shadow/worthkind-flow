# Worthkind Flow — End-to-end operational flow, contracts and tests
**As of:** 2026-11-19. **ALL diagrams below are PROPOSED target operating design, NOT production-verified code.** A local, synthetic subset of the enquiry/ticket flow exists on separate draft branches; see [PROJECT_STATE.md](PROJECT_STATE.md).

## Trust and authority
**Actors:** discovering guest (unregistered), returning guest with private receipt, first-time hotel owner, property manager, reception staff, kitchen/housekeeping/maintenance/IT, hotel finance, Worthkind sales/operations/support, Worthkind engineer/on-call, approved AI runtime, third-party channel provider, PMS, hotel payment processor, platform subscription processor, and administrator/auditor. The hotel retains authority over room inventory, reservation confirmation, prices, customer service commitments and hotel guest payments. Worthkind retains authority over service subscription, entitlements and system operations. Staff and support privileges must be explicitly scoped.

**Principle:** First deploy a dependable no-AI enquiry-to-human service. AI, voice, WhatsApp, hotel booking and platform subscription are separately gated increments. No workflow may display "confirmed", "paid", "delivered" or "resolved" without source evidence.

## 1. Whole product: discovery to use, support and offboarding
~~~mermaid
flowchart TD
  A[Buyer discovers Worthkind Flow] --> B[Discovery and honest capability demo]
  B --> C{Authorized hotel buyer and viable need?}
  C -- No --> Z[No customer onboarding; record feedback]
  C -- Yes --> D[Commercial agreement and privacy roles]
  D --> E[Verify hotel organization, property and domain]
  E --> F{Ownership and compliance checks pass?}
  F -- No --> X[Manual verification or stop]
  F -- Yes --> G[Invite manager and scoped staff]
  G --> H[Approve hotel policy, contact routes and content]
  H --> I{Pilot readiness and operator coverage?}
  I -- No --> J[Hold activation; document missing dependency]
  I -- Yes --> K[Activate direct human enquiry channel]
  K --> L[Guest enters approved property page]
  L --> M{Guest choice}
  M -- Direct human --> N[Submit validated enquiry]
  M -- Approved FAQ --> O{Known approved answer?}
  O -- Yes --> P[Show cited hotel fact; offer human]
  O -- No --> N
  M -- AI requested and enabled --> Q{Active entitlement, budget and policy?}
  Q -- No --> N
  Q -- Yes --> R[Safe agent answer or typed proposal]
  R --> S{Side effect independently authorized?}
  S -- No or uncertain --> N
  S -- Yes --> T[Invoke approved domain adapter]
  T --> U{Verified downstream outcome?}
  U -- No --> V[Pending reconciliation and human exception]
  U -- Yes --> W[Show authoritative outcome]
  N --> AA[Commit case, receipt, audit, outbox atomically]
  AA --> AB[Staff queue and real notification attempts]
  AB --> AC{Acknowledged by authorized employee?}
  AC -- No --> AD[Escalation during staffed hours; truthful pending state]
  AC -- Yes --> AE[Staff action, response or department ticket]
  AD --> AE
  AE --> AF[Recorded closure evidence and guest status]
  V --> AE
  P --> AG[Guest exits or creates enquiry]
  W --> AG
  AF --> AG
  AG --> AH[Consent-governed follow-up, measurable operations]
  AH --> AI{Support issue, complaint or dispute?}
  AI -- Yes --> AJ[Manual investigation with source records]
  AJ --> AK[Correct or reconcile; audit and notify]
  AK --> AH
  AI -- No --> AL[Renewal, feedback, feature review]
  AL --> AM{Hotel terminates?}
  AM -- No --> K
  AM -- Yes --> AN[Revoke agents, staff access, channels and billing]
  AN --> AO[Export/retain/delete under approved policy]
  AO --> AP[Account closure and audit archive]
~~~

## 2. Principal role journeys, including first use and return
~~~mermaid
flowchart LR
  subgraph Guest
    G1[New or returning visit] --> G2[View only approved hotel facts]
    G2 --> G3[Direct request or optional AI]
    G3 --> G4[Receive private receipt]
    G4 --> G5[Track, respond, dispute or abandon]
  end
  subgraph HotelOwner
    O1[Verify property] --> O2[Approve policies, staff and content]
    O2 --> O3[Review operational backlog and subscriptions]
    O3 --> O4[Handle exceptions and offboarding]
  end
  subgraph Staff
    S1[Accept invite and sign in] --> S2[Select allowed property]
    S2 --> S3[Claim or transfer case and ticket]
    S3 --> S4[Record response or resolution proof]
  end
  subgraph WorthkindOps
    W1[Qualify and contract] --> W2[Provision least-privilege tenant]
    W2 --> W3[Monitor delivery, cost, incidents]
    W3 --> W4[Authorized support and billing reconciliation]
  end
  subgraph Engineer
    E1[Review PR, migrations and tests] --> E2[Staging and pilot gate]
    E2 --> E3[Metrics and incident containment]
    E3 --> E4[Restore, rollback or release forward]
  end
  G3 -. creates .-> S3
  S4 -. updates .-> G5
  O2 -. defines permission .-> S2
  W3 -. investigates .-> E3
  W4 -. account records .-> O3
~~~

## 3. Container architecture and external trust boundaries
~~~mermaid
flowchart TB
  subgraph PublicClient[Untrusted browsers and channels]
    Guest[Hotel guest website and embed widget]
    Manager[Owner and staff console]
    Channel[WhatsApp, SMS, voice or email]
  end
  subgraph Worthkind[Worthkind controlled application]
    Edge[API gateway: rate limits, signature validation]
    Auth[Identity, membership, roles and consent]
    Domain[Modular domain API: cases, tickets, content, reservations]
    Agent[Optional policy-gated AI adapter]
    Ledger[Entitlements, usage and platform subscriptions]
    Data[(PostgreSQL: property scoped and transactional)]
    Worker[Outbox worker and callback inbox]
    Audit[Audit and metrics with redaction]
    Ops[On-call and support console]
  end
  subgraph External[Hotel and provider authority]
    PMS[Hotel PMS and inventory]
    PSP[Hotel guest PSP]
    PlatformPSP[Worthkind subscription PSP]
    Msg[Message and voice provider]
    LLM[Approved model provider]
  end
  Guest --> Edge
  Manager --> Edge
  Channel --> Edge
  Edge --> Auth
  Auth --> Domain
  Domain --> Data
  Domain --> Audit
  Domain --> Agent
  Agent --> LLM
  Agent --> Domain
  Domain --> Worker
  Worker --> Msg
  Msg --> Edge
  Domain --> PMS
  Domain --> PSP
  Ledger --> PlatformPSP
  Edge --> Ledger
  Worker --> Data
  Ops --> Audit
  Ops --> Auth
  Audit --> Data
~~~
**Source of truth:** PostgreSQL controls internal case/ticket state; PMS controls room availability and reservation; hotel PSP controls payment settlement/refund; platform PSP controls Worthkind subscriptions; messaging provider controls delivered/read outcomes. Keep distinct provider references and status evidence in local records, not copied success claims.

**Proposed deployment choice:** Keep the existing FastAPI backend as an initial modular monolith; add managed PostgreSQL, durable outbox worker and an independent authentication service/verified memberships. Preserve Worthkind movement website. Use an API integration rather than absorbing Hotel OS/Zuvamo codebases or running 15 microservices. Select provider and hosting based on the pilot contract; neither is claimed as deployed.

## 4. Sequence: guest enquiry → hotel employee → verified response
~~~mermaid
sequenceDiagram
  autonumber
  actor Guest
  participant Web as Guest UI
  participant API as Worthkind API
  participant DB as Tenant database
  participant Worker as Outbox worker
  participant Provider as Messaging provider
  actor Staff
  Guest->>Web: Submit contact, purpose and details
  Web->>Web: Create stable request key and secret receipt
  Web->>API: POST /enquiries
  API->>API: Rate limit, validate fields, resolve property
  API->>DB: Transaction: deduplicate key and payload
  alt Duplicate with same input and proof
    DB-->>API: Existing case and status
  else Different payload with same key
    DB-->>API: Conflict; no new case
  else New valid enquiry
    API->>DB: Insert case, audit and outbox together
  end
  API-->>Web: Queued receipt; no reservation claim
  Web-->>Guest: Receipt and truthful tracking status
  Worker->>DB: Claim pending event with lease
  Worker->>Provider: Send via authorized channel and idempotency key
  alt Provider error or network uncertainty
    Worker->>DB: Retry state with backoff; keep pending
    Worker-->>Staff: Escalate if aging or dead-letter
  else Provider accepts
    Provider-->>Worker: Provider message ID only
    Worker->>DB: Record accepted, not delivered
    Provider-->>API: Signed delivered/failed status webhook
    API->>DB: Deduplicate callback; update status and audit
  end
  Staff->>API: Signed-in and property-scoped claim
  API->>DB: Compare-and-set queued to claimed
  alt Unassigned or wrong property
    API-->>Staff: 403/404/409; no state mutation
  else Claimed by this employee
    Staff->>API: Respond with attributable message
    API->>DB: Response, audit and outbox in same transaction
    API-->>Staff: Response queued; delivery pending
    Guest->>API: Read case with receipt proof
    API-->>Guest: Recorded response plus delivery state
  end
~~~
**Dev reality:** PR #2 implements local enqueue, claim/reply, receipt and idempotency tests. The real provider and individual employee identity in this diagram are not implemented.

## 5. Sequence: paid agent subscription and embedding
~~~mermaid
sequenceDiagram
  autonumber
  actor Owner as Hotel owner
  participant App as Hotel console
  participant API as Worthkind API
  participant Bill as Worthkind payment provider
  participant DB as Tenant and billing DB
  participant Widget as Hotel embedded widget
  participant Agent as Safe agent adapter
  actor Guest
  Owner->>App: Choose explicitly priced plan
  App->>API: Start checkout with authorized owner identity
  API->>DB: Create pending subscription order
  API->>Bill: Provider checkout request with stable reference
  Bill-->>Owner: Hosted payment authorization
  Bill-->>API: Signed event, possibly delayed or duplicated
  API->>Bill: Independent transaction verification
  alt Invalid signature, wrong amount or unverified payment
    API->>DB: Record disputed/pending; no entitlement
  else Verified and reconciled
    API->>DB: Commit subscription, plan/version and entitlement
    API-->>Owner: Active after verified reconciliation
  end
  Owner->>App: Approve property knowledge, domains and budget
  App->>API: Install public widget ID and allowed origins
  Guest->>Widget: Ask question
  Widget->>API: Resolve public widget installation
  API->>DB: Verify property, entitlement, cost ceiling and quotas
  alt Disabled, over budget, invalid origin or unsafe
    API-->>Widget: Direct human path available
  else Allowed
    API->>Agent: Scoped content with typed tools, no broad credentials
    Agent-->>API: Answer, abstain or proposed action
    API->>DB: Audit input classification and metered usage (deduplicated)
    API-->>Widget: Grounded answer or human handoff
  end
  Bill-->>API: Renewal, failed invoice, cancellation or dispute
  API->>DB: Reconcile and version entitlement changes
~~~
**Not implemented:** this is a proposed paid-agent design; no Worthkind Flow live subscription processing or agent entitlement is verified.

## 6. Sequence: source-confirmed hotel room booking and payment
~~~mermaid
sequenceDiagram
  autonumber
  actor Guest
  participant API as Worthkind API
  participant PMS as Authorized hotel PMS
  participant Pay as Hotel-owned PSP
  participant DB as Worthkind records
  actor Finance as Hotel finance/staff
  Guest->>API: Search dates, occupancy, room type
  API->>PMS: Read live availability and quote version
  alt PMS offline or no authorization
    API-->>Guest: Cannot confirm availability; enquiry only
  else Valid expiring quote
    PMS-->>API: Quote ID, inventory, amount, currency, expiry
    API->>DB: Persist quote and checkout idempotency key
    Guest->>API: Confirm checkout intent
    API->>PMS: Place atomic hold if supported
    API->>Pay: Create hotel PSP checkout with provider reference
    Pay-->>Guest: Hosted checkout
    Pay-->>API: Signed callback
    API->>Pay: Verify amount, currency, merchant and settlement state
    alt Payment unverified, duplicate or late
      API->>DB: Pending review; do not claim booked or paid
      API->>Finance: Exception and authoritative lookup
    else Payment verified
      API->>PMS: Confirm reservation idempotently
      alt PMS acknowledgement confirmed
        PMS-->>API: Unique hotel booking reference
        API->>DB: Commit reconciled confirmed record, audit and outbox
        API-->>Guest: Confirmed by hotel source ID
      else PMS unknown or times out
        API->>DB: Paid but reservation unknown, reconciliation required
        API->>Finance: Manual resolution, possible refund policy
        API-->>Guest: Pending verification, contact desk
      end
    end
  end
~~~
**Important:** Payment success is not proof of a booked room. Quote expiry, two concurrent customers, hold expiry, cancellation and refund remain explicit hotel-policy and adapter tests.

## 7. Critical state lifecycle: guest case and staff ownership
~~~mermaid
stateDiagram-v2
  [*] --> validating
  validating --> rejected: invalid data, rate limit or wrong property
  validating --> queued: atomic create and receipt proof
  queued --> claimed: compare-and-set by authorized employee
  queued --> escalated: age past approved coverage window
  escalated --> claimed: supervisor reassigns
  claimed --> responded: response committed and outbox pending
  claimed --> escalated: transfer, shift ends or owner unavailable
  responded --> resolved: outcome confirmed by staff policy
  responded --> disputed: guest challenges outcome
  resolved --> disputed: reopened within policy
  disputed --> claimed: authorized re-review
  queued --> cancelled: valid guest withdrawal before work
  responded --> cancelled: allowed cancellation with audit
  rejected --> [*]
  resolved --> [*]
  cancelled --> [*]
~~~
Current PR #2 states only queued → claimed → responded. Escalation, cancellation, resolved/disputed and genuine delivery require new code and hotel-specific policy.

## 8. Critical state lifecycle: hotel reservation and subscription
~~~mermaid
stateDiagram-v2
  state "Reservation" as Reservation {
    [*] --> requested
    requested --> quoted: verified availability
    requested --> enquiry_only: PMS unsupported
    quoted --> expired: quote TTL
    quoted --> checkout_pending: checkout intent
    checkout_pending --> payment_unknown: timeout or callback missing
    checkout_pending --> payment_verified: PSP verification
    payment_verified --> confirmation_pending: PMS call
    confirmation_pending --> confirmed: authoritative booking ID
    confirmation_pending --> reconcile: unknown response
    reconcile --> confirmed: hotel confirms
    reconcile --> refund_pending: no room or hotel rejection
    confirmed --> cancellation_requested: guest or staff approval
    cancellation_requested --> cancelled: PMS confirms cancellation
    refund_pending --> refunded: PSP verifies refund
  }
  state "Worthkind subscription" as Subscription {
    [*] --> trial_or_pending
    trial_or_pending --> active: subscription PSP verified
    trial_or_pending --> blocked: verification fails
    active --> grace: renewal payment failure per policy
    active --> cancelled: cancellation and end-of-term check
    grace --> active: renewal reconciled
    grace --> suspended: grace exhausted
    suspended --> active: verified restoration
    cancelled --> closed: export/offboard and retention
  }
~~~

## 9. Proposed relational entity model and property isolation
~~~mermaid
erDiagram
  ORGANIZATION ||--o{ PROPERTY : owns
  ORGANIZATION ||--o{ STAFF_MEMBERSHIP : has
  STAFF_IDENTITY ||--o{ STAFF_MEMBERSHIP : receives
  PROPERTY ||--o{ STAFF_MEMBERSHIP : scopes
  PROPERTY ||--o{ APPROVED_CONTENT : publishes
  PROPERTY ||--o{ GUEST_CASE : receives
  GUEST_CASE ||--o{ SERVICE_TICKET : may_spawn
  PROPERTY ||--o{ SERVICE_TICKET : owns
  GUEST_CASE ||--o{ CASE_MESSAGE : records
  PROPERTY ||--o{ AGENT_CONFIGURATION : configures
  ORGANIZATION ||--o{ SUBSCRIPTION : pays_for
  SUBSCRIPTION ||--o{ ENTITLEMENT : grants
  PROPERTY ||--o{ WIDGET_INSTALLATION : deploys
  PROPERTY ||--o{ BOOKING_QUOTE : requests
  BOOKING_QUOTE ||--o| RESERVATION : becomes
  RESERVATION ||--o{ PAYMENT_ATTEMPT : references
  PROPERTY ||--o{ USAGE_EVENT : emits
  PROPERTY ||--o{ PROVIDER_EVENT_INBOX : receives
  PROPERTY ||--o{ EVENT_OUTBOX : queues
  PROPERTY ||--o{ AUDIT_EVENT : records
  ORGANIZATION {
    uuid id PK
    string legal_name
    string status
  }
  PROPERTY {
    uuid id PK
    uuid organization_id FK
    string verified_domain
    string time_zone
  }
  STAFF_IDENTITY {
    uuid id PK
    string provider_subject UK
  }
  STAFF_MEMBERSHIP {
    uuid id PK
    uuid property_id FK
    uuid staff_identity_id FK
    string role
    string status
  }
  GUEST_CASE {
    uuid id PK
    uuid property_id FK
    string idempotency_key
    string receipt_hash
    string status
  }
  SERVICE_TICKET {
    uuid id PK
    uuid property_id FK
    uuid guest_case_id FK
    string status
  }
  BOOKING_QUOTE {
    uuid id PK
    uuid property_id FK
    string pms_quote_ref
    datetime expires_at
  }
  RESERVATION {
    uuid id PK
    uuid property_id FK
    string pms_booking_ref
    string status
  }
  PAYMENT_ATTEMPT {
    uuid id PK
    uuid reservation_id FK
    string provider_reference UK
    string verification_state
  }
  SUBSCRIPTION {
    uuid id PK
    uuid organization_id FK
    string platform_psp_ref
    string state
  }
  EVENT_OUTBOX {
    uuid id PK
    uuid property_id FK
    string event_key UK
    string delivery_state
  }
  PROVIDER_EVENT_INBOX {
    uuid id PK
    uuid property_id FK
    string provider_event_id UK
    string processing_state
  }
  AUDIT_EVENT {
    uuid id PK
    uuid property_id FK
    string actor_id
    string action
  }
~~~
**Migration invariants (proposed):** PostgreSQL foreign keys, unique property/idempotency pairs, version/compare-and-set on critical resources, a composite property ownership check on cross-references, encrypted personal data, row-level access policies tested by role, and strict separation of guest PSP/merchant credentials from platform billing. Synthetic fixtures only in dev/test.

## 10. Failures, retries, unauthorized access and escalation
~~~mermaid
flowchart TD
  A[Operation begins] --> B{Identity and tenant permitted?}
  B -- No --> C[Reject 401/403/404, no private data or writes]
  B -- Yes --> D{Input and invariant valid?}
  D -- No --> E[422/409 with correction path]
  D -- Yes --> F[Write intent plus audit and outbox atomically]
  F --> G{Local transaction committed?}
  G -- No --> H[Rollback; safe client retry with same key]
  G -- Yes --> I[Return receipt or pending status]
  I --> J{External effect needed?}
  J -- No --> P[Resolve internal state]
  J -- Yes --> K[Worker lease, retry budget and signed provider call]
  K --> L{Provider response known?}
  L -- Accepted --> M[Record accepted only, wait for signed status]
  L -- Failed transient --> N[Backoff and replay same event key]
  L -- Timeout or ambiguous --> O[Lookup external source before retry]
  M --> Q{Delivered or business confirmed?}
  Q -- Yes --> P
  Q -- No --> O
  N --> R{Retry budget exhausted?}
  R -- No --> K
  R -- Yes --> S[Dead-letter queue; alert named on-call/owner]
  O --> T{Source-of-truth outcome found?}
  T -- Yes --> P
  T -- No --> S
  S --> U[Human resolution, possible cancellation/reversal]
  U --> V[Audit decision and notify via allowed channel]
  P --> W[Update visible source-labelled outcome]
  V --> W
~~~
**Never** blindly retry money-related side effects whose outcome is uncertain. Deduplicate inbound webhooks using stable provider event IDs; verify signature and event ownership before parsing sensitive event data. Lost client responses reuse the original key and receipt. For poor networks, show queued/unknown truthfully and allow safe status refresh; no fake offline booking confirmation.

## 11. Product lifecycle and stage gates
~~~mermaid
flowchart LR
  A[Research buyer problem] --> B[Validate hotel staff workflow]
  B --> C{Qualified pilot and owner authority?}
  C -- No --> D[Revise scope or stop]
  C -- Yes --> E[PRD and threat/permission model]
  E --> F[Build vertical slice on branch]
  F --> G[Unit, integration and negative security tests]
  G --> H{Pass with evidence?}
  H -- No --> F
  H -- Yes --> I[Staging, migration/restore rehearsal]
  I --> J{Hotel and engineering signoff?}
  J -- No --> F
  J -- Yes --> K[Limited supervised pilot]
  K --> L[Observe latency, costs, missed cases, incidents]
  L --> M{Safe and useful?}
  M -- No --> N[Rollback, fix, incident review]
  N --> F
  M -- Yes --> O[Commercial release and documented support]
  O --> P[Renewals, security updates, evaluations]
  P --> Q{Retire property or product?}
  Q -- No --> L
  Q -- Yes --> R[Revoke access and tokens, settle billing]
  R --> S[Export, retention/deletion and evidence archive]
~~~

## 12. Minimum permissions matrix (proposed, server enforced)
| Operation | Guest | Reception | Department | Hotel manager | Hotel finance | Worthkind support |
|---|---|---|---|---|---|---|
| View public facts | Approved only | Yes | Yes | Yes | Yes | Public only |
| Create enquiry | Yes with rate limit | For own property | If permitted | Own property | Restricted | No impersonation |
| Track private case | Receipt proof only | Own property's cases | Assigned/allowed | Own property | Finance-relevant only | Break-glass approved |
| Claim/respond ticket | No | Own queue | Assigned queue | Assign/escalate | Billing tickets only | No normal access |
| Approve hotel knowledge | No | Suggest | Suggest | Publish | Restricted | Cannot publish |
| Invite/revoke staff | No | No | No | Yes, scoped | No | Only delegated, audited |
| Change pricing/availability | No | PMS-approved staff | No | Hotel/PMS policy | Hotel finance policy | Never |
| Authorize hotel refunds | No | Request only | No | Hotel policy | Hotel/PSP delegated | Never |
| Manage agent/usage ceiling | No | View if permitted | No | Yes | Financial view | With approval |
| Change Worthkind platform billing | No | No | No | Authorized subscriber | Authorized payer | Audited finance role |
| Export/delete guest data | Proof-based request | No | No | Approved controller workflow | No | Only authorized DPA workflow |

**No global administrator bypass** of tenant privacy by default; break-glass requires an authorized reason, expiry and immutable trace.

## 13. Important operations: responsibilities and consistency
| Trigger / owner | Validations and data changes | External dependency | Failure, safe retry and visible outcome | Audit/consistency proof |
|---|---|---|---|---|
| Hotel owner applies / Worthkind ops | Verify representative and property; create pending org/property | Identity/domain verification | No approval: do not activate; resume with same application ID | Onboarding decision, actor, policy version |
| Manager invites staff / auth API | Manager membership, invite expiry, role, property; add pending membership | Identity email provider | Expired/replayed invite rejected; reissue with new secret; show pending | Invite and revocation events; test cross-property |
| Guest submits / case API | Bounded fields, purpose, consent, rate limit; create case, hashed receipt, audit/outbox | None to commit case | Timeout retry same idempotency+receipt; show queued, not booked | Unique(property, key), duplicate conflict, rollback |
| Staff claims and replies / case API | Individual membership, permission, case version and owner; claim/message update | Outbound messaging worker | Concurrent claim 409; response queued pending delivery; retry safe on stable command ID | CAS plus audit/outbox and who replied |
| Ticket transfer/escalation / staff API | Valid assigned owner and department, actual business hours | Optional notification provider | Unstaffed: owner exception queue and honest status; never silent closure | Ticket history and immutable transitions |
| Provider sends notification / worker | Consent/allowed template, destination, lease, event key; delivery status | Email/SMS/WhatsApp | Retry bounded on transient failure; reconcile ambiguous provider response; show accepted≠delivered | Provider IDs, signed callback, inbox dedupe |
| Agent answers / API gate | Active entitlement, property knowledge revision, budget, permission, safe tool scope | Approved model provider | Timeout/cost cap/prompt injection: abstain/human fallback; no side effect retry without authority | Model/prompt version, spend and tool trace redacted |
| Guest requests booking / booking API | PMS availability, quote TTL, amount, concurrency, hotel merchant | PMS and hotel PSP | Hold failure: no checkout; unknown payment: pending reconciliation; never say confirmed | PMS/PSP refs; financial exception trail |
| Hotel subscription/renewal / billing API | Owner identity, plan/version, currency, signed PSP verification, entitlement interval | Worthkind subscription PSP | Failed webhook: reconcile, no early entitlement; duplicate safe with PSP key | Sub ledger separate from hotel booking funds |
| Guest disputes, cancels, requests deletion / support | Proof, policy, record authority, exception approver | PMS/PSP/communications if relevant | Hold disputed state, never discard evidence; notify resolution and offboard per policy | Decision, callback evidence, retention clock |

## 14. Flow → requirement → system component → verification
| Requirement | Evidence and acceptance gate | Backend/entity | Test |
|---|---|---|---|
| REQ-001 Resolve a real hotel | Authenticated manager approves property; public slug cannot confer access | property, verified_domain | T01 unknown domain/property |
| REQ-002 Invite individual staff and revoke | Revoked/wrong-property employee gets no read/write | auth, membership | T02 role matrix, logout/revocation |
| REQ-003 No-AI human option | Human/direct path works with AI disabled | guest UI, case API | T03 20 complete no-AI scripts |
| REQ-004 Capture request exactly once | Concurrent duplicate never creates two cases | case API, unique key | T04 race and network retry |
| REQ-005 Protect guest status | Non-holder cannot view private record | hashed receipt, case read | T05 cross-tenant and token guessing |
| REQ-006 Atomic audit/outbox | Rollback leaves no orphan case/event | transaction, audit/outbox | T06 injected crash |
| REQ-007 One human owner per case | Concurrent claims permit exactly one active assignee | claim API, version | T07 two-employee CAS |
| REQ-008 Honest notification status | API acceptance not displayed as delivered | outbound worker, callback inbox | T08 failed/delayed/duplicate callbacks |
| REQ-009 Scoped hotel content | Unapproved/foreign facts never answer | approved_content | T09 content policy and abstention |
| REQ-010 Paid agent authorization | No subscription, wrong origin or over-budget calls blocked | entitlement, installation, usage | T10 failed payment/expired budget |
| REQ-011 Booking truth | PMS booking ID required to show confirmed | quote/reservation/PMS | T11 racing stock, expiring quote |
| REQ-012 Payment integrity | Signed verification, amount/currency and merchant checked | payment_attempt, PSP inbox | T12 reordered/duplicate/fake callback |
| REQ-013 Staff ticket operations | Create, transfer, resolve and reopen with permissions | service_ticket/history | T13 department, SLA, scope |
| REQ-014 Accurate hotel reporting | KPIs labelled with source and exclude synthetic data | event/report views | T14 two-property reporting reconciliation |
| REQ-015 Data and incident recovery | Restore, replay and trace without duplicate external effects | backups, inbox/outbox, logs | T15 restore and provider replay |
| REQ-016 Exit and cancellation | Revoke channels/entitlements, export/delete per agreement | retention, account/tenant | T16 offboarding + subscription dispute |

**Actual test distinction:** T01–T16 are new acceptance test IDs for target production. The development code already covers some analogous checks (idempotency, wrong property, atomic local outbox, synthetic routing) but does **not** pass this full release test matrix yet.

## 15. Edge cases that must be accepted before launch
- **First-time vs returning:** first-time hotel owner verifies property and invites staff; returning guest presents a private receipt, never guesses from name/phone; returning employee must have still-active membership.
- **Offline/poor network:** submissions may be queued by browser only if an explicit offline queue exists; otherwise inform that send is unconfirmed. No offline card charge or room confirmation.
- **Duplicate/interrupted:** reuse idempotency token after response loss; distinguish repeated user intent (new action) from repeated transport.
- **Unauthorized/wrong tenant:** deny every read/write including dashboard aggregates, files, metrics, knowledge edits and event status.
- **Provider outage:** provider-accepted, delivered, payment-authorized and reservation-confirmed are separate states; poll/reconcile against authoritative service.
- **Concurrency:** unique keys, versioned claims, quote expiry/holds and booking writes must be atomic or explicitly uncertain.
- **Cancellation/dispute:** preserve evidence and policy; hotel PSP/PMS authorizes guest money actions; platform processor authorizes Worthkind subscription actions.
- **AI failure:** deterministic direct form and staffed escalation available even if model provider unavailable; do not process financial or identity side effects from free text.
- **Staff coverage:** urgent alert cannot promise a specific response without agreed roster and emergency contacts.
- **Data deletion/retention:** confirm hotel-controller and Worthkind-processor roles, lawful bases, data transfer and retention policy before real PII.

## 16. Build order and dependencies
1. Review branch DAG and source evidence; integrate ticket code through a deliberately tested dependency path rather than treating all PR heads as equivalent.
2. M1-A: property registration, migrations, individual staff invitations, membership/RBAC, cross-tenant tests. **No live provider/PII yet.**
3. M1-B: approved hotel fact/content and safe direct guest page; low bandwidth and accessibility.
4. M1-C: unify cases, ticket history and staff ownership with idempotency and concurrency.
5. M1-D: durable worker, signed callbacks, source-truth notification state and dead letter monitoring.
6. M1-E: manager metrics with property-scoped source records; no decorative fake live KPIs.
7. M1-F: authorized pilot, backup/restore, incident on-call, staff hours, privacy and mobile browser tests.
8. M2: optional evaluated AI/voice/WhatsApp and consented follow-up; gate against entitlement and budget.
9. M3: subscription checkout **separate** from hotel guest booking; PMS/PSP adapters only after hotel authorization.
10. M4/M5: dining, events, HR/suppliers, CRM/advertising, chain management and deeper analytics after workflow evidence.

## Risks and requirements for operational support
| Risk | Containment | Owner / launch condition |
|---|---|---|
| Cross-tenant leakage | Server-side membership, PostgreSQL policy and negative tests | Engineering owner; block launch |
| Fake booking/notification outcomes | Provider ID and independently verified status | Hotel operator / engineer |
| Unanswered urgent case | Named shift/department supervisor and fallback route | Hotel manager, before live |
| AI prompt/tool abuse | Approved knowledge, typed tools, explicit consent, limits | Security lead |
| Payment dispute and double-charge | Separate PSP references, signed inbox, idempotency, finance exception | Authorized hotel finance |
| Broken worker/restore | Bounded retry, dead letter, monitoring, restore drills | Worthkind on-call |
| SaaS license/noncompliance | File-level notices, restrictions, legal review before import | Owner / legal advisor |
| Lack of willing hotel | Buyer interviews and verified pilot consent, no fabricated traction | Product owner |

**Next safe implementation slice:** Test-driven property and staff access in a dedicated PR, retaining the existing enquiry API while transitioning it away from shared dev credentials. Do not turn off the existing development prototype until replacement passes both positive and negative security tests.