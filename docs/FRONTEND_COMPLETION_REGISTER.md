# Worthkind Flow frontend completion register

This register separates source implementation from browser and hosted integration evidence. Quarters are workstreams, not measured completion percentages.

## Q1 — Guest experience and shared frontend foundation
- [x] Human-first guest service selection and responsive monochrome styling.
- [x] Preserve existing development guest, staff, tickets, operations and knowledge pages.
- [x] Add standalone versioned guest interface at `/static/guest-v1.html` in development.
- [x] Use the backend branch's same-origin `/api/v1/properties/{slug}/enquiries` contract for creation and receipt lookup.
- [x] Prevent duplicate submission, preserve identical in-memory retry proofs, validate receipt and server status, and fail without falling back to legacy storage.
- [x] Private receipt reveal, recovery, loading, error and retry controls; no persistent browser storage.
- [x] Seven versioned guest contract regression cases executed successfully against the fetched committed core and test sources in a JS harness (test doubles, not live HTTP).
- [x] Add Chromium regression coverage for versioned failure isolation and six widths across six routes.
- [ ] Execute the full Chromium suite and inspect actual rendered layouts. Previous run 12 passed JavaScript tests but failed Playwright installation on Ubuntu 26.04; runner now pinned to Ubuntu 24.04.
- [ ] Verify successful v1 creation and receipt recovery against authorized PostgreSQL-backed staging.
- [ ] Serve the v1 page and its assets through an approved same-origin frontend hosting arrangement. The backend staging middleware intentionally rejects static page routes; do not weaken it or route real users to legacy SQLite.

Q1 status: source implementation complete for this scope; browser acceptance and hosted integration remain unverified.

## Q2 — Verified staff identity and operational workspaces
- [x] Implement the versioned staff workspace at `/static/staff-v1.html` in development, preserving legacy pages.
- [x] Supabase password sign-in adapter with deployment-owned, publishable-only provider configuration, memory-only access token, explicit reauthentication on expiry, and local signout with best-effort provider revocation.
- [x] Hotel code selection, server-authorized reception queue, claim and reply; clear old property data and reject stale results.
- [x] Membership invite, accept and revoke commands for existing provider identities; do not imply identity provisioning or email delivery.
- [x] Read/update hotel settings with optimistic revision checks; AI setting is read-only.
- [x] Versioned department ticket list, creation, priority, category, case linkage, claim/start/resolve/reopen/note actions and overdue display; reuse ticket key on unconfirmed retry.
- [x] Responsive layouts, status filters, text-only rendering of private records, access-denied recovery and signout cleanup.
- [x] Seven focused Q2 contract tests passed against fetched committed source in an isolated JS harness, not hosted API calls.
- [x] Add Chromium staff UI fixture journey and 24 authenticated-module viewport checks. CI runner changed to Ubuntu 24.04 to fix Playwright installation failure on 26.04.
- [ ] Run full Chromium suite on the corrected runner and inspect rendered interfaces.
- [ ] Configure the approved Supabase identity project in deployment and test with authorized staff identities against PostgreSQL. Default sign-in is disabled; OIDC interactive login, MFA and account recovery are not implemented here.
- [ ] Deploy same-origin v1 API routing and static frontend hosting together without weakening backend staging guard.
- [ ] Connect property membership listing, staff roster, shift scheduling, shift handover, room readiness and escalation assignment workflows when versioned backend contracts exist. Current ticket due dates and reopen operations do not constitute workforce scheduling or full guest-confirmed resolution.
- [ ] Verify actual role permissions, staff identity lifecycle and cross-tenant isolation on hosted integration. Browser fixture tests do not establish production security.

Q2 status: source implementation committed for available versioned staff API contracts; remaining workflows, activation and end-to-end acceptance remain open.

## Q3 — Reservations, guest stay and commerce
- [ ] Hotel discovery, approved property content and room inventory.
- [ ] Availability, holds, booking, check-in/out, folios and verified payment outcomes.
- [ ] Dining, facilities, events, refunds and reconciliation with real provider contracts.
- [ ] Browser and integration acceptance for these flows.

## Q4 — Business management and release readiness
- [ ] Management analytics, CRM, website content, marketing, procurement and careers.
- [ ] AI Studio, voice and human handoff, platform onboarding, billing, integrations and audit.
- [ ] Full responsive visual and accessibility review, cross-workspace navigation and release tests.
- [ ] Verify deployment; no simulated success or premature production release.

Do not represent missing API contracts, provider activation or unexecuted tests as finished functionality. The existing development paths are not production identities or hotel connections.
