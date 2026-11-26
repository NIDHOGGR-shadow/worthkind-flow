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


## Continuation: native bookings, finance and provider evidence
- Migrations 029–036 installed in hosted Supabase. The private Flow schema now has 65/65 forced-RLS tables and no direct SELECT grants to anon or authenticated. A final read-only count confirmed zero properties, native bookings, payment intents, POS receipts and PMS evidence rows.
- Native booking authority is explicitly operator-enabled only after verified inventory; Cloudbeds cannot be simultaneously enabled. Native room-night uniqueness, 15-minute holds, guest receipt confirmation, cancellation, availability and atomic date changes have passed hosted rollback tests. Native confirmed reservations use pay-at-property terms. Actual hotels must supply a verified complete inventory and applicable pricing/terms before activation.
- Multi-item purchasing batches, replay protection and atomic group approval passed hosted rollback checks. Child order receipts reuse the existing stock ledger.
- Loyverse GET receipt adapter, explicit store/currency configuration, exact amount conversion and receipt evidence are implemented. Provider evidence is not automatic invoice settlement. Provider credentials and live test remain outstanding. The API choice was made as a first supported external POS, not an exclusive provider mandate.
- Partial refund request balance reservations, distinct partial/full test/live invoice states, stay invoices and controlled unpaid voids are implemented. Financial state tests use disposable database fixtures only; no real provider charge or refund performed. Settlement read adapter compares Paystack transaction IDs, references, currencies and amounts with the internal ledger; it does not independently verify bank deposits.
- Cloudbeds reservation readback evidence persists provider states, dates and channel identifiers. The optional intent link requires staff review; matching dates do not establish guest identity. Direct Cloudbeds booking creation/modification/cancellation and OTA rate/inventory writes remain outstanding.
- CI 45712028194 passed all four jobs (native booking, purchasing and POS adapter coverage). The later finance test run 45712273365 was in progress; latest full migration regression run 45712416934 was queued. Final migration 036 and newer APIs are installed/committed but not yet CI verified.
- Initial provider docs consulted: https://developers.cloudbeds.com/reference/post_postreservation-2 ; https://developers.cloudbeds.com/reference/put_putreservation-2 ; https://developer.loyverse.com/docs/ ; https://paystack.com/docs/api/settlement/ ; https://paystack.com/docs/api/refund/ .

Remaining code: Cloudbeds direct write and OTA synchronization contracts, further native arrival/departure/folio and fiscal invoice semantics, automatic POS synchronization and refund reconciliation, broader data retention and HR lifecycle requirements. All manual activation items from Q1 remain deferred. No frontend changes, merge, or production deployment.


## Final internal operations checkpoint
- Migrations 037–043 applied to hosted Supabase; 70/70 Flow tables have forced RLS, and zero direct client SELECT grants. The hosted stay check passed and rolled back. Latest counts: zero properties, stays, PMS commands and POS evidence.
- Native stay lifecycle, room occupancy and stay folio are implemented. Checkout marks rooms dirty without asserting financial settlement. Early departure and no-show financial adjustments, room moves and consolidated cross-service folios are not implemented.
- PMS manager-authorized single-room creation, cancellation and checkout-date changes, durable command replay guards, rate jobs and readback recovery are committed. Known provider IDs permit read-only reconciliation; unknown IDs require provider investigation. Emergency connection disable is permitted without allowing a native inventory takeover. Live provider credentials are not installed and writes remain disabled by default.
- POS linked-receipt refresh worker uses leases, backoff, cancellation guards and isolated runtime credentials. Compose profile is opt-in. It does not automatically match new receipts or settle invoices.
- GitHub CI 45713938653 passed PostgreSQL integration, container build, backend runtime and restore rehearsal, including stay, PMS replay and POS refresh regression tests through migration 041. Migrations 042–043 and optional provider readiness changes are newer and require fresh CI confirmation.
- Cloudbeds documentation establishes that rate-job completion does not establish downstream OTA delivery; reservation room-level date/type changes need room-specific fields and may reprice the reservation. Keep those operations unavailable until an authorized sandbox confirms request/response contracts and guest price/terms handling. References: https://developers.cloudbeds.com/reference/put_putreservation-2 , https://developers.cloudbeds.com/docs/reservation-faqs , https://developers.cloudbeds.com/docs/revenue-management-system-rms , https://developers.cloudbeds.com/reference/get_getratejobs-2 .
- Provider acceptance remains open: Cloudbeds property and sandbox, OTA distribution, Paystack test/live transaction and refund verification, Loyverse account and worker deployment. No production transactions or provider writes performed. Q3 may proceed independently, but do not mark Q2 production-complete or conceal the remaining engineering gaps.
