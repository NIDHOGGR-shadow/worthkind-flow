# Integration policy — no invented bookings

Worthkind Flow P0 is a verified **enquiry and staff handoff** tool. A real PMS/booking engine connector will need a hotel-approved integration agreement and these capabilities:

1. Find hotel/room/category inventory for explicit dates, guest count and currency.
2. Retrieve taxes, fees, cancellations, occupancy and policy version as **server-authoritative** quote data.
3. Atomically hold inventory if the provider supports holds. If not, use its native checkout.
4. Map guest consent and data minimization to provider booking requirements.
5. Create a unique checkout intent and verify payment on backend/webhook and server-to-server inquiry.
6. Confirm the actual PMS reservation idempotently; distinguish paid/pending/confirmed/rejected.
7. Capture and reconcile out-of-order callbacks, expired holds, chargebacks, retries and partial provider outages.
8. Log immutable audit events and emit transactional outbox notifications.
9. Inform the guest only of **verified states**, and route unresolved exceptions to human finance/reception.

**Hard rule:** Never mark a room booked or a transaction paid merely because the LLM said so, the browser redirected or a background job was queued.

The connector must expose `availability()`, `quote()`, `hold()` if available, `book()`, `get_booking_status()`, `cancel()` with explicit authorization and provider support. Each operation requires an idempotency key, property authorization and strict schema validation.

Do not store card numbers or payment secrets. Secrets belong in a proper secret manager. Messaging/marketing and food/dispatch providers have separate consent, signature and acknowledgement contracts.

Read source references: https://paystack.com/docs/payments/verify-payments/ ; https://docs.stripe.com/webhooks ; https://supabase.com/docs/guides/database/postgres/row-level-security
