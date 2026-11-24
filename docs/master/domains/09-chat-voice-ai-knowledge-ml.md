# Domain 09 — Chat AI, voice AI, knowledge retrieval and ML lifecycle

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Zuvamo has separate agent/voice/channel components; Worthkind Flow uses deterministic rules and synthetic FAQ only; not live integrated to hotels. **Implementation stage:** M2–M4. **Accountable workstream:** AI/ML + domain backend + hotel policy approver.

## Hotel/customer job and root cause to validate

Answer permitted hotel questions, collect structured needs and assist staff while maintaining explicit human access and source-verified actions.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Website chat, voice call, voice note, future approved provider webhook and staff assistant.
- **UI/UX screens and controls:** Clear agent disclosure, voice controls/permission, typing/recording accessibility, citations/answer provenance where appropriate, human button, no-AI fallback.
- **Primary workflow:** Channel normalize → tenant and permission scope → emergency/human rules → approved knowledge retrieval → optional evaluated model/STT → typed action proposal → backend authorization → verified response → monitoring and human review.

## Domain data and authority boundary

- **Proposed data entities:** knowledge_documents, knowledge_versions, retrieval_logs, prompt_versions, model_versions, eval_datasets, action_proposals, human_takeovers, consented_feedback.
- **Source-of-truth / authorization invariant:** Agent never has unrestricted SQL or money-moving rights; hotel owns fact approval; model output is not source of inventory, payment, employment, procurement or staff completion truth..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

Hallucination, stale fact, prompt injection, STT noise, provider timeout, token spend cap, accidental PII → abstain, direct/human fallback and rollback.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

100+ approved hotel FAQ fixture (target not achieved), prompt injection, source filtering, fixed evaluation sets, STT robustness, cost limits, human bypass and no false confirmation.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **02,03,04,07,08,13,14**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
