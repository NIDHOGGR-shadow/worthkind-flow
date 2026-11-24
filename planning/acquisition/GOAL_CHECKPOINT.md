# Worthkind Flow — Goal Setting Commercial Checkpoint

- **Goal ID:** `WF-WAITLIST-2026-11-17`; existing source-of-truth tracker: [issue #28](https://github.com/NIDHOGGR-shadow/worthkind/issues/28).
- **Owner / last update:** Worthkind founder; research and drafting assistant, 2026-11-18 UTC.
- **State:** `active` for research and prototype; **blocked on real owner-led contact, informed opt-ins and pilot signatures** for conversion milestones.
- **Execution mode:** start-to-finish session, **not a recurring automation**. No task runs in the background without a later explicit session or authorized schedule.
- **Outcome:** 20 *verified* opt-ins / 10 completed interviews / 3 written non-binding design-partner commitments.
- **30-day proposal:** 2026-11-17 through 2026-12-17; review after first genuine outreach evidence.
- **Repository:** `NIDHOGGR-shadow/worthkind`, scoped under `projects/worthkind-flow`.
- **Artifact source:** [dependent draft PR #29](https://github.com/NIDHOGGR-shadow/worthkind/pull/29), branch `feat/worthkind-flow-waitlist-pilot`, base `feat/worthkind-flow-foundation`.
- **Approved criteria:** 15–100 room *preference*; Lagos active independent/regional properties, buyer access, independently verified hotel identity; explicit waitlist consent with timestamp and role; written, specifically scoped and owner-identified pilot commitment. Never count a searched record as opted in.
- **Deduplication key:** canonical physical hotel + address; grouped buyers flagged as a shared purchasing organization; legacy `L###` identifiers preserved.

## Verified research ledger — 2026-11-18

| Metric | Batch 01 | Batch 02 | Batch 03 | Batch 04 | Combined |
| --- | ---: | ---: | ---: | ---: | ---: |
| Distinct physical-property candidates screened | 40 | 30 | 36 | 31 | **137** |
| Contemporary public property / listing corroboration | 25 | 10 | 31 | 30 | **96** |
| Pending basic source or hotel-type evidence | 11 | 19 | 4 | 1 | **35** |
| Outside preferred initial room size | 4 | 1 | 1 | 0 | **6** |
| Duplicates detected within saved batches | 0 | 0 | 0 | 0 | **0 known** |
| Hotels contacted with evidence in this campaign | 0 | 0 | 0 | 0 | **0** |
| Explicit qualified waitlist opt-ins | 0 | 0 | 0 | 0 | **0 / 20** |
| Completed discovery interviews | 0 | 0 | 0 | 0 | **0 / 10** |
| Written pilot commitments | 0 | 0 | 0 | 0 | **0 / 3** |

**Public-presence corroboration yield:** 96/137 = **70.1%**, a *research-screen metric only*. It does not establish inventory, owner authority, need, or buyer consent. No observed sales conversion rate exists (zero authorized calls/reached buyers in this campaign). **Public presence is not full ICP/buyer qualification; nearly all inventories and all decision-maker permissions remain unverified.**

**External commercial blockers:** real decision-maker access, informed opt-ins, completed hotel interviews and written pilot expressions. **No lead or research record counts toward the three outcome targets without its required evidence.**

## Accepted evidence and source ledger

- [Batch 01 — 40 source-linked properties](BATCH_01_PUBLIC_SCREEN.md), based on Nov 9 Library research and contemporary sources.
- [Batch 02 — 30 additional property screens](BATCH_02_PUBLIC_SCREEN.md), Victoria Island, Ikoyi and Lekki.
- [Batch 03 — 36 additional property screens](BATCH_03_PUBLIC_SCREEN.md), Yaba, Oniru, Lekki and remaining original hotel IDs L095–L105.
- [Batch 04 — 31 additional public-source screens](BATCH_04_PUBLIC_SCREEN.md), including new Surulere, Yaba, Ikeja and Lekki properties; 30 public-presence corroborations and one pending hotel-type classification.
- [Supplemental founder business-line call queue](CALL_QUEUE_02.md), 10 lines drawn from hotel sites and third-party listings; none dialled.
- [Prospecting scripts and discovery guide](OUTREACH_PLAYBOOK.md).
- [Competitive references and differentiator hypotheses](COMPETITOR_REALITY.md).
- [Non-binding pilot expression template](PILOT_EXPRESSION_OF_INTEREST_TEMPLATE.md).
- [Waitlist preview source](../../apps/waitlist/README.md) — isolated, *not* deployed and **not** ready for real prospect data.

Sample corroboration audit (public presence and room counts, not waitlist units): L001 Perch official site; L032 Adna official booking page; L061 Victoria Crown Plaza official 49-room site; L073 The George official 61 rooms; L084 Lilygate official 74 rooms. All five remained **uncontacted**, and buyer authority was not inferred.

## Prototype and security

- Draft PR #29 builds a dev-only form, explicit early-access consent, distinct optional marketing consent, pending verification, private withdrawal token, preview rate-limit, no public export, and no live CRM or outbound messaging.
- API **fails closed for production**; no actual customer data should be entered before a reviewed, authorized deployment.
- Tests previously passed on [GitHub Actions run 44020821862](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44020821862), including 8 waitlist tests per Python version and original site regression. New Batch 03 documentation requires latest-head CI status check.
- The product cannot yet claim completed reservations, payments, WhatsApp/voice automation or live hotel integrations.

## Exact continuation

1. **Founder action:** personally call first [CALL_QUEUE_01](CALL_QUEUE_01.md): Perch, Green House, Kelin, Adna, Triedent, Msquare, VCP and the remaining first-round hotels. [CALL_QUEUE_02](CALL_QUEUE_02.md) adds Shoregate (76 published rooms), Corniche (17/28 room discrepancy plus existing iPMS247 booking), Greatville and more publicly sourced business lines. GTA branches may have the same buying group. Request a buyer/reception decision maker; do not assume problems or consent. Log calls in a permissioned CRM, not GitHub.
2. **Record each outcome:** stable hotel ID; who answered and role; observed current booking workflow; actual problem; room count; next action; whether product updates were *explicitly* authorized; date of a proposed meeting; declined/no contact.
3. **Research after outreach prep:** new names up to WFNEW057 are screened. Reconcile Corniche's conflicting 17/28 official room descriptions, independently test buyer access/room size of the 10 best candidates in Batch 04 and ask what the existing vendor (iPMS247 for Corniche) already does. Next discovery batch must dedupe against all **137**; no historical non-hotel L106–L129 entries.
4. **Engineering:** implement genuine secure hosted storage, verified email ownership, controller privacy notice, deletion rights, approved anti-abuse and staff-only review queue. Test before requesting deployment approval. Merge base PR #2 only after its own technical review; PR #29 is dependent.
5. **Partner pipeline:** after real discovery, draft one hotel-specific trial plan and obtain written non-binding expression-of-interest with named hotel owner and measurable task outcome; count only after evidence.
6. **Next save condition:** verified founder call outcomes from either queue, or another 25–40 independently screened new properties **after** Batch 04 (137 already screened) with source links and an updated checkpoint. Prefer observed buyer outcomes over more unscreened names.
7. **Blockers:** no phone-dial action or signed-pilot execution is available in this session. Never invent human outreach, opt-ins or signatures. The user must authorize or conduct the actual calls.

## Milestone history

| Milestone | Date | Screened | Public corroborated | Qualified opt-ins | Evidence | State |
| --- | --- | ---: | ---: | ---: | --- | --- |
| Existing goal contract | 2026-11-16 | 0 in this goal ledger | 0 | 0 | Issue #28 | Planned |
| Batch 01 + preview | 2026-11-17 | 40 | 25 | 0 | Batch 01; draft PR #29 | Done research, no outreach |
| Batch 02 + competitor audit | 2026-11-17 | 30 | 10 | 0 | Batch 02; competitor brief | Done research, no outreach |
| Batch 03 + Yaba/Lekki expansion | 2026-11-17 | 36 | 31 | 0 | Batch 03 source ledger | Done research, no outreach |
| Batch 04 + verified business-line expansion | 2026-11-18 | 31 | 30 | 0 | Batch 04 + Call Queue 02 | Done research, owner calls pending |

**Completion rule:** must have 20 verified opt-ins **AND** 10 completed discovery interviews **AND** 3 written pilot expressions. Never close issue #28 on research output alone.
