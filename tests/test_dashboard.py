"""
Tests for the dashboard HTML rendering functions. Pure string
generation, no HTTP or database involved — the FastAPI route itself
is exercised manually since it requires a running server, but the
rendering logic that produces its HTML is covered directly here.
"""

from datetime import datetime
from types import SimpleNamespace

from api.dashboard import render_dashboard, render_empty_state


def test_render_empty_state_mentions_how_to_generate_a_report():
    html = render_empty_state()
    assert "No report yet" in html
    assert "main.py" in html


def test_render_dashboard_shows_kpi_tiles():
    snapshot = SimpleNamespace(
        period_label="Test Period",
        computed_at=datetime(2026, 1, 1),
        ticket_kpis={"insufficient_data": False, "total_tickets": 10, "open_tickets": 2, "sla_compliance_pct": 90.0, "mttr_hours": 5.0},
        network_kpis={"flagged_sites": ["site_x"]},
    )
    report = SimpleNamespace(
        ai_report_json={
            "generated_by": "claude",
            "executive_summary": "All good.",
            "recurring_problems": ["network (4 occurrences)"],
            "risk_observations": [],
            "vendor_observations": [],
            "cost_observations": [],
            "recommended_actions": [],
            "management_attention_items": [],
        }
    )

    html = render_dashboard(snapshot, report)

    assert "Test Period" in html
    assert "10" in html  # total tickets tile
    assert "90.0%" in html
    assert "All good." in html
    assert "network (4 occurrences)" in html
    assert "Insufficient data" in html  # empty sections still render the fallback


def test_render_dashboard_shows_time_windowed_tiles():
    snapshot = SimpleNamespace(
        period_label="Test Period",
        computed_at=datetime(2026, 1, 1),
        ticket_kpis={
            "insufficient_data": False,
            "total_tickets": 10,
            "open_tickets": 2,
            "sla_compliance_pct": 90.0,
            "mttr_hours": 5.0,
            "closed_last_7_days": 4,
            "closed_last_30_days": 9,
            "opened_today_assigned": 3,
            "opened_today_unassigned": 1,
        },
        network_kpis={},
    )

    html = render_dashboard(snapshot, None)

    assert "Closed This Week" in html
    assert "Closed This Month" in html
    assert "Assigned Today" in html
    assert "Unassigned Today" in html


def test_render_dashboard_shows_technician_performance_table():
    snapshot = SimpleNamespace(
        period_label="Test Period",
        computed_at=datetime(2026, 1, 1),
        ticket_kpis={"insufficient_data": True},
        network_kpis={},
        technician_performance={
            "insufficient_data": False,
            "by_technician": {
                "engineer_a": {"total_tickets": 10, "closed_tickets": 9, "open_tickets": 1, "sla_compliance_pct": 90.0, "mttr_hours": 5.0},
                "unassigned": {"total_tickets": 3, "closed_tickets": 0, "open_tickets": 3, "sla_compliance_pct": None, "mttr_hours": None},
            },
            "ranking_best_to_worst": ["engineer_a"],
            "excluded_from_ranking": ["unassigned"],
        },
    )

    html = render_dashboard(snapshot, None)

    assert "engineer_a" in html
    assert "90.0" in html
    assert "unassigned" in html
    assert "—" in html  # excluded rank marker


def test_render_dashboard_shows_cost_tiles_when_present():
    snapshot = SimpleNamespace(
        period_label="Test Period",
        computed_at=datetime(2026, 1, 1),
        ticket_kpis={"insufficient_data": True},
        network_kpis={},
        cost_kpis={
            "insufficient_data": False,
            "total_annual_cost": 123000.0,
            "contracts_renewing_soon": [{"vendor_name": "vendor_x"}],
        },
    )

    html = render_dashboard(snapshot, None)

    assert "123,000.0" in html
    assert "Annual Spend Tracked" in html
    assert "Renewals Due Soon" in html


def test_render_dashboard_handles_missing_cost_kpis_attribute():
    # Older snapshots (pre-Phase-5) won't have a cost_kpis attribute at all.
    snapshot = SimpleNamespace(
        period_label="Test Period",
        computed_at=datetime(2026, 1, 1),
        ticket_kpis={"insufficient_data": True},
        network_kpis={},
    )

    html = render_dashboard(snapshot, None)  # must not raise AttributeError

    assert "Test Period" in html


def test_render_dashboard_handles_no_report_object():
    snapshot = SimpleNamespace(
        period_label="Test Period",
        computed_at=datetime(2026, 1, 1),
        ticket_kpis={"insufficient_data": True},
        network_kpis={},
    )

    html = render_dashboard(snapshot, None)

    assert "Test Period" in html
    assert "Insufficient data" in html


def test_render_dashboard_escapes_html_in_user_generated_content():
    snapshot = SimpleNamespace(
        period_label="<script>alert(1)</script>",
        computed_at=datetime(2026, 1, 1),
        ticket_kpis={"insufficient_data": True},
        network_kpis={},
    )

    html = render_dashboard(snapshot, None)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
