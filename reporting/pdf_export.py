"""
PDF export via WeasyPrint — styled from plain HTML/CSS, which is far
easier to make look "executive" than drawing a PDF by hand with
reportlab. Renders the same ai_report/KPI objects Excel export uses.
"""

from weasyprint import HTML

_STYLE = """
<style>
  body { font-family: Helvetica, Arial, sans-serif; color: #1a1a1a; margin: 40px; }
  h1 { font-size: 20px; border-bottom: 2px solid #0f5c5c; padding-bottom: 8px; }
  h2 { font-size: 14px; color: #0f5c5c; margin-top: 24px; }
  .kpi-row { display: flex; gap: 24px; margin: 12px 0; }
  .kpi { border: 1px solid #ddd; border-radius: 6px; padding: 10px 16px; }
  .kpi .value { font-size: 20px; font-weight: bold; }
  .kpi .label { font-size: 11px; color: #666; }
  ul { margin: 4px 0 12px 20px; padding: 0; font-size: 12px; }
  li { margin-bottom: 4px; }
  p { font-size: 12px; }
</style>
"""


def _list_html(items: list[str]) -> str:
    if not items:
        return "<p>Insufficient data</p>"
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def export_pdf(path: str, period_label: str, ticket_kpis: dict, network_kpis: dict, ai_report: dict) -> None:
    kpi_html = ""
    if not ticket_kpis.get("insufficient_data"):
        kpi_html = f"""
        <div class="kpi-row">
          <div class="kpi"><div class="value">{ticket_kpis['total_tickets']}</div><div class="label">Total Tickets</div></div>
          <div class="kpi"><div class="value">{ticket_kpis['open_tickets']}</div><div class="label">Open</div></div>
          <div class="kpi"><div class="value">{ticket_kpis.get('sla_compliance_pct', '-')}%</div><div class="label">SLA Compliance</div></div>
          <div class="kpi"><div class="value">{ticket_kpis.get('mttr_hours', '-')}</div><div class="label">MTTR (hours)</div></div>
        </div>
        """

    flagged = network_kpis.get("flagged_sites", [])
    network_html = f"<p>{len(flagged)} site(s) flagged for bandwidth/latency/uptime issues: {', '.join(flagged) or 'none'}.</p>"

    html = f"""
    <html><head>{_STYLE}</head><body>
      <h1>AI IT Operations — Executive Report ({period_label})</h1>
      <h2>Executive Summary</h2>
      <p>{ai_report.get('executive_summary', 'Insufficient data')}</p>
      {kpi_html}
      <h2>Network / Infrastructure</h2>
      {network_html}
      <h2>Recurring Problems</h2>
      {_list_html(ai_report.get('recurring_problems', []))}
      <h2>Risk Observations</h2>
      {_list_html(ai_report.get('risk_observations', []))}
      <h2>Vendor Observations</h2>
      {_list_html(ai_report.get('vendor_observations', []))}
      <h2>Cost Observations</h2>
      {_list_html(ai_report.get('cost_observations', []))}
      <h2>Recommended Actions</h2>
      {_list_html(ai_report.get('recommended_actions', []))}
      <h2>Management Attention Items</h2>
      {_list_html(ai_report.get('management_attention_items', []))}
    </body></html>
    """
    HTML(string=html).write_pdf(path)
