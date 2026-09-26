"""
AI IT Operations — MVP pipeline entrypoint.

Runs the full loop end to end on synthetic data:

  synthetic CSVs -> connectors -> KPI engines -> AI report -> PDF/Excel

Usage:
    python main.py
    python main.py --tickets data/sample_tickets.csv --network data/sample_network.csv --outdir output

If data/sample_tickets.csv or data/sample_network.csv don't exist yet,
generate them first with:
    python data/generate_synthetic_data.py
"""

import argparse
import os
from datetime import datetime

from connectors.synthetic_tickets import SyntheticTicketConnector
from connectors.synthetic_network import SyntheticNetworkConnector
from engines.kpi_engine import calculate_ticket_kpis, detect_recurring_categories
from engines.network_engine import calculate_network_kpis
from ai.report_generator import generate_report
from reporting.pdf_export import export_pdf
from reporting.excel_export import export_excel


def run_pipeline(tickets_csv: str, network_csv: str, outdir: str, period_label: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    now = datetime.now()

    ticket_connector = SyntheticTicketConnector(tickets_csv)
    ticket_connector.authenticate()
    raw_tickets = ticket_connector.fetch()
    tickets = ticket_connector.normalize(raw_tickets)
    print(f"[connectors] {ticket_connector.name}: {len(tickets)} records normalized")

    network_connector = SyntheticNetworkConnector(network_csv)
    network_connector.authenticate()
    raw_network = network_connector.fetch()
    network_samples = network_connector.normalize(raw_network)
    print(f"[connectors] {network_connector.name}: {len(network_samples)} records normalized")

    ticket_kpis = calculate_ticket_kpis(tickets, now)
    recurring = detect_recurring_categories(tickets)
    network_kpis = calculate_network_kpis(network_samples)
    print(f"[engines] ticket KPIs computed, {len(recurring)} recurring categories flagged")
    print(f"[engines] network KPIs computed, {len(network_kpis.get('flagged_sites', []))} sites flagged")

    ai_report = generate_report(period_label, ticket_kpis, network_kpis, recurring)
    print(f"[ai] report generated via: {ai_report.get('generated_by', 'unknown')}")

    pdf_path = os.path.join(outdir, "executive_report.pdf")
    excel_path = os.path.join(outdir, "executive_report.xlsx")
    export_pdf(pdf_path, period_label, ticket_kpis, network_kpis, ai_report)
    export_excel(excel_path, period_label, ticket_kpis, network_kpis, ai_report)
    print(f"[reporting] wrote {pdf_path}")
    print(f"[reporting] wrote {excel_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI IT Operations MVP pipeline")
    parser.add_argument("--tickets", default="data/sample_tickets.csv")
    parser.add_argument("--network", default="data/sample_network.csv")
    parser.add_argument("--outdir", default="output")
    parser.add_argument("--period", default="Synthetic Demo Period")
    args = parser.parse_args()

    run_pipeline(args.tickets, args.network, args.outdir, args.period)
