"""
Synthetic vendor/contract connector — the manual-entry cost data
source described in the original spec. A real customer eventually
types this in through a form (vendor, service, cost, renewal date,
license count); for now it's read from a CSV with the same shape,
so the KPI engine and reporting work identically once that form
exists.
"""

import csv

from connectors.base import Connector


class SyntheticContractConnector(Connector):
    name = "synthetic_contracts"

    def __init__(self, csv_path: str):
        self.csv_path = csv_path

    def authenticate(self) -> None:
        pass

    def fetch(self, since=None) -> list[dict]:
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def normalize(self, raw_records: list[dict]) -> list[dict]:
        normalized = []
        for r in raw_records:
            normalized.append(
                {
                    "vendor_name": r["vendor_name"],
                    "service_name": r["service_name"],
                    "annual_cost": float(r["annual_cost"]) if r.get("annual_cost") else None,
                    "renewal_date": r.get("renewal_date") or None,
                    "license_count": int(r["license_count"]) if r.get("license_count") else None,
                    "licenses_in_use": int(r["licenses_in_use"]) if r.get("licenses_in_use") else None,
                }
            )
        return normalized
