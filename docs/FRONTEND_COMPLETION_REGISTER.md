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
- [x] Expanded commerce tests and 108 browser layout checks passed in GitHub Actions run 45700060628 (62/62 JavaScript tests).
- [x] Expanded Q3 browser acceptance passed on the earlier revision. Full visual inspection and newest native-stay/provider browser coverage remain open.
- [x] Native inventory holds, pay-at-property confirmation, date changes, cancellation, bookable rates, stay transitions, folios and stay invoices connected to versioned contracts. Cloudbeds reservation creation/cancellation/checkout-date and rate commands connected, with explicit authorization and no automatic retry of ambiguous writes.
- [ ] Guest dining order API and persistent guest venue tracking still absent. Keyed partial/full refund requests and unpaid invoice voiding are now connected; newest tests remain pending. Hosted booking/provider acceptance and final visual review remain open.
- [ ] Real identity, deployed gateway, authorized PMS/Paystack activation and hosted property acceptance. No live provider operation is claimed.
Q3 status: expanded implementation and prior automated verification complete for the recorded scope, with the remaining UI and hosted acceptance gaps explicitly open. Source support does not equal provider activation.

## Q4 — Business management and release readiness
- [x] Management overview using authorized records already loaded in the current session; not complete hotel analytics.
- [x] Content draft/list/publish/reject/withdraw, source reference, and guest published catalog.
- [x] Stock items, suppliers, purchase orders, stock movements, multi-item purchase batches and batch approval/cancellation.
- [x] Published vacancies, current-session draft management and staff application decisions. Guest applications require a careers receipt and explicit application consent.
- [x] Guest service preferences with revision checks and staff feedback review.
- [x] Optional communication consent and withdrawal tied to the property's published privacy-policy content version. No policy text is invented; consent control remains unavailable without published content. Hotel-approved policy publication and legal review remain operational requirements.
- [x] Cloudbeds stored evidence and command log, explicit provider writes and rate-job verification, Loyverse receipt reconciliation and Paystack settlement comparisons. No provider activation, OTA delivery or independent bank deposit is asserted.
- [x] Native stay controls and folios integrated for newly available Q3 contracts.
- [x] Property/session data cleanup, exact gateway allowlist and no automatic repeats of ambiguous PMS writes.
- [x] CI run 45714203571 passed 81/81 JavaScript tests and 138 browser geometry checks (96 staff modules, 36 routes, six guest commerce widths); this is evidence for that revision, not the latest commit.
- [x] Current source: 9 management, 7 native booking and 5 provider evidence tests passed in an isolated JavaScript harness. New Chromium fixture cases for native folio, batches, provider evidence and policy consent authored. Keyed partial/full refund requests and unpaid invoice voiding added with a contract test.
- [x] CI run 45714740609 passed 84/84 tests and 150 responsive layout checks; run 45715621512 passed 90/90 tests and 162 layout checks after AI/document integration.
- [x] Reviewed 36 staff CI screenshots (18 modules at 390 and 1440). Found excessive navigation footprint and poor desktop width utilization. Implemented grouped desktop sidebar and compact mobile selector.
- [x] Compact mobile selector and grouped desktop navigation passed CI run 45716029939 (90/90 tests, 162 responsive checks).
- [ ] Latest revision visual and full accessibility review, including real-device voice capture/playback, remain open.
- [x] AI Studio owner policy load/save with revision checks, exact approved source permission commands, optional guest and staff assistant, approved excerpts/source references and human enquiry fallback integrated with new AI gateway. Voice and alert policy flags do not establish operational voice or autonomous alerts.
- [x] AI Studio source permission listing, server-reported usage, internal insights and alert acknowledgment connected to current backend PR #3 contracts. Ticket proposal submission uses retry keys; explicit human approval or rejection uses server decisions, including expired/rejected outcomes and created ticket identity.
- [x] Guest recorded voice turns: local microphone recording, mono 16 kHz PCM WAV conversion, file selection alternative, explicit processing consent, bounded gateway with credential stripping, approved answer and optional audio playback or human handoff. Recorded voice turns are not live phone calls.
- [x] Added AI contract tests, browser fixture journeys and loopback voice gateway regression tests; JavaScript contract-test step passed on run 45771793780 before final gateway-test and responsive styling commits.
- [x] CI run 45771894800 passed 95/95 JavaScript tests and 162 responsive browser checks, including the voice gateway and AI approval fixture journeys.
- [ ] Real device microphone tests, actual Modal model activation, hosted AI/voice acceptance and AI audit completeness. Live telephony, automated CRM campaigns/advertising, platform tenant administration/subscription billing and complete analytics still require backend contracts.
- [x] Owner/manager document upload and retrieval by exact ID, 2 MB limit, binary-only gateway, attachment-only download, temporary object URL revocation on property/session reset. Default-off gateway flag WF_FRONTEND_DOCUMENTS_ENABLED=1 requires approved document handling policy and storage acceptance. No scan, listing or deletion API is claimed.
- [ ] Document malware screening, listing/deletion and hosted acceptance; identity recovery/MFA, dedicated shift handover, guest-confirmed resolution and historical vacancy draft listing remain open.
- [ ] Hosted frontend gateway, approved identity project, property isolation tests, provider activation, live acceptance and integration with backend PR #3. Do not mark a live deployment without verification.

Q4 status: property management, provider integration, AI policy/assistant, internal alerts, explicit approval workflows, recorded voice and private document controls implemented. Expanded AI/voice fixture browser and gateway acceptance passed in run 45771894800. Full release remains open. PR #2 remains draft; live provider and hosted acceptance are unverified.

Do not represent missing API contracts, provider activation or unexecuted tests as finished functionality. The existing development paths are not production identities or hotel connections.

## Frontend-only refinement
- [x] Guest service shortcuts, concise service copy, receipt navigation and explicit clipboard action with manual fallback and private-data cleanup.
- [x] Staff local case/ticket search, matching counts, module announcements and property-scoped filter reset.
- [x] Static inspection: both versioned entry scripts parse, no duplicate IDs, no missing literal DOM hooks or label targets in either entry page.
- [ ] New Chromium regression cases and guest screenshot capture committed through 461b9ed82cfc0507003bfcc2b6a32551c2f6f2dd; latest full execution and visual inspection not yet verified. No backend or infrastructure changes made during this refinement.
