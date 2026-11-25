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
- [x] Department tickets, category/priority, overdue display, case linkage, retry and transitions; ticket detail/history now connected to backend's versioned read contract.
- [x] Responsive layouts, filters, text-only private record rendering and property/session cleanup.
- [x] Staff roster and employee profile updates using the schedule/profile contracts on backend PR #3.
- [x] Shift scheduling, date-range selection and cancellation using backend PR #3.
- [x] Operational room condition and revision-checked updates using backend PR #3. No occupancy or availability assertion.
- [x] Reception transfer, escalation and staff resolution with reasons. Guest receipt UI recognizes escalated/resolved without claiming guest confirmation.
- [x] Ten staff and seven guest contract tests passed using fetched committed source in isolated JS harnesses; new UI syntax and static ID checks passed.
- [x] Previous full Chromium suite passed in GitHub Actions run 45694066700 (36 route-width and 24 staff fixture layout checks).
- [x] Extend browser fixtures for schedule, escalation and room operations; 36 authenticated staff module-width checks now authored.
- [ ] Expanded Chromium suite passed in run 45695602215 (72 layout checks). Subsequent gateway HTTP tests and Chromium suite passed in run 45696044082; ticket-history browser coverage and screenshot capture passed in run 45696214366; visual inspection remains open.
- [ ] Configure an approved identity project and test real staff identities, roles and session lifecycle against authorized hosted PostgreSQL. OIDC interactive login, MFA and recovery remain outside this implementation.
- [ ] Same-origin frontend gateway and nonroot container implemented; real loopback HTTP tests passed in run 45696044082 (versioned route allowlist, no legacy exposure, no forwarded client secrets/cookies, redirect/HTML denial). Hosted deployment and upstream rate-limit topology still require verification. See docs/FRONTEND_DEPLOYMENT.md.
- [ ] Connect dedicated shift handover and guest-confirmed resolution when their backend contracts exist. Neither a ticket note nor a staff resolve command substitutes for them.

Q2 status: all currently available scoped staff API contracts implemented in source, including newly added ticket history. Four checklist gates remain open (two partially satisfied by passing automated browser/gateway tests). Backend PR #3 remains a separate integration dependency; dedicated handover, guest-confirmed case resolution, hosted identity and deployment are not claimed. Do not count fixture tests as proof of live integrations.

## Q3 — Reservations, guest stay and commerce
- [x] Published property information, room catalog, nonbinding display rates, dining menu and venues.
- [x] Receipt-scoped reservation request, unchanged retry, list, withdrawal and staff review/decline.
- [x] Receipt-scoped venue request and staff venue review/accept/decline/cancel; current-session receipt display.
- [x] Room type, physical room, display rate, menu and venue management commands. Updates require authoritative revision; public catalog does not expose current draft revisions.
- [x] Read-only Cloudbeds availability, reservation status and channel reservation lookup; no hold or quote implied.
- [x] Staff dining orders, server pricing, idempotent retry, kitchen transitions and service completion.
- [x] Dining invoice, Paystack checkout link, provider verification, refund request/approval/submission/verification and finance exceptions.
- [x] Separate test and live payment modes; exact HTTPS Paystack checkout-origin validation; no card data collection.
- [x] Same-origin gateway allowlist for Q3 routes; session/property data cleanup; responsive catalog and operational forms.
- [x] Initial nine commerce contract tests passed in GitHub Actions run 45699643768. Two additional catalog/channel tests and expanded guest/staff Chromium tests are committed; final execution not yet verified.
- [ ] Final expanded browser acceptance and full visual inspection, including newly added catalog management.
- [ ] Authoritative room holds, binding quotes, actual PMS booking/create/change/cancel, check-in/out write commands, guest dining order API, persistent guest venue tracking and broader folios/settlements. These do not exist in the scoped backend contract yet.
- [ ] Real identity, deployed gateway, authorized PMS/Paystack activation and hosted property acceptance. No live provider operation is claimed.
Q3 status: 10 of 13 tracked items implemented or evidenced; checklist count is not a production readiness or effort estimate. Source support for current APIs does not equal real provider activation. Do not advance a reservation request to confirmed without source authority.

## Q4 — Business management and release readiness
- [ ] Management analytics, CRM, website content, marketing, procurement and careers.
- [ ] AI Studio, voice and human handoff, platform onboarding, billing, integrations and audit.
- [ ] Full responsive visual and accessibility review, cross-workspace navigation and release tests.
- [ ] Verify deployment; no simulated success or premature production release.

Do not represent missing API contracts, provider activation or unexecuted tests as finished functionality. The existing development paths are not production identities or hotel connections.
