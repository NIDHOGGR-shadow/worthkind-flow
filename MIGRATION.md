# Migration register

Imported 2026-11-24 from [Worthkind](https://github.com/NIDHOGGR-shadow/worthkind). The original private repository and branches are unchanged. This is a file-level migration, not a transfer of Git history or proof of deployment.

## Canonical baseline

Source commit: [b119e4f3ca6610a6c51493cfc7630eef64d724cc](https://github.com/NIDHOGGR-shadow/worthkind/commit/b119e4f3ca6610a6c51493cfc7630eef64d724cc), source folder `projects/worthkind-flow/`. All 104 source files were verified by matching Git blob SHA before additional materials were imported. The main code is the local-development baseline, not a production release. Alternate implementations are kept under `archive/`; do not add them to the runtime or test discovery without reconciliation.

## Additional material

- `archive/postgres-role-separation/`: draft PostgreSQL/RLS/OIDC artifacts from 1cd1f9c; not deployed.
- `archive/sqlite-storage-boundary/`: alternative SQLite/dashboard/knowledge modules from c16f0a5.
- `archive/provider-contracts/`: draft adapter contracts from 9565d95.
- `archive/local-overview/`: prior overview tests and documentation from 8e32366.
- `docs/whatsapp/`: design and diagrams from d02acfaa.
- `apps/waitlist/`, `planning/acquisition/`: isolated waitlist application and research from 1c3364c; prospect research is not evidence of contact or opt-in.
- `planning/NON_AI_BUILD_PLAN.md`: original non-AI plan from b09a9e2.
- `archive/original-ci.yml`: historical scoped CI configuration, not an active workflow; adapt paths before enabling.

## Original development branch register (29)

Full original Git history remains at the linked commits. Not all divergent versions of same-path files were copied; use these refs for comparison and recovery.

| Branch | Source commit |
|---|---|
| feat/worthkind-flow-browser-e2e-2026-11-19 | [14bbfc2c56b1](https://github.com/NIDHOGGR-shadow/worthkind/commit/14bbfc2c56b14cfdbb6e31a7dcdab2db4ac2ddd0) |
| feat/worthkind-flow-case-ticket-handoff-2026-11-19 | [1dcc55579af2](https://github.com/NIDHOGGR-shadow/worthkind/commit/1dcc55579af25118f5350624a8600571b401aff5) |
| feat/worthkind-flow-db-role-separation-2026-11-19 | [1cd1f9c0485e](https://github.com/NIDHOGGR-shadow/worthkind/commit/1cd1f9c0485e0ed1cf8f8ee15be5b424cc59db16) |
| feat/worthkind-flow-encrypted-guest-loop-2026-11-19 | [f3a62ec4930c](https://github.com/NIDHOGGR-shadow/worthkind/commit/f3a62ec4930c8305d840ad1769becd50cf46dcca) |
| feat/worthkind-flow-engineering-recovery-2026-11-19 | [21593e9a2cc4](https://github.com/NIDHOGGR-shadow/worthkind/commit/21593e9a2cc452a2b2d19c1eb2b303680ff9c0b4) |
| feat/worthkind-flow-fake-delivery-contract-2026-11-20 | [2a18e43b01cf](https://github.com/NIDHOGGR-shadow/worthkind/commit/2a18e43b01cfd99cb9d494266f0556dfb0e7c97e) |
| feat/worthkind-flow-foundation | [3f0a58ccf90c](https://github.com/NIDHOGGR-shadow/worthkind/commit/3f0a58ccf90c1ebc0b7cdae1031cb5916ccfe11a) |
| feat/worthkind-flow-local-first-scenarios-2026-11-19 | [b78fb9c363b5](https://github.com/NIDHOGGR-shadow/worthkind/commit/b78fb9c363b58714685c45cb8cdceb505551e507) |
| feat/worthkind-flow-local-knowledge-approval-2026-11-19 | [50f619e6b204](https://github.com/NIDHOGGR-shadow/worthkind/commit/50f619e6b20418607c720c3f29a4c75eb5cfc34e) |
| feat/worthkind-flow-local-operations-dashboard-2026-11-19 | [e11a62f42e9b](https://github.com/NIDHOGGR-shadow/worthkind/commit/e11a62f42e9bab8d3682f10b7349927ca6ba3794) |
| feat/worthkind-flow-local-operations-overview-2026-11-19 | [e0801bad3004](https://github.com/NIDHOGGR-shadow/worthkind/commit/e0801bad300489980c160aed828a0ce1ea83399d) |
| feat/worthkind-flow-local-scenario-fixtures-2026-11-19 | [8e32366a25f3](https://github.com/NIDHOGGR-shadow/worthkind/commit/8e32366a25f3212a11d7bce915cf7ba8b50dfafd) |
| feat/worthkind-flow-local-sla-queue-2026-11-20 | [b259a857eef7](https://github.com/NIDHOGGR-shadow/worthkind/commit/b259a857eef7d38cdc9b711ec2ecfbc4f5ef6db1) |
| feat/worthkind-flow-local-ticket-integration-2026-11-19 | [46ad7cc6b624](https://github.com/NIDHOGGR-shadow/worthkind/commit/46ad7cc6b6246223fbd454fb0536a23aa51042a5) |
| feat/worthkind-flow-master-platform-architecture | [95053037e4cd](https://github.com/NIDHOGGR-shadow/worthkind/commit/95053037e4cddbe9ca63b81e9490a3eb126fadc4) |
| feat/worthkind-flow-oidc-staff-api-2026-11-19 | [fe3159636402](https://github.com/NIDHOGGR-shadow/worthkind/commit/fe3159636402280796cea0540c985f2d97bf6c12) |
| feat/worthkind-flow-postgres-case-engine-2026-11-19 | [4a0b9cc7d5a9](https://github.com/NIDHOGGR-shadow/worthkind/commit/4a0b9cc7d5a9096ce3cd3043945312a2e1011efd) |
| feat/worthkind-flow-postgres-tenancy-2026-11-19 | [4b6130d9d636](https://github.com/NIDHOGGR-shadow/worthkind/commit/4b6130d9d6369ade95bd9ad48febca22836833e9) |
| feat/worthkind-flow-provider-contracts-2026-11-20 | [9565d9578dcb](https://github.com/NIDHOGGR-shadow/worthkind/commit/9565d9578dcbe33330d0d071c595e944e90bafb8) |
| feat/worthkind-flow-receipt-recovery-2026-11-19 | [7065fec48dcc](https://github.com/NIDHOGGR-shadow/worthkind/commit/7065fec48dcc1e268b0ac4b9e36be1fa3508b5c2) |
| feat/worthkind-flow-reuse-and-dashboard-preview | [47bf986bbe87](https://github.com/NIDHOGGR-shadow/worthkind/commit/47bf986bbe87e542bb90bfa89cb45d3501bbf10a) |
| feat/worthkind-flow-service-tickets | [b09a9e2bcf58](https://github.com/NIDHOGGR-shadow/worthkind/commit/b09a9e2bcf58b95ebed386c4d3f7f6c493c5f6f9) |
| feat/worthkind-flow-sqlite-knowledge-approval-2026-11-19 | [98cdeaafeb81](https://github.com/NIDHOGGR-shadow/worthkind/commit/98cdeaafeb81056db0cf9eae27374fff198b8952) |
| feat/worthkind-flow-sqlite-owner-dashboard-2026-11-19 | [6ed206043b70](https://github.com/NIDHOGGR-shadow/worthkind/commit/6ed206043b7022ae5cd1fa28ac4782cd4d9b405e) |
| feat/worthkind-flow-sqlite-storage-boundary-2026-11-19 | [c16f0a59518f](https://github.com/NIDHOGGR-shadow/worthkind/commit/c16f0a59518f6abc44b6f879b6ef285dbd4c6d02) |
| feat/worthkind-flow-staff-workspace-2026-11-19 | [7207afaf2b94](https://github.com/NIDHOGGR-shadow/worthkind/commit/7207afaf2b943d692e9ac601bd4d2e3c7a910a82) |
| feat/worthkind-flow-waitlist-pilot | [1c3364c410c7](https://github.com/NIDHOGGR-shadow/worthkind/commit/1c3364c410c709f273e16a95225a6655a8bb1a3d) |
| feat/worthkind-flow-whatsapp-architecture | [d02acfaa0fca](https://github.com/NIDHOGGR-shadow/worthkind/commit/d02acfaa0fca34f444f87b0702147d38630b2c5e) |
| fix/worthkind-flow-fake-provider-guard-20261122 | [b119e4f3ca66](https://github.com/NIDHOGGR-shadow/worthkind/commit/b119e4f3ca6610a6c51493cfc7630eef64d724cc) |

## Original issue index (29 matching titles)

These are historical pointers, not recreated issues. Access to the original private repo is required. Status reflects the source at import.

- [#68](https://github.com/NIDHOGGR-shadow/worthkind/issues/68) — WF-CI-01: GitHub Actions jobs fail without recorded steps; browser E2E verification blocked (open)
- [#32](https://github.com/NIDHOGGR-shadow/worthkind/issues/32) — [Worthkind Flow P1 · OPS-01] Production IT and hotel service ticket desk after reference PR #31 (open)
- [#30](https://github.com/NIDHOGGR-shadow/worthkind/issues/30) — [Worthkind Flow WA-SEC] Production readiness for hotel early-access consent and CRM (open)
- [#28](https://github.com/NIDHOGGR-shadow/worthkind/issues/28) — [Worthkind Flow GTM · WAITLIST-01] Secure 20 qualified hotel waitlist opt-ins and 3 pilot partners (open)
- [#27](https://github.com/NIDHOGGR-shadow/worthkind/issues/27) — [Worthkind Flow P5 · D20] Prepare secure multi-property production rollout (open)
- [#26](https://github.com/NIDHOGGR-shadow/worthkind/issues/26) — [Worthkind Flow P5 · D19] Measure per-hotel usage, bookings, cost and unit economics (open)
- [#25](https://github.com/NIDHOGGR-shadow/worthkind/issues/25) — [Worthkind Flow P5 · D18] Add official WhatsApp conversational and outbound channels (open)
- [#24](https://github.com/NIDHOGGR-shadow/worthkind/issues/24) — [Worthkind Flow P5 · D17] Integrate optional voice channel with human fallback (open)
- [#23](https://github.com/NIDHOGGR-shadow/worthkind/issues/23) — [Worthkind Flow P4 · D16] Implement compliant post-stay follow-up and reviews (open)
- [#22](https://github.com/NIDHOGGR-shadow/worthkind/issues/22) — [Worthkind Flow P4 · D15] Create supplier, partnership and event enquiry workflows (open)
- [#21](https://github.com/NIDHOGGR-shadow/worthkind/issues/21) — [Worthkind Flow P4 · D14] Create restricted careers and internships intake (open)
- [#20](https://github.com/NIDHOGGR-shadow/worthkind/issues/20) — [Worthkind Flow P3 · D13] Implement delivery coverage and courier reconciliation (open)
- [#19](https://github.com/NIDHOGGR-shadow/worthkind/issues/19) — [Worthkind Flow P3 · D12] Connect hotel restaurant catalog, POS and kitchen acceptance (open)
- [#18](https://github.com/NIDHOGGR-shadow/worthkind/issues/18) — [Worthkind Flow P3 · D11] Implement stay service tickets and department handoff (open)
- [#17](https://github.com/NIDHOGGR-shadow/worthkind/issues/17) — [Worthkind Flow P2 · D10] Build live reservation front-desk verification dashboard (open)
- [#16](https://github.com/NIDHOGGR-shadow/worthkind/issues/16) — [Worthkind Flow P2 · V5-05] Implement signed provider webhook ingress (open)
- [#15](https://github.com/NIDHOGGR-shadow/worthkind/issues/15) — [Worthkind Flow P2 · D09] Integrate payment verification and reconciliation (open)
- [#14](https://github.com/NIDHOGGR-shadow/worthkind/issues/14) — [Worthkind Flow P2 · D08] Develop authorized room/PMS adapter (open)
- [#13](https://github.com/NIDHOGGR-shadow/worthkind/issues/13) — [Worthkind Flow P1 · D07] Make every workflow observable and auditable (open)
- [#12](https://github.com/NIDHOGGR-shadow/worthkind/issues/12) — [Worthkind Flow P1 · D06] Persist idempotent human case queue (open)
- [#11](https://github.com/NIDHOGGR-shadow/worthkind/issues/11) — [Worthkind Flow P1 · V5-03] Establish versioned evaluation and release gating (open)
- [#10](https://github.com/NIDHOGGR-shadow/worthkind/issues/10) — [Worthkind Flow P1 · D05] Evaluate rules, extraction and optional grounded agent (open)
- [#9](https://github.com/NIDHOGGR-shadow/worthkind/issues/9) — [Worthkind Flow P1 · D04] Add tenant-scoped approved knowledge CMS (open)
- [#8](https://github.com/NIDHOGGR-shadow/worthkind/issues/8) — [Worthkind Flow P1 · V5-04] Complete staff handoff lifecycle and guest status (open)
- [#7](https://github.com/NIDHOGGR-shadow/worthkind/issues/7) — [Worthkind Flow P1 · V5-02] Implement atomic business audit and transactional outbox (open)
- [#6](https://github.com/NIDHOGGR-shadow/worthkind/issues/6) — [Worthkind Flow P1 · D03] Implement production tenant identity and role-based permissions (open)
- [#5](https://github.com/NIDHOGGR-shadow/worthkind/issues/5) — [Worthkind Flow P1 · D02] Deliver all direct, no-AI and human-first guest paths (open)
- [#4](https://github.com/NIDHOGGR-shadow/worthkind/issues/4) — [Worthkind Flow P1 · V5-01] Separate property resolution, guest proofing and staff authentication (open)
- [#3](https://github.com/NIDHOGGR-shadow/worthkind/issues/3) — [Worthkind Flow P0 · D01] Validate pilot hotel workflows and PMS capability (open)

## Original pull request index (29 matching branches/titles)

- [#72](https://github.com/NIDHOGGR-shadow/worthkind/pull/72) — Fail closed for production-variant fake delivery and untrusted receipt IDs (open, draft)
- [#70](https://github.com/NIDHOGGR-shadow/worthkind/pull/70) — feat(flow): synthetic SQLite provider outcomes, retry/dead-letter and delivery receipts (open, draft)
- [#69](https://github.com/NIDHOGGR-shadow/worthkind/pull/69) — feat(flow): property-scoped SQLite ticket SLA attention queue (dev only) (open, draft)
- [#67](https://github.com/NIDHOGGR-shadow/worthkind/pull/67) — feat(flow): fail-closed hotel provider contracts and integration readiness console (open, draft)
- [#66](https://github.com/NIDHOGGR-shadow/worthkind/pull/66) — test(flow): real Chromium mobile/desktop smoke over disposable SQLite (open, draft)
- [#64](https://github.com/NIDHOGGR-shadow/worthkind/pull/64) — feat(flow): one-step reception-to-department linked tickets on SQLite (open, draft)
- [#63](https://github.com/NIDHOGGR-shadow/worthkind/pull/63) — feat(flow): SQLite hotel knowledge draft, review, approval and public FAQ versioning (open, draft)
- [#62](https://github.com/NIDHOGGR-shadow/worthkind/pull/62) — refactor(flow): keep normal web API while isolating temporary SQLite connections (open, draft)
- [#61](https://github.com/NIDHOGGR-shadow/worthkind/pull/61) — feat(flow): SQLite-backed hotel operations dashboard and accurate property metrics (open, draft)
- [#60](https://github.com/NIDHOGGR-shadow/worthkind/pull/60) — feat(flow): SQLite hotel knowledge draft/review approval in normal web app (open, draft)
- [#59](https://github.com/NIDHOGGR-shadow/worthkind/pull/59) — feat(flow): local hotel operations dashboard from SQLite case and ticket truth (open, draft)
- [#58](https://github.com/NIDHOGGR-shadow/worthkind/pull/58) — feat(flow): ready-to-explore local demo fixtures across guest, tickets and overview (open, draft)
- [#57](https://github.com/NIDHOGGR-shadow/worthkind/pull/57) — feat(flow): data-derived SQLite operations overview for local hotel workflows (open, draft)
- [#56](https://github.com/NIDHOGGR-shadow/worthkind/pull/56) — feat(flow): integrate existing departmental tickets into local SQLite workspace (open, draft)
- [#55](https://github.com/NIDHOGGR-shadow/worthkind/pull/55) — feat(flow): private guest receipt recovery and safe retry UX (local-only) (open, draft)
- [#54](https://github.com/NIDHOGGR-shadow/worthkind/pull/54) — feat(flow): local-first SQLite runner and 24 guest-to-reception journey tests (open, draft)
- [#53](https://github.com/NIDHOGGR-shadow/worthkind/pull/53) — fix(flow): separate guest and staff PostgreSQL credentials and test least privilege (open, draft)
- [#52](https://github.com/NIDHOGGR-shadow/worthkind/pull/52) — feat(flow): encrypted guest enquiry to signed staff reply and private receipt loop (open, draft)
- [#51](https://github.com/NIDHOGGR-shadow/worthkind/pull/51) — feat(flow): verified OIDC staff API and authenticated PostgreSQL case claiming (open, draft)
- [#50](https://github.com/NIDHOGGR-shadow/worthkind/pull/50) — feat(flow): atomic PostgreSQL enquiry and staff case commands (open, draft)
- [#49](https://github.com/NIDHOGGR-shadow/worthkind/pull/49) — feat(flow): PostgreSQL tenant and staff RLS foundation with real-db CI (open, draft)
- [#48](https://github.com/NIDHOGGR-shadow/worthkind/pull/48) — feat(flow): functional reception workspace and master build register (open, draft)
- [#37](https://github.com/NIDHOGGR-shadow/worthkind/pull/37) — fix+docs(flow): protect private API responses and establish engineering recovery baseline (open, draft)
- [#35](https://github.com/NIDHOGGR-shadow/worthkind/pull/35) — feat(flow): review open-source reuse and prototype hotel/AI dashboard (open, draft)
- [#34](https://github.com/NIDHOGGR-shadow/worthkind/pull/34) — docs(flow): master 15-domain hospitality platform architecture (open, draft)
- [#33](https://github.com/NIDHOGGR-shadow/worthkind/pull/33) — docs(flow): research and architect complete WhatsApp channel, operations and AI flow (open, draft)
- [#31](https://github.com/NIDHOGGR-shadow/worthkind/pull/31) — feat(flow): add non-AI hotel IT and staff service ticket desk (open, draft)
- [#29](https://github.com/NIDHOGGR-shadow/worthkind/pull/29) — feat(flow): early-access waitlist preview and audited Lagos prospect research (open, draft)
- [#2](https://github.com/NIDHOGGR-shadow/worthkind/pull/2) — feat: add Worthkind Flow project under existing Worthkind repository (open, draft)

## Remaining gates

Adapt root-relative paths and CI for the new layout; reconcile alternative branches, run the actual application and test suite, verify Supabase/provider integrations and production security independently. Do not treat this transfer as engineering acceptance. Keep production credentials and real guest/customer data out of Git.
