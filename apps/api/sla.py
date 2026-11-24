"""Property-scoped ticket attention queue over local SQLite.

This exposes DEVELOPMENT deadlines only; it does NOT send notifications,
promise a hotel service SLA, or authorize anyone beyond per-hotel demo keys.
"""
from datetime import datetime, timezone

from fastapi import Header, Query
from sla_rules import classify_due


def install_sla_routes(app, database, property_id, require_staff):
    """Add a read-only staff route listing overdue/soon-due/invalid work."""

    @app.get("/api/properties/{slug}/staff/operations/attention")
    def attention_queue(
        slug: str,
        limit: int = Query(50, ge=1, le=100),
        x_staff_key: str | None = Header(None),
    ):
        require_staff(slug, x_staff_key)
        now = datetime.now(timezone.utc)
        with database() as conn:
            conn.execute("BEGIN")
            pid = property_id(conn, slug)
            rows = conn.execute(
                "SELECT id,category,priority,subject,status,due_at,origin_case_id "
                "FROM service_tickets WHERE property_id=? AND status!='resolved'",
                (pid,),
            ).fetchall()

        counts = {"overdue": 0, "due_soon": 0, "invalid_due": 0, "on_track": 0}
        attention = []
        for row in rows:
            group, minutes = classify_due(row["due_at"], row["status"], now)
            counts[group] = counts.get(group, 0) + 1
            if group not in ("overdue", "due_soon", "invalid_due"):
                continue
            attention.append({
                "ticket_id": row["id"],
                "subject": row["subject"],
                "category": row["category"],
                "priority": row["priority"],
                "status": row["status"],
                "due_at": row["due_at"],
                "origin_case_id": row["origin_case_id"],
                "attention": group,
                "minutes": minutes,
            })

        # Overdue first, then dates that cannot be trusted, then approaching
        # deadlines. Sort deterministically to avoid flickering review order.
        weight = {"overdue": 0, "invalid_due": 1, "due_soon": 2}
        attention.sort(key=lambda row: (
            weight[row["attention"]],
            -row["minutes"] if row["attention"] == "overdue" else (
                row["minutes"] if row["minutes"] is not None else 0
            ),
            row["ticket_id"],
        ))
        return {
            "property": slug,
            "source": "local_sqlite_development",
            "generated_at": now.isoformat(),
            "policy": "Synthetic development priority clocks only; no hotel SLA is guaranteed.",
            "counts": counts,
            "actionable_total": len(attention),
            "items": attention[:limit],
            "truncated": len(attention) > limit,
            "alerts_sent": 0,
            "provider_connected": False,
        }
