# Release integration candidate

Combined source heads: backend PR #3 ff6467b6d7bdd4d7049a93f584a510bec9783973; frontend PR #2 6c91e2a539fd9fac2e98bb1892a9a60f4bdd7a6f. Their 49 frontend changed paths do not overlap the backend changed files. The integration branch preserves both parents, extends the exact gateway route allowlist for the new guest, staff and CRM endpoints, and adds real loopback gateway/API/PostgreSQL HTTP acceptance. No merge to main or production deployment.

The existing browser suite also runs on this candidate. New gateway routes do not by themselves mean all new user-facing UI has been implemented. Do not expose arbitrary platform, administrative or webhook paths. The older AI PR #1 is not merged wholesale; its deterministic handoff behavior was ported into PR #3.

Hosted acceptance remains separate: provide an authorized HTTPS API origin and dedicated staging runtime (backend and frontend), restricted TLS-verified PostgreSQL logins, Supabase publishable identity setup and authorized synthetic staff accounts. Verify /ready and actual HTTPS gateway journeys. For email, approve property sender, set scoped Resend send/read credentials in worker secret environment, enable worker explicitly, and test on an owned address with consent. For CRM, provision only a separate restricted wf_platform_crm login and explicitly approved operator; do not grant admin role to runtime. Keep Modal, PMS writes and live payments off until independent provider acceptance. No real guests or money in CI.

The new HTTP test uses real Node gateway, Uvicorn and PostgreSQL on loopback with signed disposable CI identities. Provider outcomes remain fixture-tested only; no external provider contact. It is not evidence of live HTTPS, Supabase Auth sessions, actual notification delivery or final release signoff.

## Verified integration CI — 2026-11-26

Functional commit `a801cc9ce80a0e7e494df34c19b00d99d2f5c9bb`: all three workflows succeeded. [Backend boundary and real HTTP/PostgreSQL journey](https://github.com/NIDHOGGR-shadow/worthkind-flow/actions/runs/45866799846), [frontend JavaScript contracts and actual browser journey/viewport checks](https://github.com/NIDHOGGR-shadow/worthkind-flow/actions/runs/45866800111), [database recovery rehearsal](https://github.com/NIDHOGGR-shadow/worthkind-flow/actions/runs/45866799720). These are CI checks against disposable data, not hosted acceptance. Staging database migrations 052–056 were applied separately; no live provider delivery or production release was performed.
