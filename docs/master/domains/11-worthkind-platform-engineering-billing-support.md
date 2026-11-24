# Domain 11 — Worthkind engineering, administration, billing and customer support

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Foundation architecture and GitHub draft PRs present; no proven production multi-hotel billing or support control plane. **Implementation stage:** M1–M3. **Accountable workstream:** Worthkind platform lead + billing/operations.

## Hotel/customer job and root cause to validate

Operate and support the software across multiple authorized hotels, including tenant subscriptions, issues, feature rollout, incidents and customer success.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Worthkind internal admin, hotel onboarding pipeline, authorized support ticket, metering and payment service.
- **UI/UX screens and controls:** Tenant directory, subscription plans, billing ledger, usage caps, cost by hotel, rollout feature flags, incident view, SLA, access requests and contract record.
- **Primary workflow:** Qualified lead/contract → tenant provisioning → feature activation + limits → usage metering → invoice/subscription settlement → support and incident handling → renew/upgrade/offboard.

## Domain data and authority boundary

- **Proposed data entities:** platform_plans, tenant_subscriptions, invoices, provider_cost_ledger, tenant_limits, support_cases, release_flags, incident_records, provisioning_events.
- **Source-of-truth / authorization invariant:** Platform admin cannot secretly alter hotel payments or read guest conversation bodies; support impersonation, if permitted, requires explicit hotel grant and audit..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

Exceeded messaging/model costs, failed invoice, tenant outage, breached SLA, credential leak or offboarding → preserve human routes and follow documented escalation/retention process.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

Usage meter correctness, subscription reconciliation, support role denial, emergency disable, rollback, rotation, and cross-tenant cost isolation.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **02,08,10,12,13,14**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
