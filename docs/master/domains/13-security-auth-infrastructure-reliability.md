# Domain 13 — Security, authentication, infrastructure, reliability and incident recovery

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Local reference audit and tests exist; production authorization, migrations, backups, abuse limits, secrets and SRE controls are unfinished. **Implementation stage:** M1 and all releases. **Accountable workstream:** Security/SRE/tech lead + hotel controller.

## Hotel/customer job and root cause to validate

Prevent cross-hotel data leaks, forgery, duplicate payments, data loss, uncontrolled AI actions and silent service outages.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Every public, staff, admin, provider and AI request; build/test/deployment pipelines.
- **UI/UX screens and controls:** Passwordless/invite-only staff management, sign-in risk alerts, audit and incident dashboards, safe guest error and retry states.
- **Primary workflow:** Identity and tenant proof → least privilege → command schema and idempotency → atomic business/audit/outbox → monitored worker/provider result → alert, recover, reconcile and rollback when abnormal.

## Domain data and authority boundary

- **Proposed data entities:** audit_events, outbox_events, inbox_events, revoked_credentials, access_policies, incident_records, backup_checks, retention_policies, security_alerts.
- **Source-of-truth / authorization invariant:** Hotel tenant isolation enforced in backend and database; provider signatures verified raw; no secret in client code; least privilege with explicit approval for financial/high-risk actions..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

Data breach, compromised staff access, webhook replay, provider outage, partial write, background worker crash or lost DB → kill switch, isolate tenant, restore and reconcile before re-enabling.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

Security review, RLS negative suite, replay/signature, rotation, chaos/outbox, backup restore, penetration checks, privacy deletion/export and incident drill.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **all 14 other domains**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
