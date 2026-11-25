# Worthkind Flow operational agent rules

Policy version 2026-11-25.1. Worthkind Flow is the shared hospitality platform; Hotel OS is separate. This is an initial bounded implementation, not a release.

## Product-wide rules

1. Guests may browse, use direct forms, call/message reception or choose AI. Never make AI a gatekeeper. Report an issue directly to reception; staff own departmental escalation and manager visibility.
2. Resolve the property from trusted server context before accessing information or tools. Never trust model-selected tenant identifiers or expose guest records, credentials, payment information or internal staff information.
3. Emergency and human requests bypass AI. Provide a direct human route; never claim a call was connected or help dispatched without receipt.
4. The model proposes an intent or approved knowledge key. Independent server policy validates outputs and never executes a model-proposed tool. Only return current approved property facts. Missing information, malformed output, outage or disabled provider leads to direct reception.
5. Reservation, cancellation, payment, refund, room service, dining, events, supplier and careers workflows require the corresponding authoritative service, authorization and confirmed outcome. No invented availability, staff acceptance, dispatch, booking, payment or job offer. Explicit user confirmation for consequential actions; idempotency and audit/outbox for state changes.
6. AI Studio release requires versioned hotel knowledge, role-based tool scopes, approval limits, escalation schedules, hostile-scenario testing, independent reviewer, rollback and emergency kill switch. A model must not control its own permissions. Owner and platform authority remain separate.
7. Phone calls must resolve the property from the inbound number, disclose AI and recording where appropriate, allow instant human transfer, and have a callback path when staff are unavailable. WhatsApp and web must share equivalent policy, not force callers to repeat information unnecessarily. Live telephony, voice recognition and messaging integrations remain unimplemented.
8. Never put secrets in Git or browser bundles. No unapproved guest data to model providers. No live public AI until tenant limits, consent/privacy controls, individual staff auth, monitoring, tenant isolation and incident controls are tested.
9. Engineering: preserve existing behavior, inspect before changes, test/fix/retest, report actual evidence, use real integrations with authorized test credentials, never label simulated dependencies live. Do not claim production readiness before release gates pass.

## Current first implementation

- POST /api/properties/{slug}/assistant: public deterministic assistant and direct reception routing. Does not create a case or send messages; use the existing enquiry endpoint for that explicit action.
- POST /api/properties/{slug}/staff/assistant/evaluate: protected by existing development property key; optional external NVIDIA classification only for unresolved public-information text with explicit provider_consent=true. Use synthetic/public test questions only; basic regex privacy screening is not a sufficient DLP guarantee.
- NVIDIA uses the fixed hosted chat-completions endpoint and server-side environment variables: WF_NVIDIA_ENABLED=1, NVIDIA_API_KEY, WF_NVIDIA_MODEL (the exact model ID available to your account). Default disabled; no credentials committed. Replace the Classifier implementation to switch model/provider. No external tools are exposed.
- Public paid inference intentionally disabled. Staff evaluate uses the existing development authentication; do not expose this environment to actual hotel traffic or enable with real guest conversations until secure identity, quotas and privacy safeguards exist. Live provider calls are not verified.
- Test: from repository root run PYTHONPATH=apps/api python -m unittest discover -s apps/api/tests -p test_agent_policy.py. Tests use injected provider responses only and are not proof of NVIDIA connectivity.
- Production remains blocked by existing startup guard. PostgreSQL/Supabase, RLS, real identity, notifications, telephony, authoritative PMS/POS/payment integration, versioned release control and end-to-end UI must be completed before launch.
