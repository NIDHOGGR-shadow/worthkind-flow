# Domain 14 — Third-party integrations, notifications and communication channels

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Zuvamo channel adapters in separate repo; Worthkind Flow docs include WhatsApp architecture only; no verified live hospitality provider integrations. **Implementation stage:** M2–M4. **Accountable workstream:** Integrations/backend + SRE + provider owner.

## Hotel/customer job and root cause to validate

Connect websites, messaging, telephony, calendars, PMS, PSP, POS, advertising, email and staff alerts without corrupting hotel business truth.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Signed provider callbacks, authorized outbound jobs, validated user/administrator requests.
- **UI/UX screens and controls:** Channel configuration, template approval, provider health, delivery receipts, retry/dead-letter queue, hotel contact route, permissions and billing view.
- **Primary workflow:** Hotel authorizes provider → store scoped credential → verify inbound signature & tenant → inbox persist/dedupe → dispatch to typed domain → write audit/outbox → send/verify status → reconcile failures and costs.

## Domain data and authority boundary

- **Proposed data entities:** provider_accounts, provider_credentials_refs, webhook_inbox, channel_messages, template_versions, outbox_events, delivery_states, integration_health, usage_ledger.
- **Source-of-truth / authorization invariant:** Message accepted is not delivered; provider callbacks never override PMS or PSP truth without matching authoritative references; external provider may be revoked/offline..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

Provider 429/5xx, out-of-order webhook, replay, WABA suspension, missed notification, SMS/voice outage → backoff, dead-letter, alternate human and honest status.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

Signed callback fixtures, wrong-tenant sender, 24h/template boundary where applicable, status sequencing, retry unknown outcome, throughput, reconciliation and kill switch.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **02,04,05,06,07,08,09,11,13**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
