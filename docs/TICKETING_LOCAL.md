# Local departmental ticketing (SQLite only)

**Status:** Development-only integration of pre-existing ticket feature work from original draft PR #31. This is **not** an online hotel staff system, live provider integration, production permission model, actual SLA contract, or confirmed service fulfillment.

## Available local flow
1. Start the local FastAPI + SQLite app using the guide at [LOCAL_FIRST.md](LOCAL_FIRST.md).
2. From reception at http://127.0.0.1:8765/staff, choose **Department tickets**. The page is served at http://127.0.0.1:8765/staff/tickets.
3. Use your selected synthetic hotel's local development key. The ticket list and metrics are scoped to that property.
4. Create an internal ticket for IT, reception, housekeeping, maintenance, kitchen, billing or general work. Select demo priority and describe the **synthetic** problem.
5. Optionally attach a ticket to an existing receipt-only guest case, but the receptionist must first claim that enquiry. Cross-property case linkage is rejected.
6. Claim ticket → start work → add notes → resolve → reopen when appropriate; inspect full local history. All state changes and their pending outbox records are stored transactionally.
7. Change the property or staff key. Prior private ticket records and metrics are immediately cleared; any already-in-flight response must not repopulate the previous property's records.

## Key design contracts
- Shared per-hotel dev keys remain for offline-only prototyping. Real per-user staff auth and revocation are paused along with managed database/provider setup, **not** considered complete.
- Tickets and case enquiries share a local SQLite file and property scope; they have separate development outbox tables. A pending event does not mean a real message was delivered.
- SLA labels are **examples** (urgent 1h, high 4h, normal 24h, low 72h) and cannot represent any hotel's contractual commitments without approval.
- Requested departments and priorities are validated on the local API. Only the recorded dev staff actor can progress a claimed ticket, but shared keys are not individual accountability.
- The ticket UI uses DOM textContent, not guest-provided HTML. Never store real guest PII in local plaintext fields.
- No real database beyond local SQLite and no external hotel, payment, SMS, WhatsApp, email, AI, voice or PMS API is used.

## Verification
- Existing tests from the source ticket branch cover lifecycle, property isolation, idempotency, case linking, overdue/status filtering, incorrect inputs and transaction rollback.
- The new local-first branch also runs 24 direct guest→staff enquiry tests and staff/guest UI tests.
- Add manual 320/390/tablet/desktop keyboard and screen-reader checks before accepting any customer-visible UI. CI synthetic tests are not production or real browser proof.

## Deferred
Named individual staff sessions, department RBAC, authorized hotel SLA coverage, real notifications and recipient consent, offline mobile synchronization and real occupancy/payment reporting remain deferred until approved.
