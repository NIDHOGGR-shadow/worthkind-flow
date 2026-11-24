# Process flows — architecture source

These are **logical** process diagrams. Staff, guest, provider, payment and hotel systems are independent trust boundaries.

## 1. Guest service routing

```mermaid
flowchart TD
    A["Guest enters hotel site or approved channel"] --> B["Resolve hotel/tenant"]
    B --> C{"Interaction preference"}
    C -->|"Direct"| D["Existing booking / services / contact"]
    C -->|"Human"| E["Create staff handoff case"]
    C -->|"AI text or voice"| F["Safety and explicit human rules"]
    F -->|"Urgent or bypass"| E
    F -->|"Normal"| G["Property-scoped facts and intent routing"]
    G --> H{"Evidence sufficient?"}
    H -->|"No"| I["Clarify, abstain or handoff"]
    I --> E
    H -->|"Yes"| J["Domain read or user-confirmed action"]
    J --> K["Verify result against authorized system"]
    K --> L["Reply, audit and measure"]
    E --> M["Staff claims, acts and responds"]
    M --> L
    D --> L
```

## 2. Enquiry-first release

```mermaid
sequenceDiagram
    actor Guest
    participant Web as Hotel Website
    participant API as Scoped API
    participant DB as Cases and Audit
    actor Reception
    Guest->>Web: Request booking information or person
    Web->>API: Resolve property and start verified session
    API-->>Web: Scoped public hotel details
    Guest->>Web: Dates, preferences and enquiry
    Web->>API: Submit idempotent enquiry
    API->>DB: Commit case and audit in one transaction
    API-->>Guest: Enquiry recorded, NOT a confirmed booking
    Reception->>API: Authenticate and claim case
    API->>DB: Authorize case transition and audit
    Reception->>API: Respond to guest
    API-->>Guest: Verified staff reply and case status
```

## 3. Authorized future reservation

```mermaid
flowchart TD
  A["Guest supplies dates and guests"] --> B["PMS availability and confirmed quote"]
  B --> C{"Source data valid?"}
  C -->|"No"| D["Offer alternatives or human assistance"]
  C -->|"Yes"| E["Explain total and cancellation conditions"]
  E --> F["Optional atomic hold with expiry"]
  F --> G["Guest authorizes secure checkout"]
  G --> H["Verify signed gateway webhook and server-side transaction"]
  H --> I{"Paid exact amount and currency?"}
  I -->|"No or unknown"| J["Reconciliation case; do not charge again blindly"]
  I -->|"Yes"| K["Persist PMS reservation idempotently"]
  K --> L{"PMS confirms booking?"}
  L -->|"No"| J
  L -->|"Yes"| M["Receipt and confirmed reservation reference"]
  M --> N["Reception, pre-arrival notifications and audit"]
```

## 4. ML and safe inference

```mermaid
flowchart TD
    A["Inbound session and tenant resolution"] --> B{"Deterministic human or emergency trigger?"}
    B -->|"Yes"| C["Human service queue and monitored bypass"]
    B -->|"No"| D["Fast rules route or scoped knowledge search"]
    D --> E{"Requires inference?"}
    E -->|"No"| H["Rules/FAQ response and measurement"]
    E -->|"Yes"| F["Evaluated LLM with tenant-filtered approved context"]
    F --> G{"Grounded and authorized?"}
    G -->|"No"| C
    G -->|"Yes"| I["Confirm high-risk action with user"]
    I --> J["Constrained domain tool and source-verification"]
    J --> K{"Result successful?"}
    K -->|"No"| C
    K -->|"Yes"| H
    C --> H
    H --> L["Monitor cost, response time, errors and handoff"]
```

## 5. Transactional outbox and inbound callbacks

```mermaid
flowchart TD
    A["Authorized state-changing request"] --> B["Validate tenant, role and idempotency"]
    B --> C["Atomic business write + audit + outbox"]
    C --> D["Commit database transaction"]
    D --> E["Worker claims unpublished outbox event"]
    E --> F["Deliver message, retry if transient failure"]
    F --> G["Provider callback hits authenticated ingress"]
    G --> H["Verify signature, freshness, tenant and event id"]
    H --> I["Idempotent inbox and business-state reconciliation"]
    I --> J["Measure processing and alert on anomalies"]
```

## Why separate flows?

The guest interaction path must function even if AI is disabled. The payment path cannot assert success until external authoritative evidence exists. The human path must have owner, queue, acknowledgement and outcome. ML may classify intent but does not replace explicit access and financial controls.
