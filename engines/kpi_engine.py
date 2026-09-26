"""
KPI engine — turns normalized ticket records into the numbers an IT
Manager actually reports on. Pure functions, no AI, no I/O: this is
the deterministic, testable core of the platform. If a number is
wrong, it's wrong here, and a unit test catches it — nothing here
depends on an LLM being right.
"""

from collections import Counter
from datetime import datetime, timedelta

UNASSIGNED_MARKER = "unassigned"


def _duration_hours(opened_at: datetime, closed_at: datetime | None, now: datetime) -> float:
    end = closed_at or now
    return (end - opened_at).total_seconds() / 3600


def calculate_ticket_kpis(tickets: list[dict], now: datetime) -> dict:
    if not tickets:
        return {"insufficient_data": True}

    total = len(tickets)
    closed = [t for t in tickets if t["closed_at"] is not None]
    open_tickets = [t for t in tickets if t["closed_at"] is None]

    sla_met = sum(
        1 for t in closed if _duration_hours(t["opened_at"], t["closed_at"], now) <= t["sla_target_hours"]
    )
    sla_pct = round(100 * sla_met / len(closed), 1) if closed else None

    mttr_hours = (
        round(sum(_duration_hours(t["opened_at"], t["closed_at"], now) for t in closed) / len(closed), 1)
        if closed
        else None
    )

    aging_buckets = {"0-1d": 0, "1-3d": 0, "3-7d": 0, "7d+": 0}
    for t in open_tickets:
        age_days = _duration_hours(t["opened_at"], None, now) / 24
        if age_days <= 1:
            aging_buckets["0-1d"] += 1
        elif age_days <= 3:
            aging_buckets["1-3d"] += 1
        elif age_days <= 7:
            aging_buckets["3-7d"] += 1
        else:
            aging_buckets["7d+"] += 1

    category_counts = Counter(t["category"] for t in tickets)
    priority_counts = Counter(t["priority"] for t in tickets)
    engineer_counts = Counter(t["assigned_to"] for t in tickets)

    # Time-windowed views: "how much closed this week/month", "today's
    # intake, assigned vs not" — the daily/weekly/monthly breakdown an
    # IT Manager actually reports on, not just a single period total.
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    closed_last_7_days = sum(1 for t in closed if t["closed_at"] >= week_ago)
    closed_last_30_days = sum(1 for t in closed if t["closed_at"] >= month_ago)

    opened_today = [t for t in tickets if t["opened_at"].date() == now.date()]
    opened_today_assigned = sum(1 for t in opened_today if t["assigned_to"] != UNASSIGNED_MARKER)
    opened_today_unassigned = sum(1 for t in opened_today if t["assigned_to"] == UNASSIGNED_MARKER)

    return {
        "insufficient_data": False,
        "total_tickets": total,
        "open_tickets": len(open_tickets),
        "closed_tickets": len(closed),
        "sla_compliance_pct": sla_pct,
        "mttr_hours": mttr_hours,
        "aging_buckets": aging_buckets,
        "category_counts": dict(category_counts),
        "priority_counts": dict(priority_counts),
        "workload_by_engineer": dict(engineer_counts),
        "top_category": category_counts.most_common(1)[0] if category_counts else None,
        "closed_last_7_days": closed_last_7_days,
        "closed_last_30_days": closed_last_30_days,
        "opened_today_total": len(opened_today),
        "opened_today_assigned": opened_today_assigned,
        "opened_today_unassigned": opened_today_unassigned,
    }


def detect_recurring_categories(tickets: list[dict], min_occurrences: int = 3) -> list[dict]:
    """
    Flags categories with repeated tickets in the period — the
    "recurring problem" signal the AI layer turns into a management
    talking point. Deliberately simple for MVP: a count threshold,
    not clustering. Good enough to prove the pipeline; refine later.
    """
    counts = Counter(t["category"] for t in tickets)
    return [
        {"category": category, "count": count}
        for category, count in counts.items()
        if count >= min_occurrences
    ]
