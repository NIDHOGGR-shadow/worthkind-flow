# Frontend deployment and Q2 acceptance

The new gateway serves the v1 guest and staff interfaces on one origin and forwards only explicitly listed Q1–Q3 API methods to the separately deployed staging API. Legacy SQLite pages, dev staff keys, tests, arbitrary files and other API endpoints are not exposed. This does not modify the staging guard in backend PR #3.

## Runtime
Build from repository root with Dockerfile.frontend. Run the resulting nonroot container behind managed HTTPS ingress. Configure:
- WF_FRONTEND_API_ORIGIN: the authorized HTTPS backend origin only, without a path, user information or query.
- WF_FRONTEND_AUTH_ENABLED: leave 0 until backend identity configuration and approved staff identities are ready.
- WF_SUPABASE_URL: approved project URL matching the backend.
- WF_SUPABASE_PUBLISHABLE_KEY: modern publishable key, never an admin or service-role key.
- PORT: default 8080.

Do not put database passwords, encryption keys, private identity credentials or server-only secrets in the frontend environment. The browser receives only the public identity configuration. Do not use a shared project's unrelated accounts for Flow. No credentials or real records are needed by frontend CI.

Routes: / guest, /staff staff, /health frontend process health only. The health response does not verify the upstream, identity or PostgreSQL. The gateway's versioned route allowlist now includes exact Q3 catalog, reservation-request, staff PMS read, dining, venue and finance operations. Paystack webhooks stay on the authorized backend ingress, not the browser gateway. Q4 and arbitrary endpoints remain excluded.

## Acceptance
1. Verify the backend deployment /ready independently, including restricted runtime credentials and TLS.
2. Verify the frontend is served over HTTPS. Confirm browser requests go to the same frontend origin, with a fixed upstream origin selected by deployment configuration.
3. Validate rate limiting behind the real proxy topology with the backend owner; the gateway does not trust client-supplied forwarded identity/IP headers.
4. With an explicitly authorized synthetic staff identity and isolated hotel, sign in, read own property, verify denial at a different property, claim/respond, create and advance a ticket, load its history, schedule/cancel a shift, change room condition, then sign out. Clean up synthetic records through approved procedures.
5. Verify role restrictions on server and the absence of private data after context changes, token expiration and logout. Test recovery and MFA with the chosen provider before real staff onboarding. Review ingress policy, runtime logging, TLS, security headers and visual screens before launch.

Do not activate live identities, payment providers, or real guest data from this document. The selected backend has been implemented and tested in its own workstream, but the hosted runtime was not verified from this frontend branch. Dedicated shift handover and guest-confirmed case resolution are still missing backend contracts; ticket history, staff resolution, and feedback are not substitutes.

## Q3 acceptance additions
Test reservation intent retry and withdrawal, staff review, published room and menu catalog, provider read-only availability, dining order and invoice, test-mode Paystack initialization and verification, refund approval separation, venue decisions, and cross-property denial. Do not use live money or real guests until approved provider activation and property acceptance. Read-only PMS state does not authorize creating or modifying a booking; reservation requests do not hold rooms. Configure backend rate limits and payment webhook ingress independently.
