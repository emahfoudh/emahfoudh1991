from datetime import datetime, timedelta

from engines.cost_engine import calculate_cost_kpis


def _contract(vendor_name, service_name, annual_cost=10000.0, renewal_date=None,
              license_count=None, licenses_in_use=None):
    return {
        "vendor_name": vendor_name,
        "service_name": service_name,
        "annual_cost": annual_cost,
        "renewal_date": renewal_date,
        "license_count": license_count,
        "licenses_in_use": licenses_in_use,
    }


def test_empty_contracts_returns_insufficient_data():
    result = calculate_cost_kpis([], now=datetime(2026, 1, 1))
    assert result["insufficient_data"] is True


def test_total_annual_cost_sums_only_priced_contracts():
    now = datetime(2026, 1, 1)
    contracts = [
        _contract("vendor_x", "Email", annual_cost=10000),
        _contract("vendor_y", "Backup", annual_cost=5000),
        _contract("vendor_z", "Firewall", annual_cost=None),
    ]

    result = calculate_cost_kpis(contracts, now)

    assert result["total_annual_cost"] == 15000
    assert result["cost_by_vendor"] == {"vendor_x": 10000, "vendor_y": 5000}
    assert "vendor_z / Firewall" in result["missing_cost_data"]


def test_contracts_renewing_soon_respects_window_and_sorts_by_urgency():
    now = datetime(2026, 1, 1)
    contracts = [
        _contract("vendor_a", "A", renewal_date=(now + timedelta(days=100)).date().isoformat()),  # outside window
        _contract("vendor_b", "B", renewal_date=(now + timedelta(days=10)).date().isoformat()),
        _contract("vendor_c", "C", renewal_date=(now + timedelta(days=50)).date().isoformat()),
    ]

    result = calculate_cost_kpis(contracts, now, renewal_window_days=90)

    renewing = result["contracts_renewing_soon"]
    assert len(renewing) == 2
    assert renewing[0]["vendor_name"] == "vendor_b"  # most urgent first
    assert renewing[1]["vendor_name"] == "vendor_c"


def test_underutilized_licenses_flagged_below_70_percent():
    now = datetime(2026, 1, 1)
    contracts = [
        _contract("vendor_x", "Good", license_count=100, licenses_in_use=90),
        _contract("vendor_y", "Bad", license_count=100, licenses_in_use=40),
    ]

    result = calculate_cost_kpis(contracts, now)

    flagged_vendors = [u["vendor_name"] for u in result["underutilized_licenses"]]
    assert flagged_vendors == ["vendor_y"]


def test_contract_without_renewal_date_is_skipped_not_crashed():
    now = datetime(2026, 1, 1)
    contracts = [_contract("vendor_x", "NoRenewal", renewal_date=None)]

    result = calculate_cost_kpis(contracts, now)

    assert result["contracts_renewing_soon"] == []
