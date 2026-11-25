# Worthkind Flow backend: Quarter 1 handoff and Quarter 2 assessment
Date: 2026-11-25. Scope: backend and infrastructure only. PR #3, work/backend-infrastructure-hardening. This register supersedes the old SQLite-first constraint for this workstream because the owner authorized Supabase.

## Q1 verified foundations
- Hosted Supabase project xfxqlcmsfkbvbybkrppq, private worthkind_flow schema; eleven portable migrations, fourteen forced-RLS tables. Hosted transaction smoke test passed and rolled back. Ten NOLOGIN runtime roles have no grants on unrelated public tables or SECURITY DEFINER functions.
- Backend CI run 45689599390 passed runtime, encryption, private-document isolation and SQLite cutover tests. Later recovery/container workflow changes must be separately verified.
- Hosted private media bucket worthkind-flow-media provisioned by db/supabase/001_private_media.sql. It is private, permits only JPEG/PNG/WebP, maximum 5 MiB, and includes seven bucket-specific policies. Authorization checks confirmed nonanonymous Auth users, a matching session and active owner/manager membership. Unauthenticated helper check returned false. No real authenticated upload/download has been performed; MIME restrictions are not malware scanning.
- Staging runtime requires TLS verify-full and restricted noninheriting login credentials for readiness; SQLite seed and legacy routes are excluded. New readiness changes require fresh CI. Production mode remains blocked.
- Separate runtime and worker container contracts, versioned authenticated encryption, read-only source inventory, and disposable recovery workflow exist. No real source SQLite file has been inspected; no data migration is claimed.

## Explicitly deferred activation
The owner has deferred manual tasks. No live user, payment, production host, storage upload or secret was created as a substitute. Outstanding: real restricted DSNs with reverse privilege checks, managed secrets and key lifecycle, actual Auth account/sign-in, live media round trip and content safety, actual SQLite source inventory/migration if needed, real hosted backup restoration, final deployment and acceptance. Q1 is not production-complete.

## Q2 code-based assessment (26 work areas)
Hosted partial = a relevant versioned PostgreSQL path exists; not a complete operations domain. Legacy partial = SQLite code exists but is explicitly excluded in staging. Not implemented = no domain-specific production implementation identified in the assessed branch; generic enquiries do not count.

| Area | Status | Remaining operational work |
|---|---|---|
| Guest management | Hosted partial | Guest profiles, consent, identity, retention, preference management |
| Reception | Hosted partial | Case assignment/transfer, shift handover, departmental escalation, service SLA |
| Reservations | Not implemented | Quote, hold, intent, source-confirmed booking, change/cancellation |
| Room management | Not implemented | Room types, inventory, room status and source-aware assignments |
| PMS integration | Not implemented | Hotel-approved adapter, source refs, failure and sync handling |
| Channel management | Not implemented | Authorized channel/rate distribution and reconciliation |
| Pricing | Not implemented | Currency, taxes, rate plans, quote expiration and rules |
| Payments | Not implemented | Hotel PSP onboarding, signed callbacks, transaction verification |
| Reconciliation | Not implemented | Payment/booking matching, exceptions, audit and settlement |
| Refunds | Not implemented | Authorized refund commands, provider verification, dispute handling |
| Invoicing | Not implemented | Hotel guest folio/invoice and immutable adjustments |
| Dining | Not implemented | Menus, order intent, service acceptance, fulfilment |
| Kitchen operations | Not implemented | Kitchen queue, acknowledgement, preparation and exceptions |
| POS integration | Not implemented | Authorized POS adapter, verified orders and payment truth |
| Housekeeping | Legacy partial | PostgreSQL ticket lifecycle, room turnaround and department roles |
| Maintenance | Legacy partial | PostgreSQL tickets, assignments, maintenance history and closure |
| IT support | Legacy partial | PostgreSQL queue, assignment and service desk workflow |
| Staff management | Hosted partial | Employee records, departments, shifts, leave and supervisor workflows |
| Task management | Legacy partial | PostgreSQL task lifecycle, assignment, priority and escalation |
| Inventory | Not implemented | Stock items, movements, reconciliation and audit |
| Procurement | Not implemented | Purchase requests, approvals, purchase orders and receiving |
| Suppliers | Not implemented | Supplier master, approvals, delivery and supporting documents |
| Events | Not implemented | Event leads, venue availability, proposals and acceptance |
| Recruitment | Not implemented | Vacancies, restricted applications, review and decision audit |
| CMS | Legacy partial | PostgreSQL approved content, revisions, media rights and publication |
| Guest feedback | Not implemented | Verified feedback, moderation, complaints and resolution |

Summary: 3 hosted partial, 5 legacy partial, 18 not implemented. No Q2 domain can be marked complete. Assessment based on main.py, ticketing.py, operations.py, sla.py, knowledge.py, delivery_contract.py, portable migrations and master data/API contracts; not an exhaustive audit of every unmerged historical branch. Existing generic enquiry kinds for food/events/careers/suppliers are useful intake only.

## Recommended engineering order
1. Port reception/ticketing/SLA/approved content into versioned PostgreSQL, preserving the existing tested semantics.
2. Build hotel guest, rooms, rates and reservation domain; integrate PMS/PSP only with authorized authoritative provider contracts.
3. Implement finance, dining and kitchen/POS, then inventory and procurement.
4. Complete staff operations, events, recruitment and feedback. Add source-qualified audit and regression tests to each slice.

No frontend changes. Do not count simulated delivery, enquiry intake, or external-source placeholders as functioning integrations.
