"""
Cost/contract KPI engine — turns normalized vendor contract records
into renewal risk, spend breakdown, and license utilization signals.
Pure calculation, no AI, no I/O: same discipline as kpi_engine.py and
network_engine.py, so every number here is independently testable and
auditable before the AI layer ever narrates it.
"""

from datetime import datetime, timedelta


def calculate_cost_kpis(contracts: list[dict], now: datetime, renewal_window_days: int = 90) -> dict:
    if not contracts:
        return {"insufficient_data": True}

    priced = [c for c in contracts if c["annual_cost"] is not None]
    total_annual_cost = sum(c["annual_cost"] for c in priced)

    cost_by_vendor: dict[str, float] = {}
    for c in priced:
        cost_by_vendor[c["vendor_name"]] = cost_by_vendor.get(c["vendor_name"], 0) + c["annual_cost"]

    renewal_cutoff = now + timedelta(days=renewal_window_days)
    renewing_soon = []
    for c in contracts:
        if not c["renewal_date"]:
            continue
        renewal_dt = datetime.fromisoformat(c["renewal_date"])
        if now <= renewal_dt <= renewal_cutoff:
            renewing_soon.append(
                {
                    "vendor_name": c["vendor_name"],
                    "service_name": c["service_name"],
                    "renewal_date": c["renewal_date"],
                    "annual_cost": c["annual_cost"],
                    "days_until_renewal": (renewal_dt - now).days,
                }
            )
    renewing_soon.sort(key=lambda r: r["days_until_renewal"])

    underutilized = []
    for c in contracts:
        if c["license_count"] and c["licenses_in_use"] is not None:
            utilization_pct = round(100 * c["licenses_in_use"] / c["license_count"], 1)
            if utilization_pct < 70:
                underutilized.append(
                    {
                        "vendor_name": c["vendor_name"],
                        "service_name": c["service_name"],
                        "license_count": c["license_count"],
                        "licenses_in_use": c["licenses_in_use"],
                        "utilization_pct": utilization_pct,
                    }
                )

    missing_cost_data = [
        f"{c['vendor_name']} / {c['service_name']}" for c in contracts if c["annual_cost"] is None
    ]

    return {
        "insufficient_data": False,
        "contract_count": len(contracts),
        "total_annual_cost": round(total_annual_cost, 2),
        "cost_by_vendor": {k: round(v, 2) for k, v in cost_by_vendor.items()},
        "contracts_renewing_soon": renewing_soon,
        "underutilized_licenses": underutilized,
        "missing_cost_data": missing_cost_data,
    }
