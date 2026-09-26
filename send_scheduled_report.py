"""
Runs a pipeline (synthetic, Zoho sandbox, or the real SDP connector),
then emails the resulting PDF to the configured recipient. This is
the script a scheduled task (Windows Task Scheduler, cron) would call
daily or weekly.

DO NOT point REPORT_RECIPIENT_EMAIL at a real person and enable an
unattended schedule until you've tested this manually and are
confident in the report's accuracy. A wrong number reaching a COO
automatically is worse than one caught in manual review.

Requires everything main.py / run_sdp_pipeline.py / run_zoho_pipeline.py
already require, PLUS in your .env:
  SMTP_HOST
  SMTP_PORT              (defaults to 587)
  SMTP_USERNAME
  SMTP_PASSWORD
  SMTP_FROM              (defaults to SMTP_USERNAME)
  REPORT_RECIPIENT_EMAIL

For Office 365: SMTP_HOST=smtp.office365.com, SMTP_PORT=587, and an
app password or the mailbox's own password depending on your tenant's
MFA/security defaults policy - check with whoever administers Driven's
M365 tenant if a plain password is rejected.

Usage:
    python send_scheduled_report.py --pipeline synthetic
    python send_scheduled_report.py --pipeline sdp
    python send_scheduled_report.py --pipeline zoho
    python send_scheduled_report.py --pipeline sdp --dry-run   (generates the
        report and prints what WOULD be emailed, without actually sending)
"""

import argparse
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()

from reporting.email_sender import send_report_email

PIPELINE_SCRIPTS = {
    "synthetic": ("main.py", "output/executive_report.pdf"),
    "zoho": ("run_zoho_pipeline.py", "output/zoho_live_report.pdf"),
    "sdp": ("run_sdp_pipeline.py", "output/sdp_live_report.pdf"),
}


def main():
    parser = argparse.ArgumentParser(description="Run a pipeline and email the resulting report")
    parser.add_argument("--pipeline", choices=PIPELINE_SCRIPTS.keys(), required=True)
    parser.add_argument("--dry-run", action="store_true", help="Generate the report but don't send it")
    args = parser.parse_args()

    script, pdf_path = PIPELINE_SCRIPTS[args.pipeline]

    print(f"[send_scheduled_report] running {script} ...")
    result = subprocess.run([sys.executable, script], capture_output=False)
    if result.returncode != 0:
        print("[send_scheduled_report] pipeline failed, NOT sending an email.")
        sys.exit(1)

    subject = f"AI IT Operations Report — {args.pipeline} — {_today_label()}"
    body = (
        "Attached is the latest IT operations executive report.\n\n"
        "This is an automated report. Reply to this thread with questions."
    )

    if args.dry_run:
        print(f"[send_scheduled_report] DRY RUN — would email {pdf_path} with subject: {subject!r}")
        print("[send_scheduled_report] no email sent.")
        return

    print(f"[send_scheduled_report] emailing {pdf_path} ...")
    send_report_email(pdf_path, subject, body)
    print("[send_scheduled_report] email sent.")


def _today_label() -> str:
    from datetime import date

    return date.today().isoformat()


if __name__ == "__main__":
    main()
