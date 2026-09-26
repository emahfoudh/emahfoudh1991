"""
Minimal read-only API — Phase 2.

Serves the latest KPI snapshot and executive report from the local
SQLite database. Read-only on purpose: no write endpoints, no auth,
because there is no real customer or role system yet to protect.
This exists to prove "pipeline output can be served over HTTP",
which is the foundation the future dashboard will call into — it is
not itself a dashboard or a production API.
"""

from fastapi import FastAPI, HTTPException

from models.persistence import get_latest_kpi_snapshot, get_latest_report, get_or_create_synthetic_customer
from models.schema import get_engine

app = FastAPI(title="AI IT Operations API (MVP, read-only, synthetic data)")

engine = get_engine()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/kpi-snapshot/latest")
def latest_kpi_snapshot():
    customer_id = get_or_create_synthetic_customer(engine)
    snapshot = get_latest_kpi_snapshot(engine, customer_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No KPI snapshot found. Run main.py first.")
    return {
        "id": snapshot.id,
        "period_label": snapshot.period_label,
        "computed_at": snapshot.computed_at,
        "ticket_kpis": snapshot.ticket_kpis,
        "network_kpis": snapshot.network_kpis,
        "recurring_categories": snapshot.recurring_categories,
    }


@app.get("/report/latest")
def latest_report():
    customer_id = get_or_create_synthetic_customer(engine)
    report = get_latest_report(engine, customer_id)
    if report is None:
        raise HTTPException(status_code=404, detail="No report found. Run main.py first.")
    return {
        "id": report.id,
        "period_label": report.period_label,
        "generated_at": report.generated_at,
        "ai_report": report.ai_report_json,
        "pdf_path": report.pdf_path,
        "excel_path": report.excel_path,
    }
