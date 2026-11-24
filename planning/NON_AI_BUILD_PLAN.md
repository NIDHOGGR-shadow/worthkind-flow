# Worthkind Flow — Non-AI Execution Plan (2026-11-17)

**Product direction:** Worthkind Flow supports direct guest website/service forms, human reception, and optional **existing** chat and voice AI agents. The AI channels are adapters, not the authority on hotel operations. The core must serve people when every model provider is down.

## First calls and IT-service desk initiative

**First founder call:** Perch Hotel & Suites, Surulere, published front-desk number **0808 147 8404** (https://perchhotelandsuites.com/contact/). Ask for operations/reservations, learn real enquiry pain and permission for a later follow-up. Then Green House Hotel & Suites (0808 705 4000), Kelin Heights (0706 914 2552), Adna Hotel (0813 015 2911), Triedent Suites (0906 223 0021). All are published business numbers, **not verified decision-maker mobile numbers**. No contact or consent is implied.

## Non-AI build order

| Priority | Module | Owner workstream | Immediate acceptance | Production blocker |
| ---: | --- | --- | --- | --- |
| 1 | **IT & hotel service tickets** | Backend + frontend + hotel operations | Open → assigned → in progress → resolved → reopened; notes; property isolation; SLA due / overdue; history and atomic local outbox | Invited staff identity and real approval/routing, verified SLAs |
| 2 | Staff identity and RBAC | Backend/security | Per-property, per-role staff access; staff revocation; no shared dev keys | Hosted auth, migration, secret management, RLS |
| 3 | Hotel setup | Backend + product | Property config, departments, contact and opening/working hours, timezone, approval | Real management onboarding and validation |
| 4 | No-AI guest and reception | Frontend + backend | Direct service, reliable case receipts, reception acknowledgement, human completion | Rate limits, personal data policy, real staff and messaging |
| 5 | Dashboards, notifications and escalation | Frontend + reliability | Staff task board, overdue work, event processing and actual provider receipt | Real provider, retry/dead letter and alerting |
| 6 | Verified hotel booking and payment | Integrations + finance | PMS as source of truth, signed webhooks and reconciliation | Hotel permission and supported provider APIs |
| 7 | Dining, delivery, careers, suppliers, events | Department leads + backend | Separate state machines and manual approvals | Each hotel department, operator and contract |
| 8 | Hotel waitlist / sales CRM | Product and sales | Controlled prospect contact, consent proof and pilot interest | Privacy-approved backend, staff access and sender verification |

The complete platform remains a longer-term set of modules. This PR addresses only **priority 1** and development tests. The staff UI currently relies on a **per-property shared development key**. That is insufficient to identify individual employees or meet production security standards.

## Internal service-ticket API contract

Development app from `apps/api`, launch at localhost port 8000 as documented in `DEVELOPMENT.md`.

- `GET /staff/tickets` — internal management screen
- `POST /api/properties/{slug}/staff/tickets` — idempotent ticket creation; category and priority required
- `GET /api/properties/{slug}/staff/tickets` — tenant-scoped list; filters for status/category
- `GET /api/properties/{slug}/staff/tickets/metrics` — open/in-progress/resolved counts and overdue
- `GET /api/properties/{slug}/staff/tickets/{id}` — staff-only ticket and complete history
- `POST /api/properties/{slug}/staff/tickets/{id}/claim` — open/reopened → assigned
- `POST /api/properties/{slug}/staff/tickets/{id}/start` — assigned → in progress
- `POST /api/properties/{slug}/staff/tickets/{id}/resolve` — in progress → resolved, with resolution text
- `POST /api/properties/{slug}/staff/tickets/{id}/reopen` — resolved → reopened, with reason
- `POST /api/properties/{slug}/staff/tickets/{id}/notes` — staff-only notes
- Optional `origin_case_id` from a previously claimed reception enquiry.

Every state change commits in one SQLite developer transaction: **domain state + ticket_history + ticket_outbox**. This is **not** a production event broker or delivered message. No hotel staff members are contacted by these events.

### Proposed operational SLA targets

| Priority | Target from creation | Example | Enforcement today |
| --- | ---: | --- | --- |
| Urgent | 1 hour | Internal hotel IT network outage or major guest service disruption | Flag overdue, no automatic pager |
| High | 4 hours | Essential in-room AC repair | Flag overdue |
| Normal | 24 hours | Typical housekeeping issue | Flag overdue |
| Low | 72 hours | Noncritical equipment improvement | Flag overdue |

Times are defaults for a demo. Live hotels must approve opening hours, department coverage, time zones and escalation rules. Do not represent these as service guarantees or safety dispatch capability.

## Production definition of done

1. Explicit pilot hotel and assigned department supervisors; staffed SLAs recorded.
2. Signed-in, invited individual staff roles; distinct guest and provider trust boundaries.
3. PostgreSQL tenant enforcement, migrations, backups, privacy/security review and abuse limits.
4. Real notification providers and asynchronous delivery with retries, signed callbacks, a dead-letter queue and monitored reconciliation.
5. Proper guest ticket privacy, linked receptionist updates, audited reassignments, staff escalations and full response history.
6. Integration tests against real hotel policies and end-to-end mobile and desktop accessibility.
7. Approved deployments. Existing Worthkind movement site remains isolated.

**No agent integration is needed to demonstrate or test this stage.**
