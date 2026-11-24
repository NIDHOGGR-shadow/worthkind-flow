# Worthkind Flow — Platform Data Ownership and API Contracts

**Design proposal, not deployed schema.** Version: 2026-11-17. Applies to all [15 domains](domains/), not just one channel. Uses a modular hotel-operations backend before extracting separate services. **All public and internal APIs must enforce tenant/property/role scope in code and database**, not through model prompts or client-supplied hotel names.

## 1. Domain authority map

| Domain (owner) | Authoritative local records | External authority when integrated | Consumers |
| --- | --- | --- | --- |
| 02 Property identity/onboarding | organization, property, domain, staff invite, feature and integration grants | hotel legal owner, domain and provider verification | all domains |
| 01 Guest services | guest session/consent, request, receipt proof, preference | verified guest identity and channel evidence | reception, marketing, AI |
| 03 Content and public rooms | approved content versions, display room categories, asset licenses | hotel content manager; PMS owns *live* price/inventory | guest site, AI, booking |
| 04 Reception | enquiry, staff-assigned case, response and SLA | authorized hotel receptionist / PMS for inventory | guest, booking, service desk |
| 05 Reservations/payments | booking intent, payment references, reconciliation exceptions | **PMS owns reservation**, **PSP owns payment** | guest, finance, reports |
| 06 Dining/delivery | enquiry/order intent, task history | POS/kitchen owns accepted order; courier/staff owns fulfillment | guest, staff, reports |
| 07 IT/maintenance/housekeeping | ticket, status, evidence, assignment | hotel department and supervisor | guest, reception, reports |
| 08 Staff and approvals | staff profile, role, shift, delegated authority | hotel management-approved identity and schedules | all internal operations |
| 09 AI/ML | approved KB, model/prompt/tool version, evaluations, draft response | approved hotel facts and domain APIs, never agent inference | guest/staff assistance |
| 10 Hotel analytics | snapshots, metric definitions, breakdowns | source case, PMS, finance ledger and consented channels | owner/manager |
| 11 Worthkind platform | subscription, plan, tenant status, support issue | payments for Worthkind subscription and signed contracts | Worthkind admins, hotel billing |
| 12 Marketing/CRM | prospect status, proof of permission, campaign attribution | hotel buyer consent and verified conversion sources | sales, hotel marketing |
| 13 Security/SRE | audit, access decisions, incident, backup/restore, kill-switch | identity/provider verification and legal policy | every domain |
| 14 Integrations/channels | provider config, inbound inbox, outbound outbox, delivery events | signed provider-specific business status and terms | all workflows |
| 15 Events/HR/procurement | departmental leads and restricted applications | hotel sales, HR and purchasing approvers | department owner and reporting |

## 2. Multi-tenant identity and context

Use an immutable **organization_id**, **property_id**, actor principal, actor role(s), channel and purpose. A hotel chain may own several properties, but one guest contact can have different rights in each. A public hotel slug/domain is a *locator*, not proof of guest identity.

**Suggested request context** (constructed at the server boundary, not trusted from arbitrary JSON):

~~~json
{
  "organization_id": "server-resolved-org-uuid",
  "property_id": "server-resolved-property-uuid",
  "principal_type": "guest|staff|provider|system",
  "principal_id": "verified-or-scoped-id",
  "roles": ["reception"],
  "purpose": "guest_enquiry",
  "session_id": "session-or-conversation-uuid",
  "correlation_id": "uuid",
  "authenticated_at": "2026-11-17T12:00:00Z"
}
~~~

**Public APIs:** never accept a staff role or authoritative property/org ID supplied by the caller as their own authorization. Staff requests require verified login plus property membership and action-level policy. Provider callbacks require valid signature, exact provider identity, replay guard and tenant mapping. Operator access is separately time-bound and audited.

## 3. Proposed relational entities and ownership

All multi-property tables carry \`organization_id\` and \`property_id\` where appropriate. Use a real relational database and migrations before production. \`ON DELETE\`, PII-retention, anonymization, backup and restore policy need legal and operator approval.

### Core identity and configuration
- \`organizations(id, legal_name, onboarding_status, created_at)\`
- \`properties(id, organization_id, slug, display_name, timezone, active, domain_verified_at)\`
- \`property_domains(domain, property_id, proof_ref, status)\`
- \`departments(id, property_id, type, hours_policy_id)\`
- \`staff_users(id, auth_subject_id, active)\`
- \`property_roles(property_id, user_id, role, dept_id, scope, valid_from, revoked_at)\`
- \`staff_shifts(property_id, dept_id, user_id, starts_at, ends_at, supervisor_id)\`
- \`approvals(property_id, actor, action_type, subject_ref, outcome, decided_at)\`

### Guest, cases and hotel operations
- \`guest_contacts(id, property_id, encrypted_contact_ref, consent_scope)\`
- \`guest_sessions(id, property_id, proof_hash, channel, verified_at, expires_at)\`
- \`guest_enquiries(id, property_id, request_key, customer_ref, category, details_ref, state, staff_owner, created_at)\`
- \`staff_cases(id, property_id, enquiry_id, department_id, status, assigned_staff_id, due_at)\`
- \`service_tickets(id, property_id, origin_case_id, category, priority, due_at, status, assignee, resolved_at)\`
- \`ticket_history(id, property_id, ticket_id, actor, event, evidence_ref, at)\`

### Source-qualified booking and financial states
- \`room_type_display(id, property_id, pms_type_ref, content_version)\`
- \`rate_quotes(id, property_id, provider_ref, stay_dates, occupancy, amount_minor, currency, taxes_minor, policy_version, expires_at)\`
- \`inventory_holds(id, property_id, quote_id, pms_hold_ref, expires_at, state)\`
- \`reservation_intents(id, property_id, request_key, guest_ref, quote_id, status)\`
- \`hotel_reservations(id, property_id, pms_booking_ref, verified_at, status)\`
- \`payment_intents(id, property_id, reservation_intent_id, provider_ref, amount_minor, currency, status)\`
- \`payment_transactions(provider_ref, property_id, amount_minor, currency, verified_at)\`
- \`finance_exceptions(id, property_id, kind, reference, owner_id, state, decision_audit_ref)\`

**Important:** uniqueness on \`(property_id, request_key)\` for business operations. PSP duplicate callbacks dedupe on \`(provider, account_id, provider_event_id)\`. Confirmed booking requires an actual PMS source ref and verified source state. Avoid treating a Paystack \`success\` redirect as payment proof.

### F&B, events and other departments
- \`restaurant_menus(property_id, version, approved_by, active_from)\`
- \`dining_orders(property_id, pos_ref, request_id, status, quoted_total_minor, currency)\`
- \`kitchen_acknowledgements(property_id, order_id, actor_or_pos_ref, status_at)\`
- \`delivery_jobs(property_id, order_id, courier_ref, state, proof_ref)\`
- \`event_leads(property_id, venue_id, event_date, size, status, assigned_sales)\`
- \`job_applications(property_id, vacancy_id, encrypted_cv_ref, applicant_consent, restricted_hr_role)\`
- \`supplier_requests(property_id, procurement_id, restricted_docs_ref, status, approver_id)\`

### Platform/AI/marketing/security
- \`approved_content(property_id, doc_id, version, access_class, approved_by, effective_at, withdrawn_at)\`
- \`agent_releases(id, model, prompt_version, tool_schema_version, kb_version, eval_ref, live_flag)\`
- \`prospect_accounts(canonical_org_id, business_identity, sales_stage, evidence_ref)\`
- \`channel_optins(property_id, person_ref, channel, purpose, opt_in_at, revoked_at, source)\`
- \`provider_integrations(property_id, provider, identity_ref, encrypted_secret_ref, enabled, scopes)\`
- \`inbox_events(id, provider, property_id, source_event_id, raw_hash, processed_at)\`
- \`audit_events(id, property_id, principal, action, resource, outcome, at)\`
- \`outbox_events(id, property_id, type, subject_ref, attempts, lease_until, status, last_error)\`
- \`usage_ledger(property_id, provider, usage_id, unit, amount_minor, currency, period)\`
- \`worthkind_invoices(org_id, subscription_ref, amount_minor, currency, status)\`
- \`incident_records(id, affected_properties, severity, state, owner, mitigation_ref)\`

## 4. API patterns and example endpoints

**These routes are proposed target contracts; don't claim they all exist.** Existing dev P0 endpoints remain isolated and require a versioned migration/refactor plan.

| Domain | Proposed route/command | Who may call it | What success means |
| --- | --- | --- | --- |
| Guest | \`POST /v1/properties/{slug}/enquiries\` | guest scoped to resolved hotel | enquiry persisted, not booked |
| Guest | \`GET /v1/properties/{slug}/enquiries/{id}\` | proof-bearing guest or hotel staff | status read with authorization |
| Onboarding | \`POST /v1/admin/properties\` | Worthkind authorized onboarding | pending entity, not active hotel |
| Content | \`POST /v1/hotel/content/{id}/approve\` | hotel content approver | approved version effective |
| Reservations | \`GET /v1/properties/{slug}/availability\` | guest or staff | PMS-sourced current inventory or explicit unavailable |
| Booking | \`POST /v1/properties/{slug}/reservation-intents\` | verified guest + accepted quote | intent, not PMS reservation |
| Payment | \`POST /v1/integrations/{psp}/webhook\` | signed PSP | event durably captured; not booking success |
| Hotel staff | \`POST /v1/staff/cases/{id}/claim\` | authorized hotel member | atomic staff ownership |
| Service desk | \`POST /v1/staff/tickets\` | authorized department staff | ticket created, not resolved |
| Dining | \`POST /v1/properties/{slug}/dining-orders\` | verified order request | order intent, not kitchen acceptance |
| HR | \`POST /v1/properties/{slug}/job-applications\` | consented applicant | application accepted, not job offer |
| Analytics | \`GET /v1/hotel/analytics/overview\` | authorized manager/finance scope | source-labelled metrics |
| Worthkind | \`GET /v1/platform/tenants/{id}/usage\` | scoped platform billing | Worthkind usage, not hotel GMV |
| Channels | \`POST /v1/integrations/{provider}/webhook\` | signed provider callback | event stored for processing |
| AI | \`POST /v1/assist/route\` | scoped guest/staff | suggestion/FAQ, never unaudited action |

### Standard command result

~~~json
{
  "request_id": "uuid",
  "property_id": "resolved-by-server",
  "resource_id": "uuid",
  "status": "queued",
  "source": "worthkind_case_db",
  "verified_business_outcome": false,
  "requires_human": true,
  "updated_at": "2026-11-17T12:00:00Z"
}
~~~

**Never** return \`status: confirmed\` if the authoritative provider has not confirmed. When an external API is offline, explain that the result is pending and preserve an accountable human case.

## 5. State machines and money accuracy

- **Enquiry:** \`queued → claimed → responded\`; reopen/escalate/decline require explicit extension and audit.
- **Ticket:** \`open → assigned → in_progress → resolved → reopened\` (development reference, future production can add triage/escalation/paused).
- **Reservation:** \`request → quote_verified → customer_approved → optional_hold → checkout_pending → payment_verified → pms_confirmed\`; independently track \`payment_verified_but_pms_unknown\`.
- **Dining:** \`requested → quoted → submitted_to_pos → accepted_or_rejected → preparing → ready → delivered_or_collected\`.
- **Outbound notification:** \`queued → provider_accepted → sent → delivered → read\` or \`failed/unknown\`. Provider accepted is **not** delivered.
- **Pilot hotel:** \`prospect → discovery → consented_waitlist → written_pilot_interest → legal_approval → configured → staged → active\`.
- **Marketing:** \`discovered\` and \`contacted\` are not \`opted_in\`; all reporting must use distinct evidence.

## 6. Event and failure contract

Proposed naming: \`guest.enquiry.created.v1\`, \`case.claimed.v1\`, \`ticket.resolved.v1\`, \`booking.quote.verified.v1\`, \`payment.provider_verified.v1\`, \`reservation.pms_confirmed.v1\`, \`notification.provider_accepted.v1\`, \`notification.delivered.v1\`, \`content.approved.v1\`, \`hotel.onboarded.v1\`, \`marketing.opt_out.v1\`.

Each event has \`event_id, organization_id, property_id, resource_id, event_version, occurred_at, correlation_id, source\`. Store only minimum PII needed; sensitive raw payloads are protected or referenced, not broadcast in events. Use an inbox for signed callbacks and an outbox for business-triggered side effects.

**Atomicity rule:** database business state, audit event, and pending outbox event commit together. A separate worker reliably delivers, with bounded retries, leases, idempotency strategy and dead-letter handling. This does not magically make external payment/PMS calls atomic. External side effects require compensating or reconciled state machines.

**Manual override rule:** authorized staff can assign/resolve with evidence, but cannot forge payment, confirmed PMS reservation or external delivery state.

## 7. Interface-to-domain control and safe AI tools

A website, WhatsApp chat, phone-call agent, staff UI or third-party integration is a **channel adapter**. They normalize consented inputs into domain commands. They do not persist arbitrary tenant data or bypass role checks directly.

Agents receive only approved tools such as \`get_public_hotel_policy(property_id, key)\`, \`create_enquiry(...)\`, \`request_staff_handoff(...)\`. Material writes must pass backend authorization and required confirmation. Agent context must be property-approved and scoped by purpose; never accept prompt-injected directions to access a different hotel's guest.

## 8. Accessibility, observability and testing contract

Every user surface must show: who the hotel is; whether an action is pending or completed; whether a real staff member has acknowledged; source/last updated when displaying volatile inventory; human bypass and contact details; appropriate privacy choices.

Tests required before production include: cross-tenant reads/writes, revoked staff, signed webhook forgery, duplicate payment callbacks, concurrency/oversell, human takeover, no-AI mode, stale inventory, delivery-state confusion, worker crash/replay, restore drill, cost caps, mobile/keyboard/screen-reader, finance metric reconciliation, safe termination/offboarding.

**No test is deemed passed by this design document.** Check the associated PR/CI evidence and obtain hotel-side pilot approval separately.
