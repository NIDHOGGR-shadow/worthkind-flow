# Domain 02 — Hotel registration, onboarding and multi-tenancy

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Synthetic demo hotel identities in PR #2; no production tenant onboarding or signed pilot. **Implementation stage:** M1. **Accountable workstream:** Platform backend/security + founder + hotel owner.

## Hotel/customer job and root cause to validate

Verify operator and property, obtain explicit agreement, configure brand, locations, staff owners, departments, response hours, services and authorized integration scope.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Worthkind sales/design-partner application and approved administrative console.
- **UI/UX screens and controls:** Pilot interest → company/property verification → service configuration checklist → role invites → content approval → sender/provider setup → sandbox preview → go-live checklist.
- **Primary workflow:** Sales-approved hotel → legal/property authority check → create organization and property IDs → approve domains/brand/privacy → invite staff with roles → configure source-of-truth systems and hours → dry-run isolation checks → activate feature flags → monitor/offboard.

## Domain data and authority boundary

- **Proposed data entities:** organizations, properties, domains, subscriptions, onboarding_checks, departments, staff_invites, integration_grants, tenant_feature_flags, audit_events.
- **Source-of-truth / authorization invariant:** Organization owns its hotels; property-scoped users must not see sibling properties unless explicitly authorized. Worthkind support cannot impersonate hotel staff without audited, time-limited authorization..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

Domain collision, unauthorized person, duplicate property, invalid contact, revoked token, failed webhook or overdue checklist → keep inactive and rollback onboarding.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

Property/domain uniqueness, account invites/expiry/revocation, 2-hotel isolation, domain ownership proofs, offboarding/deletion, migration and re-activation drills.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **08,11,13,14**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
