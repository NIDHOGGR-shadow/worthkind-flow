# Worthkind Flow — Local Operations Dashboard

**Status:** Local development reference; no real hotel data, booking authority, payment gateway, subscription meter or AI/voice connector. Uses the same private SQLite database as the guest and service desk screens.

## How to open

From the repo project directory, run:

    python scripts/local_dev.py start --seed-demo

Then open http://127.0.0.1:8765/staff/overview in the same local browser. Choose a demo hotel and enter the temporary per-property staff key printed by the runner. After creating tickets at /staff/tickets and guest enquiries at /, reload the property overview.

## Counts and source of truth

The new backend endpoint is GET /api/properties/{slug}/staff/overview. It explicitly requires the existing development-only X-Staff-Key, resolves the property server-side, and reads a consistent SQLite transaction snapshot. Its response has cache control no-store and contains no name, contact, or free-text guest detail fields.

| UI metric | Actual local SQL source | Meaning |
| --- | --- | --- |
| Guest enquiries | cases rows for resolved property | Total cases, regardless of provider delivery |
| Queued / claimed / replied | cases.status groups | Local case workflow state; a reply is not an external notification |
| Department tickets | service_tickets rows for property | Internal work requests |
| Unresolved | service_tickets where status is not resolved | Does not prove SLA or employee availability |
| Overdue | active service_tickets whose due_at is earlier than UTC now | Based on locally configured example priority windows, not contracted SLA |
| Pending local events | outbox + ticket_outbox processed_at IS NULL | Number of pending **local event records**, not customer messages or provider delivery |
| Recent enquiries | cases id, kind, status and created_at only (max eight) | Excludes guest name, contact and details |
| Recent tickets | service_tickets id, category, status, priority and due_at only (max eight) | Excludes subject/description (may be sensitive) |

Never substitute production-style occupancy/room availability, arrivals, bookings, hotel payments, AI usage or Worthkind revenue when no source exists. They remain null in the API and are visibly labelled Not connected on the page.

## Authorization and privacy caveats

- Hotel scoping is enforced in the API and SQLite WHERE property_id filters. The staff key is a shared **demo** property key, not an individual human principal or future tenant RBAC.
- Staff secret and all returned case/ticket content remain in memory only and are cleared from the visible dashboard on property or key change; old requests are ignored.
- No keys are written to localStorage, sessionStorage, cookies or the URL.
- The preview is for synthetic cases only; the existing SQLite case table still stores guest contact data in plaintext. Do not enter real hotel customer information.
- An outbox row or dev simulation mark is never evidence of notification delivered.
- Do not expose the developer service on a public host. Production startup remains forbidden.

## Verification and next steps

- Automated Python tests in apps/api/tests/test_operations_dashboard.py test empty values, actual SQL counts, linked ticket transitions, overdue, no-store policy, 401 denial, wrong-property isolation and no fabricated provider delivery.
- Automated Node fake-DOM tests in apps/web/tests/overview-ui.test.cjs exercise real API-source rendering, no guest HTML injection, key switching, late response, inaccessible data and secret visibility.
- Browser accessibility and responsive checks at 320px, 390px, tablet and desktop remain manual until actual browser automation has run.

Next: add hotel-approved local knowledge draft/review workflow, case handoff/reporting, optional disabled-provider contracts, and broader end-to-end acceptance checks. Online databases and external APIs remain paused by the owner.
