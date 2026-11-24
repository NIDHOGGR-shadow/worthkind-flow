# Worthkind Flow — Hotel knowledge editor (SQLite development adapter)

## Current user decision

Worthkind Flow remains a normal browser-based web application. The FastAPI server stores development records in SQLite **instead of Supabase for now**. This is not an offline-only feature. [Database portability contract](DATABASE_PORTABILITY.md) covers how the same APIs will later use PostgreSQL/Supabase.

## Start and use

From the Worthkind Flow project directory:

    python scripts/local_dev.py start --seed-demo

Visit http://127.0.0.1:8765/staff/knowledge. Select a synthetic hotel and enter the local staff key printed by the runner. The separate local approval key is printed too, generated privately for that property and saved inside the ignored .local/approval-keys.json file.

1. Load hotel knowledge using the staff key and select one of three local FAQ categories: hotel name, booking enquiry policy or human assistance.
2. Save a proposed fact as a draft. The existing guest answer remains unchanged.
3. Review the draft in the editor. Approve using the separate local approval key. The new published answer appears on the existing guest information endpoint.
4. Optionally withdraw the published fact. The guest answer must then abstain and offer human assistance, not invent another answer.

**Approval is a simulation of the workflow only.** The generated approval key is not a named hotel manager, identity provider or customer authorization. The app must not be used for a real hotel's confidential policies or customer details.

## Data boundaries

- public_facts remains the only guest-facing approved fact source. The public API checks its approved flag; draft content cannot leak through that endpoint.
- knowledge_drafts uses property_id, question_key, base_version and revision for stale-edits detection.
- knowledge_audit records per-property draft, publication and withdrawal events, with a SHA-256 hash of answer text, in the same SQLite transaction as the domain change.
- Two properties cannot approve each other's facts with their respective local keys.
- No passwords or keys are stored in web localStorage, query strings or cookies by the UI. They stay in the current page's memory.
- A withdraw increments published version, invalidating any draft built from the older approved version.

## Verification

- apps/api/tests/test_knowledge_editor.py checks separate local approval credentials, incorrect property, unsupported topics, stale revisions, audit rollback, fact withdrawal, guest fallback and HTTP route availability.
- apps/api/tests/test_local_dev_runner.py checks approval-key generation, file permissions, repeatability and symlink refusal.
- apps/web/tests/knowledge-ui.test.cjs checks save/review/publish, unsaved-edit guards, wrong hotel key and UI context clearing.

These are development tests. Browser layout, keyboard, accessibility, rate limits, individual staff identity, production-grade approval permissions, document provenance, publishing history and real hotel consent still require separate implementation and verification.

## Next work

Build the actual staff/manager invitation and permission flow using SQLite as the current backing database, not a fake offline architecture. Keep the HTTP API contract stable for later Supabase migration. Continue accessible hotel CMS screens and provider adapter contract tests without making unverified external calls.
