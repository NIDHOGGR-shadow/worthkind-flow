# Domain 06 — Restaurant, kitchen, room service and delivery

**Scope:** one module of the Worthkind Flow multi-hotel platform, not a separate SaaS product. **Status evidence:** Design only in Worthkind Flow; Hotel OS has a dining webpage, not proven POS/kitchen integration. **Implementation stage:** M4. **Accountable workstream:** Hotel F&B/kitchen + backend/frontend.

## Hotel/customer job and root cause to validate

Help guests see approved menus, make dining requests and follow real kitchen acceptance, room-service and dispatch outcomes.

**Discovery requirement:** confirm which specific activity is failing or costly for a real hotel, who owns the current process, which system is authoritative, frequency of exceptions and what measurable change the manager would pay for. Existing architecture and screen design do not establish market demand.

## Actors, entry, and key interface

- **Entry sources:** Public menu, in-house verified stay, restaurant booking form, POS/kitchen staff, approved courier.
- **UI/UX screens and controls:** Restaurants, menus/allergens, table enquiry, room-service menu, cart/charges, kitchen status, pickup/delivery and staff order board.
- **Primary workflow:** Hotel-approved menu → availability/allergen confirmation → guest selects food and location → POS/kitchen validates prices/availability → accepts/rejects → kitchen progresses → delivery or pickup verified → closure/adjustment.

## Domain data and authority boundary

- **Proposed data entities:** restaurants, menus, menu_items, allergens, tables, dining_requests, kitchen_orders, order_status_events, delivery_jobs, refund_cases.
- **Source-of-truth / authorization invariant:** Menu content owner controls public facts; POS/kitchen decides whether an order exists; dispatch provider/staff confirms delivery; room number is insufficient proof of a guest's charging authority..
- Every write must validate organization/property, actor, purpose and version; use idempotent commands. Business state, audit and transactional outbox should commit atomically, with provider inbox and retries for external callbacks.
- System design treats personal data as private by default; no arbitrary LLM or cross-tenant admin read access.

## Failure and recovery

Sold-out item, allergy uncertainty, kitchen unavailable, rider refusal, delivery dispute → truthful pending/rejected status and human fallback.

Where a provider cannot prove an outcome, show `pending`, `unknown` or `needs_human`, not `confirmed`, `paid`, `delivered` or `resolved`.

## Test and release evidence required

Menu price/version checks, allergies absent, occupancy auth, POS rejection, duplicate order, courier failure, partial refund and operator acceptance.

Passing local/synthetic tests only establishes reference behavior. Real hotel, legal, provider and staffing acceptance must be recorded separately.

## Cross-module dependencies

Domains **02,03,05,07,08,13,14**. See [Master Architecture](../MASTER_PLATFORM_ARCHITECTURE.md), [Data Contracts](../DATA_AND_API_CONTRACTS.md), [Release Plan](../IMPLEMENTATION_ROADMAP.md), and [Platform diagrams](../diagrams/01-whole-platform.mmd).
