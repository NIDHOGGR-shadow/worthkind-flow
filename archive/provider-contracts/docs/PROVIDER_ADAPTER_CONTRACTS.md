# Worthkind Flow — Provider-adapter contracts (safe development scaffolding)

**Release status:** implemented source in a draft branch, **not a connection to any live hotel provider**. Worthkind Flow is a normal web application, using SQLite for development instead of Supabase until the owner approves a hosted database.

## Current source behavior

`apps/api/provider_contracts.py` defines five distinct provider boundaries:

| Service | Required future source of truth | Current operation |
| --- | --- | --- |
| PMS availability | An authorized hotel inventory/PMS response for dates and room classes | Disabled; refuses to claim rooms available |
| PMS reservation | Hotel-authorized hold and verified booking confirmation | Disabled; cannot create a booking |
| Hotel guest payments | Hotel-owned PSP or bank, independently verified status | Disabled; cannot accept or verify payment |
| Guest messaging | Authorized delivery provider with event receipts/consent | Disabled; cannot mark a message as sent/delivered |
| Optional AI | Hotel-approved facts, bounded model, human override and cost limits | Disabled; cannot claim an AI answer |

**Safe default:** The adapter registry contains `DisabledAdapter` for every service. Calling an adapter raises `IntegrationNotConnected`, never returns an apparent success or silently uses a mock. There is no library/network/credential client in this module.

**Synthetic fixtures:** `FixtureAdapter` is allowed only in test code. Its responses are marked `state=simulated` and `source=synthetic_fixture`; Pydantic rejects claims of booking confirmation, delivered message, paid charge or live room inventory. A fixture is scoped to one hotel and stores idempotency-key request fingerprints in memory, rejecting conflicting reuse.

**Data minimization:** The generic `IntegrationRequest` accepts only the property slug, action, idempotency key and opaque internal reference. Arbitrary card numbers, access tokens, guest contacts and prompts are forbidden. Future real provider APIs need dedicated typed request models, secure server-held credentials, consent and privacy controls; never put them into the generic test reference.

**Staff readiness API:** `GET /api/properties/{slug}/staff/integrations/readiness` uses the existing development property key and returns five explicitly disabled capabilities with `production_connected=false`. Data is not cached. The corresponding web interface is `/staff/integrations`, also linked from other staff pages. It can **view** readiness, never activate a provider.

## Safety gates for future real connectors

A future hotel-operator-authorized adapter must separately prove:

1. Verified property and staff role, permitted operation and provider account ownership, server-side authorization and short-lived credentials.
2. Operation-specific typed payload and consent, separate room reservation vs money verification vs messaging receipts vs optional AI outcomes.
3. Real provider source validation: signature/HMAC or token-bound response, source reference, replay-safe callback, idempotency and event timestamp. An arbitrary JSON field such as `paid=true` cannot be accepted as evidence.
4. State machine with pending/unknown/failure, timeouts, retries and dead-letter handling. Never mark an operation complete merely because a request was sent.
5. Tenant-isolation and privacy adversarial tests; cost budgets; audit redaction; accessible error/human fallback.
6. Signed-out/invalid-key behavior, cancellation/refund and outage recovery; real operator review before any production release.
7. Backup and rollback for managed database migrations; separate Worthkind subscription billing from hotel guest payments.
8. Deployment, provider sandbox or authorized pilot, then independent **production verification** using real source receipts.

## Testing and source evidence

`apps/api/tests/test_provider_contracts.py` checks disabled actions, tenant-scoped fixtures, idempotency conflicts, false-authority rejection, forbidden fields, and property-key-protected FastAPI readiness.

`apps/web/tests/integrations-ui.test.cjs` checks a real API-shaped status response, stale context/key reset, forbidden forged readiness and safe text rendering. Existing Python and JS tests still belong in `.github/workflows/worthkind-flow-ci.yml`.

**Current external CI blocker:** On 2026-11-20, GitHub Actions run [#110](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44802619267) and subsequent run [#113](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44802916635) ended with no assigned runners and no executed job steps. This is an execution blocker, not evidence that the tests pass or fail. Rerun the current draft heads when Actions resumes; until then status remains IMPLEMENTED / TEST EXECUTION PENDING.

## Usage

Start the existing SQLite development app with `python scripts/local_dev.py start --seed-demo`, open `http://127.0.0.1:8765/staff/integrations` and enter the relevant generated demo staff key.

Expected: five service cards all say **Not connected**, with no booking, payment, AI or delivery success claims. Switching hotels or changing the key clears previous data.

**Owner boundary:** no Supabase provisioning, no real provider connection, no staff permission changes and no real guest data.
