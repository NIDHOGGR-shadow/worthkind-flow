# Domain 08 — Staff, departments, roles, schedules and approvals

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Development staff keys exist; no production invite-only employee identity, separation of duties or shift planner. **Implementation stage:** M1. **Accountable workstream:** Security/auth backend + hotel operations manager.

## Hotel/customer job and root cause to validate

Ensure every business action is performed by the right person with coverage when staff are away.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Verified hotel owner invitation, employee login, staff manager or HR/admin request.
- **UI/UX screens and controls:** Staff invitations, roles and property permissions, shift schedules, supervisor approvals, away status, reassignment and access revocation.
- **Primary workflow:** Hotel owner invites staff → verify identity and set limited role → assign properties/departments → schedule and on-call coverage → record approvals and actions → rotate/revoke on departure.

## Domain data and authority boundary

- **Proposed data entities:** users, property_memberships, departments, roles, permissions, shifts, approvals, staff_devices, access_audit, delegation_grants.
- **Source-of-truth / authorization invariant:** Invite-only real user identity; least privilege per organization, property, department and action. Finance approval should not automatically be available to reception; optional staff break-glass use must be audited..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

Lost account, shift gap, absent manager, expired invite, employee dismissal or unsafe approval → deny and escalate, never fallback to shared production key.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

All role/tenant combinations, invitation expiry, revocation immediate, two-person sensitive approval, shift boundaries and emergency overrides.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **02,11,13**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
