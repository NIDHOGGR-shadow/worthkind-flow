# PostgreSQL M1-A tenancy foundation (experimental integration branch)

**Safety:** Migration `migrations/001_tenant_staff_foundation.sql` is for an isolated PostgreSQL 16+ database under reviewed credentials. It is **NOT** applied to production, the existing Worthkind website, or the FastAPI development SQLite database. Never execute it against an existing customer database without an authorized migration rehearsal and rollback plan.

## What actually exists
- An organization → property relationship with unique property slugs and organization-bound foreign keys.
- External-provider identity **references only** (no passwords), property-specific role/membership status and timestamps.
- Minimal guest case metadata with property-scoped request keys and an assignment foreign key that rejects cross-hotel assignment.
- Audit and outbox schema placeholders, distinct from delivery confirmations.
- Row Level Security enabled and forced on all seven tables, with a dedicated no-login `wf_staff_runtime` read-only role and policies that restrict active, permitted staff to their own hotels' case metadata.
- Default-deny for unauthenticated context, invited, revoked and suspended members. Housekeeping cannot read guest case metadata through the reception policy.
- Isolated real PostgreSQL integration tests executed by GitHub Actions with an ephemeral test database.

## Authentication trust boundary — critical
The SQL session attribute `wf.actor_id` is **not an authentication method**. PostgreSQL custom session settings can be set by a SQL-capable client. The server must independently verify the staff's identity token, map its stable provider subject to a staff identity, establish a trusted transaction-local actor context, and **never expose the database connection or arbitrary SQL to browsers/clients**. Read-only RLS limits accidental query errors; it does not replace safe API authorization or protect a compromised DB credential.

No API endpoints use this schema yet. There is no invite email, sign-in UI, staff password workflow, JWT issuer validation, session expiration, guest-data encryption, production migration management, database backup or real notification worker. The current `WF_ENV=production` failure remains in force.

## Test locally (isolated, disposable database only)
Create an empty Postgres instance with an administrator able to create roles, then run:

```bash
python -m pip install -r apps/api/requirements-pg-test.txt
export WF_TEST_POSTGRES_DSN="postgresql://postgres:LOCAL_TEST_ONLY@127.0.0.1:5432/worthkind_ci"
python -m pytest apps/api/tests_pg -q
```

The test fixture deliberately refuses DSNs not containing localhost/127.0.0.1, creates the schema/role and truncates its namespaced tables before each test. **Never reuse a real database name or test role password.** The CI job uses a short-lived service container.

## Integration sequence
1. Verify migration + permission/foreign-key negatives on PostgreSQL in CI.
2. Decide actual identity issuer and verify JWT (issuer/audience/signature) at the FastAPI boundary. Do not allow arbitrary user-provided actor IDs to become SQL context.
3. Implement transactional repository operations with a separate narrowly privileged application service role (no DB superuser). Create a case + audit + outbox atomically and claim/respond using conditional updates, with actual staff membership recheck and concurrency tests.
4. Adapt the existing guest receipt and staff UI to the new backend without removing old verified functionality; retain `no-store`, idempotency and no-AI fallback.
5. Run full two-property browser/API integration, security review, backup/restore and zero-real-PII pilot gate before any release.

## Operational ownership and pending decisions
- Preferred managed PostgreSQL vendor and identity issuer need explicit owner signoff before provisioning. Existing code and CI make no external account changes.
- Any migration rollback must be reviewed separately; this branch provides **no destructive downgrade script**.
- Schema may evolve under new numbered migrations after reviewed changes. Never alter an already-applied migration in production.

## Second migration: atomic case commands (002)
The second migration creates two distinct no-login SQL roles: a guest API command role and a staff command role. They receive EXECUTE on reviewed, schema-qualified, security-definer functions, but no direct table reads/writes.

- `create_guest_case`: requires an active hotel in a verified organization; property-scoped request key and identical request/receipt fingerprints on retries; inserts case + audit + pending outbox atomically on first creation.
- `claim_guest_case`: requires the trusted API to map a verified employee identity to the transaction-local actor ID; checks active property, staff identity, membership and reception/manager/owner role; changes only queued cases and records audit/outbox.
- `record_case_reply`: only the exact claiming employee may update their case; takes an opaque encrypted byte payload and fingerprint, not plaintext; records an event as pending. **PostgreSQL cannot validate that supplied bytes were actually encrypted.** Implement API-side authenticated encryption and key lifecycle before storing real reply content.

**Risk:** The functions run with a privileged migration owner and rely on a trusted API connection. The current CI uses an ephemeral admin PostgreSQL account to validate function semantics. A production migration plan must give these functions a dedicated, tightly restricted owner that can perform required writes without unnecessary privileges, and it must validate the verified identity token at the service boundary. Never give these role credentials or arbitrary SQL access to a browser. No external notification or real guest reply is sent.

**CI tests:** real PostgreSQL idempotent create, wrong-hotel and role denial, single-winner concurrent claim, ownership/revocation enforcement, forced event-write failure rollback, and no false delivered status. These tests demonstrate SQL behavior only; a connected FastAPI→Postgres→UI path is the next integration task.

## Third migration and FastAPI integration: verified staff identity (003)
The provider-neutral OIDC bridge does not invent a provider account. The API must be configured **server-side** with:
- `WF_OIDC_ISSUER`: exactly trusted token issuer.
- `WF_OIDC_AUDIENCE`: this Worthkind Flow API audience.
- `WF_OIDC_JWKS_JSON`: currently trusted RSA public JWK keys with explicit stable KIDs. Only RS256 is accepted. Never put private keys in this JSON.
- `WF_STAFF_POSTGRES_DSN`: server-only staff login with the narrowly granted `wf_auth_lookup`, `wf_staff_runtime`, and `wf_staff_commands` roles; never use a superuser in production.

`staff_oidc.py` verifies token signature, algorithm, key ID, issuer, audience, expiration and stable subject; no JWT property/role claim can grant access. Then PostgreSQL `resolve_staff_session` checks active organization, property, identity, membership and role. Transaction-local actor context is derived **only** from this database lookup.

New **development-only integrated routes** (require configured identity and DB, otherwise fail closed): 
- `GET /api/v1/properties/{slug}/staff/cases` — filtered safe case metadata only, no customer contact or free text.
- `POST /api/v1/properties/{slug}/staff/cases/{uuid}/claim` — one atomic PostgreSQL claim plus audited pending event. Repeated/foreign claims rejected. No real delivery is claimed.

These endpoints use actual PostgreSQL commands with locally generated signed test JWTs in CI. They do **not** replace the existing synthetic SQLite `/staff` UI workflow, automatically create hotel employees, encrypt existing guest details, verify a real identity provider, or enable production startup.

**Go-live blockers:** select the real hotel's identity issuer/owner, prove JWKS rotation and claim policies, provide a restricted DB login not owned by migration superuser, harden function ownership and connection pooling, implement API-side envelope encryption and retention, and run browser plus production-like negative-security tests. Production migration/role grants require explicit authorization.

## Fourth migration: encrypted synthetic guest-to-staff loop (004)
Adds an encrypted guest payload column, a role-gated atomic submit function and a private receipt-only lookup. The normal development SQLite routes remain available; these are **separate v1 FastAPI PostgreSQL routes**.

**Development-only environment flags (no real credentials in repository):**
- `WF_ENABLE_PG_GUEST_API=1` to explicitly activate the synthetic PostgreSQL guest path.
- `WF_DATA_KEY_B64` holding a randomly generated 32-byte key encoded as standard Base64, server-only; CI generates it dynamically. Never use the literal examples as real keys.
- `WF_GUEST_POSTGRES_DSN` private guest PostgreSQL login permitted to use only `wf_guest_api`; staff uses its separate `WF_STAFF_POSTGRES_DSN`.
- For staff endpoints, separately verified OIDC issuer/audience/JWKS configuration as above.

**API workflow:** Guest requests `POST /api/v1/properties/{slug}/enquiries` with a unique request key, input fields and 32+ character client-generated receipt secret; API encrypts guest details with AES-256-GCM and property/request AAD, commits case+audit+pending outbox via database function, returns the private receipt. Same request key and exact receipt/data retry returns same case; changed data returns conflict. Staff read via signed JWT decrypts only their authorized hotel's guest content; claim and recorded reply are database-atomic. Guest reads `GET /api/v1/properties/{slug}/enquiries/{case_id}` only with the original `X-Receipt-Token` header and receives the recorded reply after staff writes it. A reply is **not** a real sent email/SMS/WhatsApp notification.

**Security limitations:** App-wide secret is not yet per-property envelope encryption. Production must use managed KMS/rotation, backup/retention/deletion, DPA and data residency agreements, consent forms, phishing/leak-safe receipt storage, anti-spam/IP rate limits, genuine hotel staff identities and a verified notification delivery provider. The actual public website is not yet connected to v1 and no real hotel traffic has been authorized. `WF_ENV=production` continues to block startup.

## Separate guest and staff SQL credentials (next hardening batch)
The v1 API now deliberately requires different server-only settings:
- `WF_GUEST_POSTGRES_DSN`: login permitted to **SET ROLE wf_guest_api** only, with no staff or raw-table permissions.
- `WF_STAFF_POSTGRES_DSN`: distinct login permitted to **SET ROLE wf_auth_lookup, wf_staff_runtime and wf_staff_commands**, with no guest API role.
The earlier shared `WF_POSTGRES_DSN` is **not** used by these v1 functions. CI creates two disposable NOINHERIT logins with test-only credentials, verifies both API paths and denies cross-role commands. No actual managed DB roles have been provisioned.

**Security caveat:** This limits accidental permission blast radius but does not protect an attacker who obtains a database password and issues arbitrary SQL under its authorized roles. Production must ensure only the backend can reach PostgreSQL, use TLS and credential rotation, add narrowly scoped function ownership, monitor queries, and never expose unrestricted SQL or private DSNs to the browser. Schema changes are still draft, not authorized for a real database.


## Standalone Flow continuation (25 November 2026)
- Migration 005 denies runtime case reads when a property or organization is inactive.
- Migration 006 and /api/v1/properties/{slug}/staff/memberships/{invite,accept,revoke} manage existing identity-provider subjects, audited atomically. The private WF_STAFF_LIFECYCLE_POSTGRES_DSN login may SET ROLE wf_staff_lifecycle only. Owner bootstrapping, identity-provider account creation and sending invite emails remain separate. A revoked membership cannot be silently reactivated.
- Migration 007 and apps/api/event_projector.py build a durable internal case activity ledger. Configure a distinct private WF_EVENT_PROJECTOR_POSTGRES_DSN login with only wf_event_projector role access. Run from apps/api with python event_projector.py, or add --once for a single bounded batch. Concurrent workers use SKIP LOCKED and atomic projection; failed transactions leave work pending. This is not a notification worker and does not update external delivery state.
- CI run 45687757148 passed the PostgreSQL integration and SQLite runtime jobs at commit 86ba045f18e20f77cc15f2398fa7d314de92bf65 (before migrations 006 and 007). New changes need their own passing CI evidence.
- No dedicated hosted Flow database has been identified; do not point the Flow credentials at the landlord, Hotel OS or Student Creators database. Production startup remains blocked. Private role credentials, function ownership hardening, TLS, secrets/key management, hosted verification and full migration are still outstanding.


## Hosted Supabase staging foundation (25 November 2026)

Owner authorized selecting an existing project. Selected Primary account project ref `xfxqlcmsfkbvbybkrppq` (eu-west-1). It already hosts seven unrelated public tables, and initially had no Auth users, storage buckets or Flow schema/roles. Keep all Flow tables in the private `worthkind_flow` schema; do not expose it in the Data API, reuse a project service key as a database login, or change unrelated public objects. Shared compute, backup and Auth boundaries mean a separate dedicated production project remains preferable.

Migrations 001–011 applied successfully through Supabase. Hosted checks: 14/14 tables have forced RLS; anon, authenticated and service_role have no schema usage or function execution privileges. A rolled-back synthetic smoke test registered a hotel, activated an owner, resolved membership, consumed a quota, created a case and projected an internal event without marking external delivery. Follow-up counts for organizations, properties, staff identities and guest cases were all zero. Security advisor reports intentional deny-by-default private tables without public policies; unrelated public RPC warnings were not modified.

### Server connection configuration

- WF_IDENTITY_PROVIDER=supabase
- WF_SUPABASE_URL=https://xfxqlcmsfkbvbybkrppq.supabase.co
- WF_SUPABASE_PUBLISHABLE_KEY: project publishable (or legacy anon) key.
- WF_ENABLE_PG_GUEST_API=1 for the versioned guest route.
- WF_DATA_KEY_B64 and WF_GUEST_QUOTA_SECRET: distinct random server secrets, never commit them.
- WF_GUEST_POSTGRES_DSN: restricted login permitted SET ROLE wf_guest_api.
- WF_STAFF_POSTGRES_DSN: restricted login permitted SET ROLE wf_auth_lookup, wf_staff_runtime, wf_staff_commands.
- WF_STAFF_LIFECYCLE_POSTGRES_DSN: restricted login permitted SET ROLE wf_staff_lifecycle.
- WF_EVENT_PROJECTOR_POSTGRES_DSN: restricted login permitted SET ROLE wf_event_projector.
- WF_HOTEL_PROVISIONER_POSTGRES_DSN: operator-only login permitted SET ROLE wf_hotel_provisioner.
- WF_PROPERTY_CONFIG_POSTGRES_DSN: restricted login permitted SET ROLE wf_property_config.
- WF_GUEST_QUOTA_POSTGRES_DSN: restricted login permitted SET ROLE wf_guest_quota.
- WF_DOCUMENT_POSTGRES_DSN: restricted login permitted SET ROLE wf_document_store.

Use private TLS PostgreSQL connections, with certificate verification, separate restricted login roles, and secrets stored in the deployment environment. No application login credentials were provisioned in this session. Use the verified Auth UUID as the provider subject when registering or activating a staff member. Supabase Auth adapter calls the project's Auth server rather than trusting user metadata; local test coverage uses a simulated HTTP transport, not a real sign-in.

The new database recovery workflow applies every migration in a disposable PostgreSQL 17 service, creates synthetic evidence, dumps the Flow schema and restores into another disposable database, then verifies recovered data and RLS. It does not back up the real hosted database or prove a cross-project disaster recovery capability. The production startup guard is unchanged. SQLite routes, full data migration, restricted login provisioning, live Auth verification, key rotation, public media storage, production infrastructure, and independent backup/restore still require work.
