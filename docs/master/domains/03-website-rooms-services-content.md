# Domain 03 — Hotel website, rooms, services and content management

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Separate Hotel OS website and Worthkind Flow synthetic FAQ exist; no shared multi-hotel CMS connected. **Implementation stage:** M1. **Accountable workstream:** Frontend/CMS + hotel content owner.

## Hotel/customer job and root cause to validate

Give guests accurate property descriptions, room types, amenities, service hours, images, policies and an accessible branded site that hotel staff can update.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Hotel-owned domain, CMS editor, integration sync from authorized PMS.
- **UI/UX screens and controls:** Branded homepage, rooms/suites, dining, experiences, offers, events, policies; staff content editor with draft/preview/approval/version history.
- **Primary workflow:** Hotel content draft → owner approval/version → publish tenant-scoped static/dynamic page → optionally index public facts → guest reads current version → periodic revalidation/revoke outdated content.

## Domain data and authority boundary

- **Proposed data entities:** hotel_pages, room_types, amenities, property_assets, asset_licenses, policy_versions, knowledge_versions, content_approvals.
- **Source-of-truth / authorization invariant:** Marketing content is not a live availability/price quote; real price and inventory come from PMS, and owner-approved public content alone can feed guest answers..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

Missing image/license, unapproved content, conflicting rate, unsupported policy or outage → last approved version or human clarification; never publish unreviewed rooms.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

Tenant asset isolation, content approval/revert, contrast, mobile, cached-version invalidation, policy expiry, SEO correctness and no placeholder text.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **02,04,09,13**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
