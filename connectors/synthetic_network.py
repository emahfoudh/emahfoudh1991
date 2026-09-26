"""
Synthetic network/bandwidth connector — MVP data source #2.

This is what a future real connector (FortiGate SD-WAN stats, an ISP's
monitoring API, a PRTG/Zabbix export) would eventually replace. For
now it reads a CSV of daily-per-site bandwidth/latency/uptime samples
that look like what those tools actually export, so the KPI engine
and AI layer are built against realistic shapes from day one.
"""

import csv
from datetime import datetime

from connectors.base import Connector


class SyntheticNetworkConnector(Connector):
    name = "synthetic_network"

    def __init__(self, csv_path: str):
        self.csv_path = csv_path

    def authenticate(self) -> None:
        pass

    def fetch(self, since: datetime | None = None) -> list[dict]:
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if since is None:
            return rows
        return [r for r in rows if datetime.fromisoformat(r["sample_date"]) >= since]

    def normalize(self, raw_records: list[dict]) -> list[dict]:
        normalized = []
        for r in raw_records:
            normalized.append(
                {
                    "site": r["site"],
                    "sample_date": datetime.fromisoformat(r["sample_date"]),
                    "bandwidth_mbps_committed": float(r["bandwidth_mbps_committed"]),
                    "bandwidth_mbps_measured": float(r["bandwidth_mbps_measured"]),
                    "latency_ms": float(r["latency_ms"]),
                    "packet_loss_pct": float(r["packet_loss_pct"]),
                    "uptime_pct": float(r["uptime_pct"]),
                    "circuit_provider": r.get("circuit_provider") or None,
                }
            )
        return normalized
