# Worthkind Flow — Hotel knowledge review on local SQLite

**Stage:** Development, built on the existing normal web application. Supabase provisioning is deferred by owner decision; SQLite is the current development database, not an offline-product requirement.

## What this slice implements

- A hotel-scoped staff knowledge workspace at **/staff/knowledge**, reachable from Reception, Tickets and Operations.
- Unpublished draft proposals with an idempotency key and source/reference. Drafting never changes the public answer.
- A local development approval command that checks the proposed base version, creates a numbered approved revision and updates the existing public FAQ.
- Rejection with audit reason; withdrawal that increments the version, writes a historical record, and makes the public FAQ immediately abstain rather than deleting prior evidence.
- SQLite audit data and revision history recorded in the same transaction as a knowledge change.
- Deterministic question→topic mapping for hotel name, booking, human help, dining, events, parking, check-in, check-out, amenities, accessibility and cancellation. **No external AI model** is used, and a topic without approved content responds with `unknown` and a direct human path.
- A reviewer workspace with the actual public guest FAQ preview, based on the local API—not on a separate sample JSON display.

## Demo walkthrough

1. Follow [local SQLite setup](LOCAL_FIRST.md) and launch `python scripts/local_dev.py start --seed-demo`.
2. Open http://127.0.0.1:8765/staff/knowledge and enter the local development staff key for one synthetic hotel.
3. Select Dining, write a clearly **synthetic** answer and cite a synthetic local verification note. Save as unpublished draft.
4. In the public preview, ask about the restaurant. The FAQ must abstain until that draft is approved.
5. Approve the draft. Recheck the public preview: it now shows the approved local version/source and no AI execution.
6. Create two competing drafts based on the same version, approve one and verify the stale other is rejected (409).
7. Supply a withdrawal explanation, withdraw the published fact and recheck: the public FAQ must stop exposing the answer. History must retain the prior version.
8. Change hotel. The former property's draft/answer/history must disappear, and the former hotel's staff key must not authorize the new hotel.

## Development data and authorization limitations

This is **not production approval**. A development staff key grants both draft and approval permissions, so there is no individual verified actor, true dual control, shift scope or managerial sign-off. The client and API label this fact. Use no real hotel policy, guest details or employee documents in the current plaintext development SQLite. Every answer and approval here is synthetic.

A real hotel integration must add verified property owner/content manager authorization; distinct role capabilities; versioned publishing/rollback and provenance requirements; privacy and data retention review; approvals for operationally sensitive content; and independent tests. Actual reservation availability, money, cancellations and service fulfillment must never be inferred from typed FAQ text.

## Implementation layout

- `apps/api/knowledge.py`: SQLite schema `knowledge_drafts`, `knowledge_revisions`, `knowledge_audit`; validation, authenticated commands, atomic history, deterministic topic lookup.
- `apps/api/main.py`: route installation and public FAQ reads from `public_facts` where `approved=1`.
- `apps/web/knowledge.html`, `knowledge.js` and shared `styles.css`: responsive staff review UI, safe text rendering, mutation/reload and visible pending/error states.
- `apps/api/tests/test_knowledge.py`: approval, withdrawal, revision conflicts, cross-hotel permissions, rollback and idempotency tests.
- `apps/web/tests/knowledge-ui.test.cjs`: UI interaction tests with synthetic responses; not a real-browser accessibility verdict.
- `.github/workflows/worthkind-flow-ci.yml`: API and JS tests alongside the existing website regression.

Existing synthetic public facts seeded before this feature may have version 1 without a corresponding managed `knowledge_revisions` row; new approved/withdrawn actions are recorded from the first managed change onward. A future audited migration should import legacy baseline sources before real hotel cutover.

## Status and release gates

The new workflow remains a **draft GitHub PR**, not deployed. Its development behavior is marked TESTED only after the relevant CI run succeeds; manual browser/keyboard/screen reader and real identity/approval tests are separate. Continue to use the production import guard and local synthetic data until actual managed authentication and hotel agreement are in place.
