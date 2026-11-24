# Worthkind Flow — First Engineering Code Review

**Review date:** 2026-11-16 (UTC)  
**Target:** [draft PR #2](https://github.com/NIDHOGGR-shadow/worthkind/pull/2), branch `feat/worthkind-flow-foundation`  
**Scope:** P0 reference guest enquiry → staff case → guest status, approved synthetic information lookup, audit/outbox, parent Worthkind site safety.

## Review verdict

- **Development/demo foundation:** conditionally acceptable; automated checks pass.
- **Real hotel or public production deployment:** **NOT APPROVED.** `WF_ENV=production` intentionally raises at import to block deployment.
- **Merge:** leave draft until owner and technical reviewer inspect changed files and sign off that the root Worthkind website remains unaffected.

### Verified evidence

- [GitHub Actions run 43968742587](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/43968742587): 21 API/integrity tests passed on Python 3.11 and 3.12, with three deprecation warnings; JavaScript syntax checks and root website tests/build green.
- The original Worthkind website, `package.json`, hackathon routes and Vercel configuration have not been changed by this PR. Only `projects/` and a dedicated CI workflow are added.
- Property-scoped receipt retrieval, cross-property denial, single idempotent case under concurrent duplicate requests, rejected changed-payload replay, rollback on audit failure, state transitions and no-LLM human intent bypass have automated checks.
- Outbox simulation tests crash rollback and repeat consumption, but **does not send messages**.

## Findings ordered by severity

| ID | Severity | Evidence / location | Required action |
| --- | --- | --- | --- |
| R01 | Blocker for production | `apps/api/main.py`: development keys, local SQLite and two synthetic hotels; production guard | Replace with managed PostgreSQL migrations, invited staff identity, tenant RBAC, secret storage and a real hotel onboarding workflow (#4, #6, #27). |
| R02 | Blocker for real reservations | `booking_capabilities` returns enquiry-only, no authorized PMS or payment provider | Obtain pilot hotel consent and actual booking provider API; test quotes/holds, signed payment verification and error reconciliation (#14–#17). |
| R03 | High | `outbox_worker.py` is **local simulation only**. There is no real message delivery, provider inbox, lease/retry scheduler or dead-letter queue | Implement production transactional outbox publishing, verified webhooks, idempotent consumer and backpressure/alerting (#7, #13, #16). Never treat pending event as delivered. |
| R04 | High | `main.py` human cases support queued → claimed → responded, with no timed escalation/reopen and only shared dev staff credential | Add real staff identities, acceptance SLAs, reassignment, reopening and delivery receipt to guest (#8, #12). |
| R05 | High | `public_facts` contains approved **synthetic fixture only**; no hotel-approved CMS or ingestion/revalidation | Build content approval/versioning, tenant retrieval and abstention fixture set; gather 100 legitimate pilot hotel questions (#9–#11). |
| R06 | High | API routes accept unauthenticated public enquiry submissions; rate limits and bot protections are absent | Add bounded distributed rate limiting, abuse limits, fraud/spam monitoring and privacy retention before exposing to public internet. |
| R07 | High | Real guest data retention, export/deletion, consent and access logging are unspecified; local SQLite stores contact details in plain form | Complete privacy/legal review, retention/deletion policy, purpose-based access, backups and encrypted production storage (#6, #27). |
| R08 | Medium | Web JS syntax and API tests passed, but no automated cross-browser/mobile accessibility or network-interruption UI E2E | Implement browser tests, manual keyboard/screen-reader/320px–desktop review, offline status and mobile responsiveness (#5). |
| R09 | Medium | Guest receipt is held in page memory and displayed; refresh loses status tracking unless copied | Plan secure recoverable guest session or explicitly verified contact-based access; never use email alone as identity proof. |
| R10 | Medium | `main.py` remains a single reference module and uses deprecated FastAPI startup event | Refactor domain/repository/auth/queue modules and lifespan after P0 contract stabilizes; test migrations and environment configuration. |
| R11 | Medium | ML not trained or active, no voice channel | Retain rules baseline; implement versioned fixed test gates before enabling LLM/ML/voice. Synthetic classifier was not release-ready (#10, #11, #24). |
| R12 | Medium | No live ad tracking, food dispatch, HR or supplier fulfillment | Keep those domains out of first deployment; define real external authority, permission, audit and success metric for each (#18–#27). |

## Strengths to keep

1. Direct and explicit human paths can bypass AI.
2. No live booking or payment success is falsely asserted.
3. Guest receipt access is scoped to property and requires possession of a strong secret.
4. Idempotency and audit/outbox writes are transactional in the SQLite reference.
5. Model inference is optional and absent by default; unsupported information is not invented.
6. Parent Worthkind website gets its own CI regression job.
7. Work lives under `projects/worthkind-flow/` and can be reviewed or reverted independently.

## Next code review sequence

1. **Founder/product owner:** validate one willing hotel's booking provider, receptionist escalation, staffing availability, consent and documented policies ([#3](https://github.com/NIDHOGGR-shadow/worthkind/issues/3)).
2. **Technical lead/backend:** choose PostgreSQL/RLS migration model; implement production auth + real outbox (#4, #6, #7, #8).
3. **AI/ML + hotel content:** create approved documents, controlled retrieval, fixed eval set and abstention tests (#9, #10, #11).
4. **QA/security:** negative tenant/replay/abuse tests, signed provider callbacks after integration, browser accessibility and incident drills.
5. **Hotel manager:** accept documented SLAs and establish a staffed response route before any guest traffic.
6. Review PR #2 and its green CI, retain draft or merge only after reviewing its scope and release non-goals. Production remains a separate gate.

**Confidence boundaries:** Passed unit and reference integration tests are evidence for the specified development contracts, not for actual production integrations or operational readiness.
