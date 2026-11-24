"""Pure deadline classification for local Worthkind development ticket SLAs."""
from datetime import datetime, timezone
from math import ceil


def classify_due(due_at, status: str, now: datetime, soon_minutes: int = 60):
    """Return (classification, minutes) with UTC-normalized deadline semantics.

    Minutes are rounded upward. An expired deadline is overdue at the first
    positive fraction of a minute; a future deadline within the threshold is
    due_soon. Invalid dates never masquerade as on-time. Resolved work is
    ignored regardless of due date.
    """
    if status == "resolved":
        return "resolved", None
    if soon_minutes < 1 or soon_minutes > 1440:
        raise ValueError("Soon threshold must be between 1 and 1440 minutes")
    try:
        deadline = datetime.fromisoformat(str(due_at).replace(" ", "T"))
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            raise ValueError("Clock must be timezone-aware")
        seconds = (deadline.astimezone(timezone.utc) - now.astimezone(timezone.utc)).total_seconds()
    except (ValueError, TypeError, OverflowError):
        return "invalid_due", None
    if seconds < 0:
        return "overdue", ceil(-seconds / 60)
    if seconds <= soon_minutes * 60:
        return "due_soon", ceil(seconds / 60)
    return "on_track", ceil(seconds / 60)
