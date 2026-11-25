# Quarter 2 backend status

Quarter 2 is substantially implemented, but is not complete or production-certified.

## Evidence
- Hosted private PostgreSQL schema: 53 tables, all with forced row-level security. Direct SELECT grants to anon/authenticated: zero.
- Migrations 012–028 applied to the selected hosted Supabase database.
- Hosted transactional checks passed for tickets, content, room/rate operations, procurement, dining, staff shifts, guest records, reservation requests, event venues and recruitment.
- CI run 45695284987 passed container build, disposable database recovery rehearsal, PostgreSQL integration and backend runtime checks. This predates the final reception, payment-mode and operational read-contract changes. Final CI run 45695695859 was queued at the time of writing.
- No hosted customer transaction, payment, refund, confirmed PMS booking or live external notification was performed.

## Functional boundaries
| Area | Implementation and remaining work |
| --- | --- |
| Guest profiles, consent and feedback | Encrypted case-based records, consent history and feedback; cross-stay identity and validated consent policies remain. |
| Reception, tasks, housekeeping, maintenance, IT | Department-scoped ticket lifecycle, SLA, history, room states, reception transfers/escalation; final changes await CI. |
| Rooms, rates, availability | Room catalog and nonbinding display rates; Cloudbeds availability adapter code, not live verified. |
| Reservations, PMS, channel management | Receipt-backed reservation requests and staff review; read-only Cloudbeds adapter. Quotes, holds, confirmed booking creation/modification/cancellation and OTA write synchronization remain. |
| Payments, reconciliation, refunds and invoices | Paystack HTTP adapter, dining invoices, verified-payment matching, exception records, dual-approved full refund workflow, test/live invoice separation. Live credentials, live verification, partial refunds, broader folios/tax and settlement reconciliation remain. |
| Dining, kitchen, POS | Internal menus, priced order lines and kitchen state transitions. External POS integration remains unimplemented. |
| Inventory, procurement, suppliers | Stock movements, supplier approval, single-item purchasing and partial receipt. Multi-line purchasing and further operational acceptance remain. |
| Staff, recruitment and events | Staff profiles and shifts, venue requests and collision prevention, restricted applications and review. Applicant attachments and further HR lifecycle work remain. |
| CMS | Draft, approval, publication and withdrawal with version tracking. |

## Deployment
Q2 code is committed to work/backend-infrastructure-hardening (PR #3), not merged into main or deployed. Live Auth, runtime database credentials, provider activation and real property acceptance remain outstanding. The initial provider choices are Paystack and Cloudbeds; neither was activated. The selected shared Supabase project contains unrelated applications outside the Flow schema. Do not use real customer records or funds until authorization and activation are verified.
