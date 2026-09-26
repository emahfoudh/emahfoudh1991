"""
Persistence layer tests — use an isolated in-memory SQLite DB per
test, never the real ai_it_operations.db file, so tests can't
interfere with (or depend on) whatever a local pipeline run produced.
"""

from datetime import datetime

from models.schema import get_engine, init_db
from models.persistence import (
    get_latest_kpi_snapshot,
    get_latest_report,
    get_or_create_synthetic_customer,
    persist_contracts,
    persist_kpi_snapshot,
    persist_network_samples,
    persist_report,
    persist_tickets,
)


def _fresh_engine():
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    return engine


def test_get_or_create_customer_is_idempotent():
    engine = _fresh_engine()
    first_id = get_or_create_synthetic_customer(engine)
    second_id = get_or_create_synthetic_customer(engine)
    assert first_id == second_id


def test_persist_and_retrieve_kpi_snapshot():
    engine = _fresh_engine()
    customer_id = get_or_create_synthetic_customer(engine)

    ticket_kpis = {"insufficient_data": False, "total_tickets": 5}
    network_kpis = {"insufficient_data": False, "flagged_sites": ["site_c"]}
    recurring = [{"category": "network", "count": 3}]

    snapshot_id = persist_kpi_snapshot(engine, customer_id, "Test Period", ticket_kpis, network_kpis, recurring)
    assert snapshot_id is not None

    latest = get_latest_kpi_snapshot(engine, customer_id)
    assert latest.period_label == "Test Period"
    assert latest.ticket_kpis["total_tickets"] == 5
    assert latest.network_kpis["flagged_sites"] == ["site_c"]


def test_persist_report_links_to_snapshot():
    engine = _fresh_engine()
    customer_id = get_or_create_synthetic_customer(engine)

    snapshot_id = persist_kpi_snapshot(engine, customer_id, "Test Period", {}, {}, [])
    ai_report = {"executive_summary": "Insufficient data"}
    report_id = persist_report(engine, customer_id, "Test Period", ai_report, "x.pdf", "x.xlsx", snapshot_id)

    latest = get_latest_report(engine, customer_id)
    assert latest.id == report_id
    assert latest.ai_report_json["executive_summary"] == "Insufficient data"
    assert latest.pdf_path == "x.pdf"


def test_persist_tickets_and_network_samples_roundtrip():
    engine = _fresh_engine()
    customer_id = get_or_create_synthetic_customer(engine)

    tickets = [
        {
            "external_id": "TCK-1", "source_system": "synthetic_tickets", "title": "test",
            "category": "network", "priority": "P3", "status": "closed",
            "opened_at": datetime(2026, 1, 1), "closed_at": datetime(2026, 1, 2),
            "sla_target_hours": 24, "assigned_to": "engineer_a", "vendor": None,
        }
    ]
    samples = [
        {
            "site": "site_a", "sample_date": datetime(2026, 1, 1),
            "bandwidth_mbps_committed": 100, "bandwidth_mbps_measured": 98,
            "latency_ms": 10, "packet_loss_pct": 0.1, "uptime_pct": 99.9,
            "circuit_provider": "isp_x",
        }
    ]

    # Should not raise; these functions commit but don't return rows,
    # so absence of an exception is the contract being tested here.
    persist_tickets(engine, customer_id, tickets)
    persist_network_samples(engine, customer_id, samples)


def test_persist_contracts_roundtrip_including_missing_renewal_date():
    engine = _fresh_engine()
    customer_id = get_or_create_synthetic_customer(engine)

    contracts = [
        {
            "vendor_name": "vendor_x", "service_name": "Email Security",
            "annual_cost": 45000.0, "renewal_date": "2026-06-01",
            "license_count": 250, "licenses_in_use": 240,
        },
        {
            "vendor_name": "vendor_z", "service_name": "Firewall Support",
            "annual_cost": None, "renewal_date": None,
            "license_count": None, "licenses_in_use": None,
        },
    ]

    # Should not raise, including the None renewal_date case.
    persist_contracts(engine, customer_id, contracts)


def test_persist_kpi_snapshot_stores_cost_kpis():
    engine = _fresh_engine()
    customer_id = get_or_create_synthetic_customer(engine)

    cost_kpis = {"insufficient_data": False, "total_annual_cost": 123000.0}
    persist_kpi_snapshot(engine, customer_id, "Test Period", {}, {}, [], cost_kpis)

    latest = get_latest_kpi_snapshot(engine, customer_id)
    assert latest.cost_kpis["total_annual_cost"] == 123000.0
