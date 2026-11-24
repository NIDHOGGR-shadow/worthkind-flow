"""Property-scoped local operations snapshot for Worthkind Flow.

Development only. No real PMS, delivery provider, occupancy or billing source.
Uses the existing SQLite database; never substitutes synthetic dashboard figures.
"""
from datetime import datetime, timezone
from fastapi import Header

CASE_STATES = ("queued", "claimed", "responded")
TICKET_STATES = ("open", "assigned", "in_progress", "resolved", "reopened")


def _counts(rows, labels):
    counts = {key: 0 for key in labels}
    for row in rows:
        counts[row["status"]] = row["count"]
    return counts


def install_operations_routes(app, database, property_id, require_staff):
    @app.get("/api/properties/{slug}/staff/overview")
    def operations_overview(slug: str, x_staff_key: str | None = Header(None)):
        # The development property credential is only a temporary reference;
        # this MUST be replaced with individual verified staff permissions for
        # real tenant/user data or any remote/public deployment.
        require_staff(slug, x_staff_key)
        now = datetime.now(timezone.utc)

        with database() as conn:
            # Snapshot consistency even while another connection writes.
            conn.execute("BEGIN")
            pid = property_id(conn, slug)
            hotel = conn.execute("SELECT name FROM properties WHERE id=?", (pid,)).fetchone()
            case_rows = conn.execute(
                "SELECT status,COUNT(*) AS count FROM cases WHERE property_id=? GROUP BY status",
                (pid,),
            ).fetchall()
            ticket_rows = conn.execute(
                "SELECT status,COUNT(*) AS count FROM service_tickets WHERE property_id=? GROUP BY status",
                (pid,),
            ).fetchall()
            due_rows = conn.execute(
                "SELECT status,due_at FROM service_tickets WHERE property_id=? AND status!='resolved'",
                (pid,),
            ).fetchall()
            # A local pending outbox entry is NOT sent/delivered. Simulated
            # dev delivery is also not a real provider receipt.
            case_pending = conn.execute(
                "SELECT COUNT(*) FROM outbox WHERE property_id=? AND processed_at IS NULL",
                (pid,),
            ).fetchone()[0]
            ticket_pending = conn.execute(
                "SELECT COUNT(*) FROM ticket_outbox WHERE property_id=? AND processed_at IS NULL",
                (pid,),
            ).fetchone()[0]
            cases = conn.execute(
                "SELECT id,kind,status,created_at FROM cases WHERE property_id=? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 8",
                (pid,),
            ).fetchall()
            tickets = conn.execute(
                "SELECT id,category,priority,status,due_at FROM service_tickets "
                "WHERE property_id=? ORDER BY created_at DESC, rowid DESC LIMIT 8",
                (pid,),
            ).fetchall()

        case_counts = _counts(case_rows, CASE_STATES)
        ticket_counts = _counts(ticket_rows, TICKET_STATES)
        overdue = sum(
            datetime.fromisoformat(row["due_at"]) < now
            for row in due_rows
        )
        return {
            "property": {"slug": slug, "name": hotel["name"]},
            "as_of": now.isoformat(),
            "source": "property_scoped_local_sqlite",
            "data_is_synthetic": True,
            "production_ready": False,
            "cases": {
                "total": sum(case_counts.values()),
                "by_status": case_counts,
                "needs_staff": case_counts["queued"],
                "recent": [dict(row) for row in cases],
            },
            "tickets": {
                "total": sum(ticket_counts.values()),
                "by_status": ticket_counts,
                "unresolved": sum(
                    value for key, value in ticket_counts.items() if key != "resolved"
                ),
                "overdue": overdue,
                "recent": [dict(row) for row in tickets],
            },
            "local_outbox": {
                "pending_case_events": case_pending,
                "pending_ticket_events": ticket_pending,
                "pending_total": case_pending + ticket_pending,
                "external_notifications_sent": None,
                "delivery_authority": "none_local_simulation_only",
            },
            "unsupported": {
                "occupancy": None,
                "arrivals_today": None,
                "confirmed_bookings": None,
                "hotel_payments": None,
                "ai_conversations": None,
                "worthkind_billing": None,
            },
        }
