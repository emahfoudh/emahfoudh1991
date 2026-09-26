"""
Email delivery for the executive report PDF — the "send it to the
COO daily/weekly" piece.

Uses plain SMTP (works with Office 365, Gmail, or any standard SMTP
provider) rather than a vendor-specific API, so it isn't locked to
one email platform. Credentials read from environment variables only.

This module only SENDS what you tell it to, to the recipient you
configure — it has no schedule of its own and no default recipient.
Wiring it to a real person's real inbox and turning on an unattended
schedule is a deliberate step, not something this code does by
itself.
"""

import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_report_email(pdf_path: str, subject: str, body_text: str) -> None:
    """
    Sends the given PDF as an attachment to the configured recipient.
    Raises if any required environment variable is missing or the
    SMTP server rejects the send — callers should not silently
    swallow a failed report delivery.
    """
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ["SMTP_USERNAME"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    from_address = os.environ.get("SMTP_FROM", smtp_username)
    to_address = os.environ["REPORT_RECIPIENT_EMAIL"]

    message = MIMEMultipart()
    message["From"] = from_address
    message["To"] = to_address
    message["Subject"] = subject
    message.attach(MIMEText(body_text, "plain"))

    with open(pdf_path, "rb") as f:
        attachment = MIMEApplication(f.read(), _subtype="pdf")
    attachment.add_header(
        "Content-Disposition", "attachment", filename=os.path.basename(pdf_path)
    )
    message.attach(attachment)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(from_address, [to_address], message.as_string())
