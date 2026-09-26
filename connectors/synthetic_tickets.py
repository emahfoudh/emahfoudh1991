"""
Synthetic ticket connector — MVP data source #1.

Reads a CSV that looks like an export from any ITSM tool (Zoho Desk,
ServiceNow, etc.) and normalizes it onto the common Ticket model.
No network calls, no credentials, no employer data — this is the
safe, offline starting point the whole pipeline gets proven against
before a single real API connector is written.
"""

import csv
from datetime import datetime

from connectors.base import Connector


class SyntheticTicketConnector(Connector):
    name = "synthetic_tickets"

    def __init__(self, csv_path: str):
        self.csv_path = csv_path

    def authenticate(self) -> None:
        pass  # nothing to authenticate for a local file

    def fetch(self, since: datetime | None = None) -> list[dict]:
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if since is None:
            return rows
        return [r for r in rows if datetime.fromisoformat(r["opened_at"]) >= since]

    def normalize(self, raw_records: list[dict]) -> list[dict]:
        normalized = []
        for r in raw_records:
            normalized.append(
                {
                    "external_id": r["ticket_id"],
                    "source_system": "synthetic_tickets",
                    "title": r["title"],
                    "category": r["category"],
                    "priority": r["priority"],
                    "status": r["status"],
                    "opened_at": datetime.fromisoformat(r["opened_at"]),
                    "closed_at": datetime.fromisoformat(r["closed_at"]) if r.get("closed_at") else None,
                    "sla_target_hours": float(r["sla_target_hours"]),
                    "assigned_to": r["assigned_to"],
                    "vendor": r.get("vendor") or None,
                }
            )
        return normalized
