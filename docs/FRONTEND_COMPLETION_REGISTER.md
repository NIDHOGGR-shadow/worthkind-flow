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
- [x] Chromium suite passed on Ubuntu 24.04, GitHub Actions run 45694066700. Automated geometry checks are not full visual inspection.
- [ ] Verify successful v1 creation and receipt recovery against authorized PostgreSQL-backed staging.
- [ ] Serve the v1 page and its assets through an approved same-origin frontend hosting arrangement. The backend staging middleware intentionally rejects static page routes; do not weaken it or route real users to legacy SQLite.

Q1 status: source implementation and prior automated browser checks passed; visual inspection and hosted integration remain unverified.

## Q2 — Verified staff identity and operational workspaces
- [x] Versioned staff workspace with legacy pages preserved.
- [x] Configurable Supabase password sign-in, memory-only token, expiry, local signout and provider revocation attempt.
- [x] Hotel selection, server-authorized reception queue, claim and reply.
- [x] Membership invite, accept and revoke for existing provider identities.
- [x] Hotel settings read/update with optimistic revision control.
- [x] Department tickets, category/priority, overdue display, case linkage, retry and transitions.
- [x] Responsive layouts, filters, text-only private record rendering and property/session cleanup.
- [x] Staff roster and employee profile updates using the schedule/profile contracts on backend PR #3.
- [x] Shift scheduling, date-range selection and cancellation using backend PR #3.
- [x] Operational room condition and revision-checked updates using backend PR #3. No occupancy or availability assertion.
- [x] Reception transfer, escalation and staff resolution with reasons. Guest receipt UI recognizes escalated/resolved without claiming guest confirmation.
- [x] Ten staff and seven guest contract tests passed using fetched committed source in isolated JS harnesses; new UI syntax and static ID checks passed.
- [x] Previous full Chromium suite passed in GitHub Actions run 45694066700 (36 route-width and 24 staff fixture layout checks).
- [x] Extend browser fixtures for schedule, escalation and room operations; 36 authenticated staff module-width checks now authored.
- [ ] Run and verify the expanded Chromium suite on the current revision and perform visual inspection.
- [ ] Configure an approved identity project and test real staff identities, roles and session lifecycle against authorized hosted PostgreSQL. OIDC interactive login, MFA and recovery remain outside this implementation.
- [ ] Verify same-origin API routing and frontend hosting without weakening the staging guard.
- [ ] Connect dedicated shift handover and guest-confirmed resolution when their backend contracts exist. Neither a ticket note nor a staff resolve command substitutes for them.

Q2 status: 14 of 18 checklist items implemented or evidenced (78% by equal checklist count, not engineering effort). Hosted acceptance and the remaining missing contracts prevent closing Q2. API source contracts are on the unmerged backend branch; frontend fixtures are not proof of live integrations.

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
