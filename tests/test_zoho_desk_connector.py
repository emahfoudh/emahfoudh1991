"""
Tests for the Zoho Desk connector's normalization logic, using mocked
HTTP responses shaped like Zoho's real API. This sandbox environment
has no network access to Zoho at all, so these tests never make a
real call — they verify the connector's parsing/mapping logic is
correct, independent of connectivity.
"""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("ZOHO_CLIENT_ID", "test_client_id")
os.environ.setdefault("ZOHO_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("ZOHO_REFRESH_TOKEN", "test_refresh_token")
os.environ.setdefault("ZOHO_API_DOMAIN", "https://www.zohoapis.ae")
os.environ.setdefault("ZOHO_ORG_ID", "170000343054")

from connectors.zoho_desk import ZohoDeskConnector, _parse_zoho_datetime  # noqa: E402


SAMPLE_TICKET_OPEN = {
    "id": "1",
    "ticketNumber": "101",
    "subject": "IT support",
    "category": "Software",
    "priority": "Medium",
    "statusType": "Open",
    "status": "Open",
    "createdTime": "2026-09-26T10:00:00.000Z",
    "dueDate": "2026-09-26T18:00:00.000Z",
    "assigneeId": "555",
}

SAMPLE_TICKET_CLOSED = {
    "id": "2",
    "ticketNumber": "102",
    "subject": "Mobile issue",
    "category": "Mobile",
    "priority": "High",
    "statusType": "Closed",
    "status": "Closed",
    "createdTime": "2026-09-25T09:00:00.000Z",
    "closedTime": "2026-09-25T12:30:00.000Z",
    "dueDate": "2026-09-25T17:00:00.000Z",
    "assigneeId": "555",
}


def test_parse_zoho_datetime_strips_timezone():
    dt = _parse_zoho_datetime("2026-09-26T10:00:00.000Z")
    assert dt == datetime(2026, 9, 26, 10, 0, 0)
    assert dt.tzinfo is None


def test_normalize_open_ticket_computes_sla_from_due_date():
    connector = ZohoDeskConnector()
    normalized = connector.normalize([SAMPLE_TICKET_OPEN])

    ticket = normalized[0]
    assert ticket["external_id"] == "101"
    assert ticket["source_system"] == "zoho_desk"
    assert ticket["category"] == "Software"
    assert ticket["status"] == "open"
    assert ticket["closed_at"] is None
    assert ticket["sla_target_hours"] == 8.0  # 10:00 -> 18:00 due date


def test_normalize_closed_ticket_maps_status_correctly():
    connector = ZohoDeskConnector()
    normalized = connector.normalize([SAMPLE_TICKET_CLOSED])

    ticket = normalized[0]
    assert ticket["status"] == "closed"
    assert ticket["closed_at"] == datetime(2026, 9, 25, 12, 30, 0)
    assert ticket["priority"] == "High"


def test_normalize_missing_category_falls_back_to_uncategorized():
    ticket_no_category = dict(SAMPLE_TICKET_OPEN)
    del ticket_no_category["category"]

    connector = ZohoDeskConnector()
    normalized = connector.normalize([ticket_no_category])

    assert normalized[0]["category"] == "Uncategorized"


@patch("connectors.zoho_desk.requests.post")
def test_authenticate_sets_access_token(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "fake_access_token"}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    connector = ZohoDeskConnector()
    connector.authenticate()

    assert connector._access_token == "fake_access_token"
    mock_post.assert_called_once()


@patch("connectors.zoho_desk.requests.get")
def test_fetch_paginates_until_short_page(mock_get):
    full_page = [{"id": str(i), "createdTime": "2026-09-26T10:00:00.000Z"} for i in range(100)]
    short_page = [{"id": "100", "createdTime": "2026-09-26T10:00:00.000Z"}]

    first_response = MagicMock()
    first_response.json.return_value = {"data": full_page}
    first_response.raise_for_status.return_value = None

    second_response = MagicMock()
    second_response.json.return_value = {"data": short_page}
    second_response.raise_for_status.return_value = None

    mock_get.side_effect = [first_response, second_response]

    connector = ZohoDeskConnector()
    connector._access_token = "fake_access_token"
    tickets = connector.fetch()

    assert len(tickets) == 101
    assert mock_get.call_count == 2
