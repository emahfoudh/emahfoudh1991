from datetime import datetime, timedelta

from engines.kpi_engine import calculate_ticket_kpis, detect_recurring_categories
from engines.network_engine import calculate_network_kpis


def _ticket(opened_at, closed_at=None, sla_target_hours=24, category="network", priority="P3", assigned_to="engineer_a"):
    return {
        "opened_at": opened_at,
        "closed_at": closed_at,
        "sla_target_hours": sla_target_hours,
        "category": category,
        "priority": priority,
        "assigned_to": assigned_to,
    }


def test_empty_tickets_returns_insufficient_data():
    result = calculate_ticket_kpis([], now=datetime(2026, 1, 1))
    assert result["insufficient_data"] is True


def test_sla_compliance_calculation():
    now = datetime(2026, 1, 10)
    opened = datetime(2026, 1, 1)
    within_sla = _ticket(opened, opened + timedelta(hours=10), sla_target_hours=24)
    breached_sla = _ticket(opened, opened + timedelta(hours=30), sla_target_hours=24)

    result = calculate_ticket_kpis([within_sla, breached_sla], now)

    assert result["closed_tickets"] == 2
    assert result["sla_compliance_pct"] == 50.0


def test_open_ticket_counted_but_excluded_from_sla():
    now = datetime(2026, 1, 10)
    opened = datetime(2026, 1, 1)
    closed = _ticket(opened, opened + timedelta(hours=5), sla_target_hours=24)
    still_open = _ticket(opened)

    result = calculate_ticket_kpis([closed, still_open], now)

    assert result["total_tickets"] == 2
    assert result["open_tickets"] == 1
    assert result["sla_compliance_pct"] == 100.0  # only closed tickets count toward SLA%


def test_closed_last_7_and_30_days_counts():
    now = datetime(2026, 1, 31)
    opened = datetime(2026, 1, 1)
    closed_3_days_ago = _ticket(opened, now - timedelta(days=3))
    closed_20_days_ago = _ticket(opened, now - timedelta(days=20))
    closed_60_days_ago = _ticket(opened, now - timedelta(days=60))

    result = calculate_ticket_kpis([closed_3_days_ago, closed_20_days_ago, closed_60_days_ago], now)

    assert result["closed_last_7_days"] == 1
    assert result["closed_last_30_days"] == 2  # includes the 3-day and 20-day ones


def test_opened_today_assigned_vs_unassigned():
    now = datetime(2026, 1, 15, 14, 0)
    today_morning = datetime(2026, 1, 15, 8, 0)
    yesterday = datetime(2026, 1, 14, 8, 0)

    assigned_today = _ticket(today_morning, assigned_to="engineer_a")
    unassigned_today = _ticket(today_morning, assigned_to="unassigned")
    assigned_yesterday = _ticket(yesterday, assigned_to="engineer_b")

    result = calculate_ticket_kpis([assigned_today, unassigned_today, assigned_yesterday], now)

    assert result["opened_today_total"] == 2
    assert result["opened_today_assigned"] == 1
    assert result["opened_today_unassigned"] == 1


def test_recurring_category_detection_respects_threshold():
    now = datetime(2026, 1, 1)
    tickets = [_ticket(now, category="network") for _ in range(3)] + [_ticket(now, category="access")]

    recurring = detect_recurring_categories(tickets, min_occurrences=3)

    assert {"category": "network", "count": 3} in recurring
    assert not any(r["category"] == "access" for r in recurring)


def test_network_kpis_flags_underdelivering_site():
    samples = [
        {"site": "site_a", "bandwidth_mbps_committed": 100, "bandwidth_mbps_measured": 98,
         "latency_ms": 10, "packet_loss_pct": 0.1, "uptime_pct": 99.9, "circuit_provider": "isp_x"},
        {"site": "site_b", "bandwidth_mbps_committed": 100, "bandwidth_mbps_measured": 60,
         "latency_ms": 60, "packet_loss_pct": 2.0, "uptime_pct": 97.0, "circuit_provider": "isp_y"},
    ]

    result = calculate_network_kpis(samples)

    assert "site_b" in result["flagged_sites"]
    assert "site_a" not in result["flagged_sites"]


def test_network_kpis_empty_input():
    result = calculate_network_kpis([])
    assert result["insufficient_data"] is True
