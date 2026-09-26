"""
Tests for the ManageEngine SDP connector, using mocked HTTP responses.
Never makes a real API call — this environment has no path to Driven's
real ManageEngine instance, and never should. These tests verify the
normalization logic against SDP's documented response shape; the
exact live shape (endpoint path, datetime format) is unverified until
tested against the real portal, same situation the Zoho Desk
connector was in before its two live-testing fixes.
"""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

os.environ.setdefault("SDP_CLIENT_ID", "test_client_id")
os.environ.setdefault("SDP_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("SDP_REFRESH_TOKEN", "test_refresh_token")
os.environ.setdefault("SDP_API_DOMAIN", "https://sdpondemand.manageengine.com")
os.environ.setdefault("SDP_PORTAL_NAME", "driven")

from connectors.manageengine_sdp import ManageEngineSDPConnector, _parse_sdp_datetime  # noqa: E402


SAMPLE_REQUEST_EPOCH_FORMAT = {
    "id": "1001",
    "subject": "Password reset",
    "category": {"name": "Access"},
    "priority": {"name": "Medium"},
    "status": {"name": "Open"},
    "created_time": {"value": "1735689600000"},  # 2025-01-01T00:00:00 UTC in ms
    "due_by_time": {"value": "1735776000000"},  # +24h
    "technician": {"name": "engineer_a"},
}

SAMPLE_REQUEST_CLOSED = {
    "id": "1002",
    "subject": "Laptop repair",
    "category": {"name": "Hardware"},
    "priority": {"name": "High"},
    "status": {"name": "Closed"},
    "created_time": {"value": "1735689600000"},
    "completed_time": {"value": "1735693200000"},  # +1h
    "due_by_time": {"value": "1735776000000"},
    "technician": {"name": "engineer_b"},
}


def test_parse_sdp_datetime_handles_epoch_ms_dict():
    dt = _parse_sdp_datetime({"value": "1735689600000"})
    assert dt.year == 2025 and dt.month == 1 and dt.day == 1


def test_parse_sdp_datetime_handles_iso_string_fallback():
    dt = _parse_sdp_datetime("2025-01-01T00:00:00.000Z")
    assert dt == datetime(2025, 1, 1)


def test_parse_sdp_datetime_rejects_unrecognized_shape():
    import pytest

    with pytest.raises(ValueError):
        _parse_sdp_datetime(12345)


def test_normalize_open_request_computes_sla_from_due_by_time():
    connector = ManageEngineSDPConnector()
    normalized = connector.normalize([SAMPLE_REQUEST_EPOCH_FORMAT])

    ticket = normalized[0]
    assert ticket["external_id"] == "1001"
    assert ticket["source_system"] == "manageengine_sdp"
    assert ticket["category"] == "Access"
    assert ticket["status"] == "open"
    assert ticket["closed_at"] is None
    assert ticket["sla_target_hours"] == 24.0


def test_normalize_closed_request_maps_status_and_closed_at():
    connector = ManageEngineSDPConnector()
    normalized = connector.normalize([SAMPLE_REQUEST_CLOSED])

    ticket = normalized[0]
    assert ticket["status"] == "closed"
    assert ticket["closed_at"] is not None
    assert ticket["priority"] == "High"
    assert ticket["assigned_to"] == "engineer_b"


def test_normalize_missing_category_falls_back_to_uncategorized():
    request = dict(SAMPLE_REQUEST_EPOCH_FORMAT)
    del request["category"]

    connector = ManageEngineSDPConnector()
    normalized = connector.normalize([request])

    assert normalized[0]["category"] == "Uncategorized"


@patch("connectors.manageengine_sdp.requests.post")
def test_authenticate_sets_access_token(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "fake_access_token"}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    connector = ManageEngineSDPConnector()
    connector.authenticate()

    assert connector._access_token == "fake_access_token"


@patch("connectors.manageengine_sdp.requests.get")
def test_fetch_calls_correct_url_without_portal_in_path(mock_get):
    """
    Regression test for the live 404 found during real testing: the
    portal name must NOT appear in the URL path. If this test starts
    failing because the path changed again, that's a deliberate
    decision to re-verify against a live instance, not a silent revert.
    """
    response = MagicMock()
    response.json.return_value = {"requests": []}
    response.raise_for_status.return_value = None
    mock_get.return_value = response

    connector = ManageEngineSDPConnector()
    connector._access_token = "fake_access_token"
    connector.fetch()

    called_url = mock_get.call_args[0][0]
    assert called_url == "https://sdpondemand.manageengine.com/api/v3/requests"
    assert "driven" not in called_url


@patch("connectors.manageengine_sdp.requests.get")
def test_fetch_paginates_until_short_page(mock_get):
    full_page = [{"id": str(i), "created_time": {"value": "1735689600000"}} for i in range(100)]
    short_page = [{"id": "100", "created_time": {"value": "1735689600000"}}]

    first_response = MagicMock()
    first_response.json.return_value = {"requests": full_page}
    first_response.raise_for_status.return_value = None

    second_response = MagicMock()
    second_response.json.return_value = {"requests": short_page}
    second_response.raise_for_status.return_value = None

    mock_get.side_effect = [first_response, second_response]

    connector = ManageEngineSDPConnector()
    connector._access_token = "fake_access_token"
    tickets = connector.fetch()

    assert len(tickets) == 101
    assert mock_get.call_count == 2


def test_connector_source_contains_no_write_http_calls():
    """
    Structural safety check: this connector must never call requests.post
    against the SDP API domain (only against the OAuth accounts domain
    for token refresh), and never requests.put/patch/delete at all.
    """
    import inspect

    import connectors.manageengine_sdp as module

    source = inspect.getsource(module)
    assert "requests.put(" not in source
    assert "requests.patch(" not in source
    assert "requests.delete(" not in source
    # requests.post is allowed ONLY for the OAuth token exchange
    post_call_lines = [line for line in source.splitlines() if "requests.post(" in line]
    assert len(post_call_lines) == 1
