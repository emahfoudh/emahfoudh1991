"""
Tests for the email delivery module, entirely with mocked smtplib.
Never sends a real email, never connects to a real SMTP server -
this environment has no business emailing anyone.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("SMTP_HOST", "smtp.example.com")
os.environ.setdefault("SMTP_USERNAME", "test@example.com")
os.environ.setdefault("SMTP_PASSWORD", "test_password")
os.environ.setdefault("REPORT_RECIPIENT_EMAIL", "recipient@example.com")

from reporting.email_sender import send_report_email  # noqa: E402


@pytest.fixture
def sample_pdf(tmp_path):
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake pdf content")
    return str(pdf_path)


@patch("reporting.email_sender.smtplib.SMTP")
def test_send_report_email_logs_in_and_sends(mock_smtp_cls, sample_pdf):
    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    send_report_email(sample_pdf, "Test Subject", "Test body")

    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("test@example.com", "test_password")
    assert mock_server.sendmail.call_count == 1

    from_addr, to_addrs, message_str = mock_server.sendmail.call_args[0]
    assert from_addr == "test@example.com"
    assert to_addrs == ["recipient@example.com"]
    assert "Test Subject" in message_str


@patch("reporting.email_sender.smtplib.SMTP")
def test_send_report_email_uses_custom_from_address(mock_smtp_cls, sample_pdf):
    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    with patch.dict(os.environ, {"SMTP_FROM": "reports@example.com"}):
        send_report_email(sample_pdf, "Subject", "Body")

    from_addr, _, _ = mock_server.sendmail.call_args[0]
    assert from_addr == "reports@example.com"


def test_send_report_email_raises_on_missing_env_var(sample_pdf):
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(KeyError):
            send_report_email(sample_pdf, "Subject", "Body")


@patch("reporting.email_sender.smtplib.SMTP")
def test_send_report_email_attaches_pdf_with_correct_filename(mock_smtp_cls, sample_pdf):
    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    send_report_email(sample_pdf, "Subject", "Body")

    _, _, message_str = mock_server.sendmail.call_args[0]
    assert "report.pdf" in message_str
