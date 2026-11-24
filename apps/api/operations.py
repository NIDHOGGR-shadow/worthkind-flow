"""Development hotel operations read model, sourced entirely from local SQLite.

This module deliberately does not invent occupancy, revenue, booking confirmations,
notification delivery, employee identity, or live hotel status. Queries are scoped to
the selected property *after* its development staff key is checked.
"""
from datetime import datetime, timezone

from fastapi import Header


CASE_STATUSES = ("queued", "claimed", "responded")
TICKET_STATUSES = ("open", "assigned", "in_progress", "resolved", "reopened")


def _counts(conn, table, column, property_id, labels):
    """Return all known states (including zeros) for one property only."""
    rows = conn.execute(
        f"SELECT {column} AS label, COUNT(*) AS total FROM {table} "
        "WHERE property_id=? GROUP BY " + column,
        (property_id,),
    ).fetchall()
    counts = {label: 0 for label in labels}
    for item in rows:
        # Keep unexpected/future states visible rather than silently dropping
        # them and understating totals on the management screen.
        counts[str(item["label"] or "unclassified")] = item["total"]
    return counts


def _utc(value):
    parsed = datetime.fromisoformat(value.replace(" ", "T"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def install_operations_routes(app, database, property_id, require_staff):
    """Install property-scoped SQLite operations read route on existing API."""

    @app.get("/api/properties/{slug}/staff/operations/overview")
    def operations_overview(slug: str, x_staff_key: str | None = Header(None)):
        require_staff(slug, x_staff_key)
        with database() as conn:
            # A consistent SQLite read snapshot, including case/ticket/event counts.
            conn.execute("BEGIN")
            pid = property_id(conn, slug)
            property_row = conn.execute(
                "SELECT name FROM properties WHERE id=?", (pid,)
            ).fetchone()

            cases_by_status = _counts(conn, "cases", "status", pid, CASE_STATUSES)
            tickets_by_status = _counts(conn, "service_tickets", "status", pid, TICKET_STATUSES)

            cases_by_kind_rows = conn.execute(
                "SELECT kind, COUNT(*) AS total FROM cases "
                "WHERE property_id=? GROUP BY kind ORDER BY kind",
                (pid,),
            ).fetchall()
            tickets_by_category_rows = conn.execute(
                "SELECT category, COUNT(*) AS total FROM service_tickets "
                "WHERE property_id=? GROUP BY category ORDER BY category",
                (pid,),
            ).fetchall()
            unresolved_due_rows = conn.execute(
                "SELECT due_at FROM service_tickets WHERE property_id=? AND status!='resolved'",
                (pid,),
            ).fetchall()
            now = datetime.now(timezone.utc)
            overdue = 0
            invalid_due_dates = 0
            for row in unresolved_due_rows:
                try:
                    if _utc(row["due_at"]) < now:
                        overdue += 1
                except (TypeError, ValueError, OverflowError):
                    invalid_due_dates += 1

            case_events_pending = conn.execute(
                "SELECT COUNT(*) AS total FROM outbox "
                "WHERE property_id=? AND processed_at IS NULL",
                (pid,),
            ).fetchone()["total"]
            ticket_events_pending = conn.execute(
                "SELECT COUNT(*) AS total FROM ticket_outbox "
                "WHERE property_id=? AND processed_at IS NULL",
                (pid,),
            ).fetchone()["total"]

            # IDs and internal action types only, no guest name/contact/details.
            case_history = conn.execute(
                "SELECT case_id AS ref, action AS action, created_at AS happened_at "
                "FROM audit WHERE property_id=? ORDER BY created_at DESC, rowid DESC LIMIT 15",
                (pid,),
            ).fetchall()
            ticket_history = conn.execute(
                "SELECT ticket_id AS ref, event AS action, created_at AS happened_at "
                "FROM ticket_history WHERE property_id=? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 15",
                (pid,),
            ).fetchall()

        events = []
        for origin, rows in (("guest_case", case_history), ("service_ticket", ticket_history)):
            for row in rows:
                try:
                    occurred = _utc(row["happened_at"])
                except (ValueError, TypeError, OverflowError):
                    continue
                events.append({
                    "type": origin,
                    "reference": row["ref"],
                    "action": row["action"],
                    "occurred_at": occurred.isoformat(),
                })
        events.sort(key=lambda event: event["occurred_at"], reverse=True)

        return {
            "property": {"slug": slug, "display_name": property_row["name"]},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "local_sqlite_development",
            "case_counts": {
                "total": sum(cases_by_status.values()),
                "by_status": cases_by_status,
                "by_kind": {row["kind"]: row["total"] for row in cases_by_kind_rows},
            },
            "ticket_counts": {
                "total": sum(tickets_by_status.values()),
                "by_status": tickets_by_status,
                "by_category": {row["category"]: row["total"] for row in tickets_by_category_rows},
                "unresolved": sum(
                    value for status, value in tickets_by_status.items() if status != "resolved"
                ),
                "overdue": overdue,
                "invalid_due_dates": invalid_due_dates,
            },
            "local_events": {
                "pending_case_events": case_events_pending,
                "pending_ticket_events": ticket_events_pending,
                "pending_total": case_events_pending + ticket_events_pending,
                "provider_delivery_connected": False,
                "delivery_confirmed": False,
                "description": "Local pending records only, not messages sent or delivered.",
            },
            "recent_activity": events[:10],
            "external_metrics": {
                "confirmed_bookings": None,
                "occupancy": None,
                "hotel_revenue": None,
                "agent_usage": None,
                "reason": "No authoritative PMS, payment or AI provider is connected.",
            },
        }
