# Local operations overview (SQLite only, no external APIs)

This is a development data-derived operations screen, not a live hotel-owner account. The user has deferred online databases, hosted staff authentication and provider integrations.

## Screens, data and access

- Open http://127.0.0.1:8765/staff/overview while running the local SQLite app.
- Select Demo Hotel A or B and enter its per-hotel local development key. This is not a real owner account; anyone with that shared dev key can see the same development-only hotel counts.
- The local API route is GET /api/properties/{slug}/staff/overview. It requires the same dev staff header as the reception/ticket consoles.
- On changing hotel or key, figures are hidden immediately and late responses from the prior context are discarded.
- Response headers require no-store; the dashboard does not use browser storage or expose guest names, contact details, case contents or ticket notes.

## Metrics grounded in SQLite

| Figure | Database authority | Meaning and exclusions |
| --- | --- | --- |
| Guest enquiries | cases per property | Locally recorded synthetic enquiry count, not successful bookings |
| Awaiting local staff response | cases.status not responded | Recorded cases not marked responded, not a contractual SLA |
| Unresolved tickets | service_tickets.status not resolved | Internal synthetic tickets still open/assigned/in progress/reopened |
| Overdue sample targets | unresolved service_tickets.due_at | Compares actual local due timestamps with current UTC time; demo SLA targets only |
| Service/department breakdown | grouped cases.kind and service_tickets.category | Counts from selected property only |
| Pending local events | outbox and ticket_outbox processed_at IS NULL | Local pending records, never proof of email/SMS/WhatsApp delivery |

**Intentionally not shown:** Hotel occupancy, room prices, confirmed reservation totals, hotel guest payment revenue, Worthkind subscription revenue, actual sent/delivered notifications, real AI usage and any PMS source fields. These remain unavailable until providers are authorized, integrated and reconciled.

## Tests and follow-up

- Python TestClient/SQLite integration cases cover zero-state, real record transitions, both hotels, guest case versus ticket counts, simulated overdue, unauthorized/wrong hotel, pending-only event evidence, no PII and no-store headers.
- Node simulated DOM tests verify source-qualified display, property/credential clearing, late response guard, invalid source denial and accessible key visibility.
- Manual viewport, keyboard and screen-reader checks remain unverified. No production deployment or signed hotel pilot is implied.
- A future legitimate hotel manager UI must use individual staff identities, property/organization RBAC and audit; the developer shared key is not an owner permission model.

See [LOCAL_FIRST.md](LOCAL_FIRST.md) for startup and [TICKETING_LOCAL.md](TICKETING_LOCAL.md) for linked internal ticket workflows.
