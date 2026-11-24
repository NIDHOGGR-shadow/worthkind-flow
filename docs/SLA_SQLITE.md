# Local SQLite service deadline attention queue

**Status as of 2026-11-20:** implementation committed on the dependent draft SLA branch. Core pure deadline classification passed six manual local assertions, and a separate SQLite-backed FastAPI route contract passed seven local assertions from `scripts/sla_isolated_smoke.py`. Full Worthkind API/UI/browser CI remains **unverified** while [CI issue #68](https://github.com/NIDHOGGR-shadow/worthkind/issues/68) is unresolved. **No real notification, hotel SLA or production authorization is implied.**

## Source / calculations

- Existing `service_tickets` table: `property_id`, `status`, `due_at`, `priority`, `category`, `subject`, `origin_case_id`.
- One hotel-scoped read endpoint: `GET /api/properties/{slug}/staff/operations/attention?limit=50`, requiring the existing **development-only** staff key.
- The UTC evaluator `apps/api/sla_rules.py` classifies unresolved tickets:
  - **overdue:** deadline strictly before the snapshot time; reports upward-rounded elapsed minutes
  - **due_soon:** deadline now or in the next 60 minutes; reports upward-rounded remaining minutes
  - **on_track:** more than 60 minutes until deadline
  - **invalid_due:** missing, malformed or out-of-range deadline—visible as a data quality issue rather than being misrepresented as on-time
  - **resolved:** excluded from active attention irrespective of deadline
- Sorted action list prioritizes overdue, invalid due dates, then due soon. Counts include all unresolved tickets for this property. API returns the `source`, `generated_at`, limited queue, `actionable_total`, `truncated`, `alerts_sent: 0` and `provider_connected: false`.
- Hotel operations UI fetches only when staff clicks **Review deadline queue**. Changing hotel or key clears previous details and prevents stale responses from leaking into the new context.

## Developer walkthrough

1. Run the local SQLite FastAPI app with synthetic hotel keys (see [local dev setup](LOCAL_FIRST.md)).
2. Create development maintenance and reception tickets using `/staff/tickets`, ideally with both hotels represented.
3. For test purposes on an isolated database, adjust `due_at` of one unresolved ticket to before current UTC, one to within 60 minutes, one further ahead, and another to invalid text. Keep real guest records out of SQLite.
4. Open `/staff/operations` with hotel A's local key, load overview, then review its deadline queue.
5. Confirm overdue, due soon and invalid tickets are listed. Resolved and other-property tickets must never be present.
6. Switch to hotel B; the previous hotel queue must be wiped, and the old key must not authorize hotel B.

## Validation / limitations

- **Pure local rules:** six direct assertions passed on 2026-11-20 for expired by one second, 60/61 minute boundary, resolved, invalid and naive UTC.
- **Isolated local API contract:** `python scripts/sla_isolated_smoke.py` executed seven assertions successfully using a disposable SQLite database and real FastAPI TestClient. This exercises the same `sla.py` and `sla_rules.py` sources in an isolated test harness, not the complete Worthkind application.\n- **Committed full-app unit/integration/UI assertions:** `apps/api/tests/test_sla.py` and the updated `apps/web/tests/operations-ui.test.cjs` cover actual SQLite tenant isolation, no-cache private replies, deadline ordering, dismissed resolved tasks, limit semantics and no false notification indicators.
- **Do not claim integrated tests passing** until GitHub Actions records executed steps and success. Previous [run #114](https://github.com/NIDHOGGR-shadow/worthkind/actions/runs/44803214893) and follow-up runs had failures without steps/logs; see [issue #68](https://github.com/NIDHOGGR-shadow/worthkind/issues/68).
- This is not a real staff notification or SLA enforcement mechanism. Department/owner roles, escalation assignments, approved hotel policy, signed provider receipts and alert delivery must be implemented and verified separately.
- **SQLite is only the development database** until the owner chooses Supabase or another managed database. Worthkind Flow is a connected web application, not an offline-only app.
