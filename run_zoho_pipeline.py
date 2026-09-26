"""
Runs the full pipeline against your REAL Zoho Desk sandbox instead of
synthetic CSVs. Network samples still come from the synthetic
connector, since there's no real network data source yet.

Requires these in your local .env (never committed):
  ZOHO_CLIENT_ID
  ZOHO_CLIENT_SECRET
  ZOHO_REFRESH_TOKEN
  ZOHO_API_DOMAIN       (e.g. https://www.zohoapis.ae)
  ZOHO_ORG_ID
  ANTHROPIC_API_KEY     (optional — falls back to template report without it)

This script only ever reads tickets (Desk.tickets.READ scope) from
your own personal sandbox org. It has never been run against, and
must never be pointed at, Driven's real ManageEngine system.

Usage:
    python run_zoho_pipeline.py
"""

import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from connectors.zoho_desk import ZohoDeskConnector
from connectors.synthetic_network import SyntheticNetworkConnector
from engines.kpi_engine import calculate_ticket_kpis, detect_recurring_categories
from engines.network_engine import calculate_network_kpis
from ai.report_generator import generate_report
from reporting.pdf_export import export_pdf
from reporting.excel_export import export_excel
from models.schema import get_engine, init_db
from models.persistence import (
    get_or_create_synthetic_customer,
    persist_tickets,
    persist_network_samples,
    persist_kpi_snapshot,
    persist_report,
)


def main():
    now = datetime.now()
    period_label = "Zoho Desk Sandbox — Live Test"
    outdir = "output"
    os.makedirs(outdir, exist_ok=True)

    zoho = ZohoDeskConnector()
    zoho.authenticate()
    raw_tickets = zoho.fetch()
    tickets = zoho.normalize(raw_tickets)
    print(f"[connectors] zoho_desk: {len(tickets)} real tickets fetched and normalized")

    network_connector = SyntheticNetworkConnector("data/sample_network.csv")
    network_connector.authenticate()
    network_samples = network_connector.normalize(network_connector.fetch())
    print(f"[connectors] synthetic_network: {len(network_samples)} records (no real network source yet)")

    ticket_kpis = calculate_ticket_kpis(tickets, now)
    recurring = detect_recurring_categories(tickets, min_occurrences=2)  # lower threshold for a small sandbox dataset
    network_kpis = calculate_network_kpis(network_samples)
    print(f"[engines] ticket KPIs: {ticket_kpis}")
    print(f"[engines] recurring categories: {recurring}")

    ai_report = generate_report(period_label, ticket_kpis, network_kpis, recurring)
    print(f"[ai] report generated via: {ai_report.get('generated_by', 'unknown')}")
    if ai_report.get("ai_error"):
        print(f"[ai] fell back because: {ai_report['ai_error']}")
    print(f"[ai] ANTHROPIC_API_KEY present: {bool(os.environ.get('ANTHROPIC_API_KEY'))}")

    pdf_path = os.path.join(outdir, "zoho_live_report.pdf")
    excel_path = os.path.join(outdir, "zoho_live_report.xlsx")
    export_pdf(pdf_path, period_label, ticket_kpis, network_kpis, ai_report)
    export_excel(excel_path, period_label, ticket_kpis, network_kpis, ai_report)
    print(f"[reporting] wrote {pdf_path}")
    print(f"[reporting] wrote {excel_path}")

    engine = get_engine()
    init_db(engine)
    customer_id = get_or_create_synthetic_customer(engine)
    persist_tickets(engine, customer_id, tickets)
    persist_network_samples(engine, customer_id, network_samples)
    snapshot_id = persist_kpi_snapshot(engine, customer_id, period_label, ticket_kpis, network_kpis, recurring)
    persist_report(engine, customer_id, period_label, ai_report, pdf_path, excel_path, snapshot_id)
    print("[persistence] wrote to ai_it_operations.db")


if __name__ == "__main__":
    main()
