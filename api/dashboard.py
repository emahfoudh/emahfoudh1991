"""
Minimal read-only dashboard — Phase 4.

Renders the latest KPI snapshot + AI report as a single HTML page.
No JavaScript, no build step, no auth — this is the smallest possible
proof that the persisted pipeline output can be viewed as a page
rather than raw JSON. A real dashboard (drill-down, history, live
refresh) is designed for later, not built now, per the MVP scope.
"""

from html import escape


def _kpi_tile(value, label) -> str:
    return f"""
    <div class="tile">
      <div class="tile-value">{escape(str(value))}</div>
      <div class="tile-label">{escape(label)}</div>
    </div>
    """


def _list_section(title: str, items: list[str]) -> str:
    if not items:
        items_html = "<p class='muted'>Insufficient data</p>"
    else:
        items_html = "<ul>" + "".join(f"<li>{escape(str(i))}</li>" for i in items) + "</ul>"
    return f"<h2>{escape(title)}</h2>{items_html}"


_STYLE = """
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif;
         max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.5; }
  h1 { border-bottom: 2px solid #0f5c5c; padding-bottom: 8px; }
  h2 { color: #0f5c5c; margin-top: 28px; font-size: 1.1em; }
  .meta { color: #888; font-size: 0.9em; margin-bottom: 20px; }
  .tiles { display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0; }
  .tile { border: 1px solid #ccc; border-radius: 8px; padding: 12px 20px; min-width: 100px; }
  .tile-value { font-size: 1.6em; font-weight: bold; }
  .tile-label { font-size: 0.8em; color: #888; }
  ul { padding-left: 20px; }
  li { margin-bottom: 4px; }
  .muted { color: #888; font-style: italic; }
  .empty { text-align: center; margin-top: 80px; color: #888; }
  a.button { display: inline-block; margin-top: 24px; padding: 8px 16px;
             border: 1px solid #0f5c5c; border-radius: 6px; color: #0f5c5c;
             text-decoration: none; }
  table.tech-table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 0.85em; }
  table.tech-table th, table.tech-table td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
  table.tech-table th { background: rgba(15,92,92,0.1); }
</style>
"""


def _technician_table_html(technician_performance: dict) -> str:
    if not technician_performance or technician_performance.get("insufficient_data"):
        return "<p class='muted'>Insufficient data</p>"

    by_technician = technician_performance.get("by_technician", {})
    ranking = technician_performance.get("ranking_best_to_worst", [])
    excluded = set(technician_performance.get("excluded_from_ranking", []))
    ordered = ranking + [t for t in by_technician if t in excluded]

    rows = ""
    for rank, tech in enumerate(ordered, start=1):
        perf = by_technician[tech]
        rank_label = str(rank) if tech not in excluded else "—"
        rows += f"""
        <tr>
          <td>{escape(rank_label)}</td>
          <td>{escape(tech)}</td>
          <td>{perf['total_tickets']}</td>
          <td>{perf['closed_tickets']}</td>
          <td>{escape(str(perf.get('sla_compliance_pct', '-')))}</td>
          <td>{escape(str(perf.get('mttr_hours', '-')))}</td>
        </tr>
        """

    excluded_note = (
        "<p class='muted' style='font-size:0.8em;'>Rows marked \"—\" are excluded from ranking "
        "(unassigned, or too few closed tickets for a fair comparison).</p>"
        if excluded
        else ""
    )

    return f"""
    <table class="tech-table">
      <tr><th>Rank</th><th>Technician</th><th>Total</th><th>Closed</th><th>SLA %</th><th>MTTR (hrs)</th></tr>
      {rows}
    </table>
    {excluded_note}
    """


def render_empty_state() -> str:
    return f"""
    <html><head><title>AI IT Operations</title>{_STYLE}</head><body>
      <div class="empty">
        <h1>No report yet</h1>
        <p>Run <code>python main.py</code> (synthetic data) or
        <code>python run_zoho_pipeline.py</code> (your Zoho sandbox)
        to generate the first report.</p>
      </div>
    </body></html>
    """


def render_dashboard(snapshot, report) -> str:
    ticket_kpis = snapshot.ticket_kpis or {}
    network_kpis = snapshot.network_kpis or {}
    cost_kpis = getattr(snapshot, "cost_kpis", None) or {}
    technician_performance = getattr(snapshot, "technician_performance", None) or {}
    ai_report = report.ai_report_json or {} if report else {}

    tiles = []
    if not ticket_kpis.get("insufficient_data"):
        tiles += [
            _kpi_tile(ticket_kpis.get("total_tickets", "-"), "Total Tickets"),
            _kpi_tile(ticket_kpis.get("open_tickets", "-"), "Open"),
            _kpi_tile(f"{ticket_kpis.get('sla_compliance_pct', '-')}%", "SLA Compliance"),
            _kpi_tile(ticket_kpis.get("mttr_hours", "-"), "MTTR (hrs)"),
            _kpi_tile(len(network_kpis.get("flagged_sites", [])), "Sites Flagged"),
            _kpi_tile(ticket_kpis.get("closed_last_7_days", "-"), "Closed This Week"),
            _kpi_tile(ticket_kpis.get("closed_last_30_days", "-"), "Closed This Month"),
            _kpi_tile(ticket_kpis.get("opened_today_assigned", "-"), "Assigned Today"),
            _kpi_tile(ticket_kpis.get("opened_today_unassigned", "-"), "Unassigned Today"),
        ]
    if cost_kpis and not cost_kpis.get("insufficient_data"):
        tiles += [
            _kpi_tile(f"{cost_kpis.get('total_annual_cost', 0):,}", "Annual Spend Tracked"),
            _kpi_tile(len(cost_kpis.get("contracts_renewing_soon", [])), "Renewals Due Soon"),
        ]
    tiles_html = "<div class='tiles'>" + "".join(tiles) + "</div>" if tiles else ""

    return f"""
    <html><head><title>AI IT Operations Dashboard</title>{_STYLE}</head><body>
      <h1>AI IT Operations — {escape(snapshot.period_label)}</h1>
      <div class="meta">Computed {snapshot.computed_at} · Report generated via {escape(ai_report.get('generated_by', 'unknown'))}</div>

      {tiles_html}

      <h2>Technician Performance</h2>
      {_technician_table_html(technician_performance)}

      <h2>Executive Summary</h2>
      <p>{escape(ai_report.get('executive_summary', 'Insufficient data'))}</p>

      {_list_section("Recurring Problems", ai_report.get('recurring_problems', []))}
      {_list_section("Risk Observations", ai_report.get('risk_observations', []))}
      {_list_section("Vendor Observations", ai_report.get('vendor_observations', []))}
      {_list_section("Cost Observations", ai_report.get('cost_observations', []))}
      {_list_section("Recommended Actions", ai_report.get('recommended_actions', []))}
      {_list_section("Management Attention Items", ai_report.get('management_attention_items', []))}

      <a class="button" href="/report/latest">View raw JSON</a>
    </body></html>
    """
