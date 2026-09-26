"""
Runs the full pipeline against a REAL ManageEngine ServiceDesk Plus
instance. Read-only end to end — see connectors/manageengine_sdp.py
for the safety notes on that.

DO NOT run this against Driven's instance (or any instance) without
explicit authorization and a least-privilege, read-only API
credential scoped only to what's needed.

Requires these in your local .env (never committed):
  SDP_CLIENT_ID
  SDP_CLIENT_SECRET
  SDP_REFRESH_TOKEN
  SDP_API_DOMAIN
  SDP_PORTAL_NAME
  ANTHROPIC_API_KEY   (optional — leave unset for the first real run so
                        no real ticket data is sent anywhere until you
                        decide that's acceptable)

The first live run against a real portal will likely need a fix to
connectors/manageengine_sdp.py's endpoint path or datetime parsing,
the same way the Zoho Desk connector needed two live-testing fixes
before it worked. Read the traceback, adjust, re-run — don't guess
blind.

Usage:
    python run_sdp_pipeline.py
"""

import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from connectors.manageengine_sdp import ManageEngineSDPConnector
from connectors.synthetic_network import SyntheticNetworkConnector
from connectors.synthetic_contracts import SyntheticContractConnector
from engines.kpi_engine import calculate_technician_performance, calculate_ticket_kpis, detect_recurring_categories
from engines.network_engine import calculate_network_kpis
from engines.cost_engine import calculate_cost_kpis
from ai.report_generator import generate_report
from reporting.pdf_export import export_pdf
from reporting.excel_export import export_excel
from models.schema import get_engine, init_db
from models.persistence import (
    get_or_create_synthetic_customer,
    persist_tickets,
    persist_network_samples,
    persist_contracts,
    persist_kpi_snapshot,
    persist_report,
)


def main():
    now = datetime.now()
    period_label = "ManageEngine SDP — Live Read-Only Test"
    outdir = "output"
    os.makedirs(outdir, exist_ok=True)

    sdp = ManageEngineSDPConnector()
    sdp.authenticate()
    raw_tickets = sdp.fetch()
    tickets = sdp.normalize(raw_tickets)
    print(f"[connectors] manageengine_sdp: {len(tickets)} real tickets fetched and normalized")

    network_connector = SyntheticNetworkConnector("data/sample_network.csv")
    network_connector.authenticate()
    network_samples = network_connector.normalize(network_connector.fetch())
    print(f"[connectors] synthetic_network: {len(network_samples)} records (no real network source yet)")

    contract_connector = SyntheticContractConnector("data/sample_contracts.csv")
    contract_connector.authenticate()
    contracts = contract_connector.normalize(contract_connector.fetch())
    print(f"[connectors] synthetic_contracts: {len(contracts)} records (no real cost source yet)")

    ticket_kpis = calculate_ticket_kpis(tickets, now)
    recurring = detect_recurring_categories(tickets, min_occurrences=2)
    network_kpis = calculate_network_kpis(network_samples)
    cost_kpis = calculate_cost_kpis(contracts, now)
    technician_performance = calculate_technician_performance(tickets, now)
    print(f"[engines] ticket KPIs: {ticket_kpis}")
    print(f"[engines] recurring categories: {recurring}")
    print(f"[engines] technician ranking (best to worst): {technician_performance.get('ranking_best_to_worst', [])}")
    print(f"[engines] excluded from ranking: {technician_performance.get('excluded_from_ranking', [])}")

    ai_report = generate_report(period_label, ticket_kpis, network_kpis, recurring, cost_kpis)
    print(f"[ai] report generated via: {ai_report.get('generated_by', 'unknown')}")
    if ai_report.get("ai_error"):
        print(f"[ai] fell back because: {ai_report['ai_error']}")
    print(f"[ai] ANTHROPIC_API_KEY present: {bool(os.environ.get('ANTHROPIC_API_KEY'))}")

    pdf_path = os.path.join(outdir, "sdp_live_report.pdf")
    excel_path = os.path.join(outdir, "sdp_live_report.xlsx")
    export_pdf(pdf_path, period_label, ticket_kpis, network_kpis, ai_report, technician_performance)
    export_excel(excel_path, period_label, ticket_kpis, network_kpis, ai_report, technician_performance)
    print(f"[reporting] wrote {pdf_path}")
    print(f"[reporting] wrote {excel_path}")

    engine = get_engine()
    init_db(engine)
    customer_id = get_or_create_synthetic_customer(engine)
    persist_tickets(engine, customer_id, tickets)
    persist_network_samples(engine, customer_id, network_samples)
    persist_contracts(engine, customer_id, contracts)
    snapshot_id = persist_kpi_snapshot(
        engine, customer_id, period_label, ticket_kpis, network_kpis, recurring, cost_kpis, technician_performance
    )
    persist_report(engine, customer_id, period_label, ai_report, pdf_path, excel_path, snapshot_id)
    print("[persistence] wrote to ai_it_operations.db")


if __name__ == "__main__":
    main()
