"""
Real Zoho Desk connector — Phase 3, the first live vendor API.

Reads credentials from environment variables only (never hardcoded):
  ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN,
  ZOHO_API_DOMAIN, ZOHO_ORG_ID

Uses the refresh token to obtain a short-lived access token on each
run (access tokens expire in ~1 hour, so we never cache one across
runs). Requests only what Desk.tickets.READ permits, and normalizes
Zoho's ticket shape onto the same common Ticket model the synthetic
connector produces, so nothing downstream (KPI engine, AI layer,
reporting) needs to know or care which connector produced the data.
"""

import os
from datetime import datetime, timedelta

import requests

from connectors.base import Connector

ACCOUNTS_TOKEN_URL_ENV = "ZOHO_ACCOUNTS_DOMAIN"
DEFAULT_ACCOUNTS_DOMAIN = "https://accounts.zoho.ae"

DEFAULT_SLA_HOURS = 24.0


class ZohoDeskConnector(Connector):
    name = "zoho_desk"

    def __init__(self):
        self.client_id = os.environ["ZOHO_CLIENT_ID"]
        self.client_secret = os.environ["ZOHO_CLIENT_SECRET"]
        self.refresh_token = os.environ["ZOHO_REFRESH_TOKEN"]
        self.api_domain = os.environ["ZOHO_API_DOMAIN"].rstrip("/")
        self.org_id = os.environ["ZOHO_ORG_ID"]
        self.accounts_domain = os.environ.get(ACCOUNTS_TOKEN_URL_ENV, DEFAULT_ACCOUNTS_DOMAIN).rstrip("/")
        self._access_token: str | None = None

    def authenticate(self) -> None:
        """Exchange the long-lived refresh token for a short-lived access
        token. Called once per run; never persisted to disk."""
        response = requests.post(
            f"{self.accounts_domain}/oauth/v2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if "access_token" not in payload:
            raise RuntimeError(f"Zoho auth failed: {payload}")
        self._access_token = payload["access_token"]

    def _headers(self) -> dict:
        if not self._access_token:
            raise RuntimeError("authenticate() must be called before fetch()")
        return {
            "Authorization": f"Zoho-oauthtoken {self._access_token}",
            "orgId": self.org_id,
        }

    def fetch(self, since: datetime | None = None) -> list[dict]:
        """Paginate through GET /api/v1/tickets. Zoho Desk's API lives on
        desk.zoho.<region> with an /api/v1/ path — NOT the generic
        api_domain (www.zohoapis.<region>) the OAuth token response
        returns, which is shared across other Zoho products (CRM, etc.)
        and doesn't serve Desk endpoints. Zoho returns up to 100 records
        per page via `from`/`limit`; we stop once a page comes back
        short, which means we've reached the end."""
        tickets: list[dict] = []
        start = 0
        page_size = 100

        while True:
            response = requests.get(
                f"{self.api_domain}/api/v1/tickets",
                headers=self._headers(),
                params={"from": start, "limit": page_size, "sortBy": "createdTime"},
                timeout=30,
            )
            response.raise_for_status()
            page = response.json().get("data", [])
            tickets.extend(page)

            if len(page) < page_size:
                break
            start += page_size

        if since is not None:
            tickets = [
                t for t in tickets
                if t.get("createdTime") and _parse_zoho_datetime(t["createdTime"]) >= since
            ]

        return tickets

    def normalize(self, raw_records: list[dict]) -> list[dict]:
        normalized = []
        for t in raw_records:
            opened_at = _parse_zoho_datetime(t["createdTime"])
            closed_at = _parse_zoho_datetime(t["closedTime"]) if t.get("closedTime") else None
            due_date = _parse_zoho_datetime(t["dueDate"]) if t.get("dueDate") else None

            sla_target_hours = (
                round((due_date - opened_at).total_seconds() / 3600, 1)
                if due_date
                else DEFAULT_SLA_HOURS
            )

            status_type = (t.get("statusType") or t.get("status") or "").lower()
            status = "closed" if status_type in ("closed", "resolved") else "open"

            normalized.append(
                {
                    "external_id": str(t.get("ticketNumber") or t["id"]),
                    "source_system": "zoho_desk",
                    "title": t.get("subject", ""),
                    "category": t.get("category") or "Uncategorized",
                    "priority": t.get("priority") or "Medium",
                    "status": status,
                    "opened_at": opened_at,
                    "closed_at": closed_at,
                    "sla_target_hours": sla_target_hours,
                    "assigned_to": str(t.get("assigneeId") or "unassigned"),
                    "vendor": None,
                }
            )
        return normalized


def _parse_zoho_datetime(value: str) -> datetime:
    """Zoho returns ISO8601 with a 'Z' suffix, e.g. 2026-09-26T10:00:00.000Z.
    Parsed as naive UTC to match the rest of the pipeline's datetime handling."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.replace(tzinfo=None)
