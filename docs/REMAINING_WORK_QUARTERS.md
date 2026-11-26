# Remaining engineering baseline — 2026-11-26
16 tracked packages, 4 per quarter, equally weighted for milestone accounting (not engineering hours or product-wide completeness). A package counts only with its stated evidence. An external blocker does not stop independent work; substitute another completed package while keeping the blocked one open. No production release, real charges or provider activation without approval.

| ID | Package | Evidence to close |
|---|---|---|
| Q1.1 | Verify subscription contract migration on staging | CI, exact migration 057 applied, restricted grants checked |
| Q1.2 | Subscription cancellation and replacement | Immutable record, scoped/idempotent tests, staging migration |
| Q1.3 | Contract AI allowance enforcement | Weighted quota and negative tests, staging migration |
| Q1.4 | Refresh combined release candidate | Latest backend integrated, exact route allowlist, all CI |
| Q2.1 | Platform invoices and billing reconciliation | Isolated platform ledger; real provider evidence before paid status |
| Q2.2 | CRM waitlist and operator workflows | Consent/withdrawal, controlled onboarding, verified API/UI |
| Q2.3 | Outstanding native hotel stay and dining workflow | Room-service/occupancy, room moves and financial exceptions tested |
| Q2.4 | Staff operational exceptions and reporting | Attendance corrections, leave history and relevant reporting tested |
| Q3.1 | New module interface connectivity | Role-scoped UI for latest backend operations, browser checks |
| Q3.2 | Accessibility and performance | Executed keyboard/accessibility, concurrency and load evidence |
| Q3.3 | Security and recovery | Independent review, privacy and recovery workflows, restore evidence |
| Q3.4 | Hosted runtime and observability | Restricted service credentials, HTTPS, workers and health telemetry |
| Q4.1 | Live notification acceptance | Verified sender, consented owned test address and provider receipt |
| Q4.2 | Modal chat and voice acceptance | Rotated proxy credentials, approved endpoints, real bounded provider response |
| Q4.3 | External payment/PMS/POS acceptance | Authorized test-mode reconciliation, no unapproved live transactions |
| Q4.4 | Pilot and release signoff | Combined hosted journey, approved commercial/legal/operational gates and rollback |

Baseline excludes already verified earlier work. Q1.1 completed: functional commit b3bcd6563c405688831f4e8c11fa30832a5674cf, workflows 45871072317 and 45871072748 passed; exact 057 applied to xfxqlcmsfkbvbybkrppq and provisioning vs staff read grants verified. Q1.2–Q1.4 pending. This is an initial remaining-work package inventory; refine within packages when new evidence exposes deficiencies without silently counting them completed.
