"""
Real ManageEngine ServiceDesk Plus (Cloud) connector — read-only.

ManageEngine SDP Cloud authenticates through the same Zoho identity
backend as Zoho Desk, so the OAuth refresh-token flow is identical.
The API base URL and request path are configurable via environment
variables rather than hardcoded, because (as with the Zoho Desk
connector) the exact endpoint needs live verification against the
real portal before it's certain — the generic "api domain" from the
OAuth token response is not reliable across ManageEngine products.

This connector ONLY issues GET requests. There is no create, update,
or delete anywhere in this file, matching every other connector in
this project. It must only ever be pointed at an instance the
operator is explicitly authorized to read from, with a least-
privilege, read-only API credential.

Credentials read from environment variables only:
  SDP_CLIENT_ID
  SDP_CLIENT_SECRET
  SDP_REFRESH_TOKEN
  SDP_API_DOMAIN        (e.g. https://sdpondemand.manageengine.com)
  SDP_ACCOUNTS_DOMAIN    (defaults to https://accounts.zoho.com)
  SDP_PORTAL_NAME        (your portal's subdomain, e.g. "driven")
"""

import os
from datetime import datetime

import requests

from connectors.base import Connector

DEFAULT_ACCOUNTS_DOMAIN = "https://accounts.zoho.com"
DEFAULT_SLA_HOURS = 24.0


class ManageEngineSDPConnector(Connector):
    name = "manageengine_sdp"

    def __init__(self):
        self.client_id = os.environ["SDP_CLIENT_ID"]
        self.client_secret = os.environ["SDP_CLIENT_SECRET"]
        self.refresh_token = os.environ["SDP_REFRESH_TOKEN"]
        self.api_domain = os.environ["SDP_API_DOMAIN"].rstrip("/")
        self.portal_name = os.environ["SDP_PORTAL_NAME"]
        self.accounts_domain = os.environ.get("SDP_ACCOUNTS_DOMAIN", DEFAULT_ACCOUNTS_DOMAIN).rstrip("/")
        self._access_token: str | None = None

    def authenticate(self) -> None:
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
            raise RuntimeError(f"ManageEngine SDP auth failed: {payload}")
        self._access_token = payload["access_token"]

    def _headers(self) -> dict:
        if not self._access_token:
            raise RuntimeError("authenticate() must be called before fetch()")
        return {
            "Authorization": f"Zoho-oauthtoken {self._access_token}",
            # SDP's v3 API requires this versioned media type on Accept;
            # a live 415 Unsupported Media Type confirmed it's required.
            "Accept": "application/vnd.manageengine.sdp.v3+json",
        }

    def fetch(self, since: datetime | None = None) -> list[dict]:
        """
        Paginate through GET /api/v3/requests — read-only, no other HTTP
        method is ever used. An earlier version of this connector
        included /app/{portal}/ in the path and got a live 404; this
        path assumes the tenant/portal is instead resolved from the
        OAuth token itself. Still unverified whether THIS path is
        correct — read the next live response before assuming it works.
        """
        tickets: list[dict] = []
        start_index = 1
        row_count = 100

        while True:
            list_info = {
                "row_count": row_count,
                "start_index": start_index,
                "sort_field": "created_time",
                "sort_order": "asc",
            }
            response = requests.get(
                f"{self.api_domain}/api/v3/requests",
                headers=self._headers(),
                params={"input_data": _json_dumps({"list_info": list_info})},
                timeout=30,
            )
            response.raise_for_status()
            body = response.json()
            page = body.get("requests", [])
            tickets.extend(page)

            if len(page) < row_count:
                break
            start_index += row_count

        if since is not None:
            tickets = [t for t in tickets if t.get("created_time") and _parse_sdp_datetime(t["created_time"]) >= since]

        return tickets

    def normalize(self, raw_records: list[dict]) -> list[dict]:
        normalized = []
        for t in raw_records:
            opened_at = _parse_sdp_datetime(t["created_time"])
            # Field name for closure time is unconfirmed - try both
            # observed candidates rather than assuming one.
            closed_time_raw = t.get("completed_time") or t.get("resolved_time")
            closed_at = _parse_sdp_datetime(closed_time_raw) if closed_time_raw else None
            due_date = _parse_sdp_datetime(t["due_by_time"]) if t.get("due_by_time") else None

            sla_target_hours = (
                round((due_date - opened_at).total_seconds() / 3600, 1) if due_date else DEFAULT_SLA_HOURS
            )

            status_obj = t.get("status", {}) or {}
            status_name = (status_obj.get("internal_name") or status_obj.get("name") or "").lower()
            # Status names are admin-configurable per instance, so this list
            # covers the common terminal states observed in practice
            # (confirmed against a live "Canceled" ticket that was
            # incorrectly counted as open before this fix). Not
            # exhaustive - a custom terminal status name would still be
            # missed, which is a real limitation, not a hidden one.
            TERMINAL_STATUSES = {"closed", "resolved", "cancelled", "canceled"}
            status = "closed" if status_name in TERMINAL_STATUSES else "open"

            normalized.append(
                {
                    "external_id": str(t.get("id")),
                    "source_system": "manageengine_sdp",
                    "title": t.get("subject", ""),
                    "category": (t.get("category", {}) or {}).get("name") or "Uncategorized",
                    "priority": (t.get("priority", {}) or {}).get("name") or "Medium",
                    "status": status,
                    "opened_at": opened_at,
                    "closed_at": closed_at,
                    "sla_target_hours": sla_target_hours,
                    "assigned_to": (t.get("technician", {}) or {}).get("name") or "unassigned",
                    "vendor": None,
                }
            )
        return normalized


def _json_dumps(obj: dict) -> str:
    import json

    return json.dumps(obj)


def _parse_sdp_datetime(value) -> datetime:
    """
    SDP's API typically returns time fields as a dict like
    {"value": "1698307200000", "display_value": "..."} where value is
    epoch milliseconds — NOT an ISO string like Zoho Desk. This is
    unverified against a live response and likely needs adjustment.
    """
    if isinstance(value, dict) and "value" in value:
        return datetime.fromtimestamp(int(value["value"]) / 1000)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    raise ValueError(f"Unrecognized SDP datetime format: {value!r}")
