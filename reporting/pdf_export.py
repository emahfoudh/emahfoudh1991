"""
PDF export via xhtml2pdf — styled from plain HTML/CSS, pure Python
with no native system libraries required (unlike WeasyPrint, which
needs GTK/Pango installed separately and fails hard on a stock
Windows machine). Renders the same ai_report/KPI objects Excel
export uses. xhtml2pdf's CSS support is more limited than
WeasyPrint's (no flexbox/grid), so layout here uses plain tables.
"""

from xhtml2pdf import pisa

_STYLE = """
<style>
  body { font-family: Helvetica, Arial, sans-serif; color: #1a1a1a; margin: 20px; }
  h1 { font-size: 20px; border-bottom: 2px solid #0f5c5c; padding-bottom: 8px; }
  h2 { font-size: 14px; color: #0f5c5c; margin-top: 24px; }
  table.kpi-row { width: 100%; margin: 12px 0; border-collapse: separate; border-spacing: 12px 0; }
  table.kpi-row td { border: 1px solid #ddd; border-radius: 4px; padding: 10px 16px; width: 25%; }
  .kpi-value { font-size: 20px; font-weight: bold; display: block; }
  .kpi-label { font-size: 11px; color: #666; }
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
        <table class="kpi-row">
          <tr>
            <td><span class="kpi-value">{ticket_kpis['total_tickets']}</span><span class="kpi-label">Total Tickets</span></td>
            <td><span class="kpi-value">{ticket_kpis['open_tickets']}</span><span class="kpi-label">Open</span></td>
            <td><span class="kpi-value">{ticket_kpis.get('sla_compliance_pct', '-')}%</span><span class="kpi-label">SLA Compliance</span></td>
            <td><span class="kpi-value">{ticket_kpis.get('mttr_hours', '-')}</span><span class="kpi-label">MTTR (hours)</span></td>
          </tr>
        </table>
        <table class="kpi-row">
          <tr>
            <td><span class="kpi-value">{ticket_kpis.get('closed_last_7_days', '-')}</span><span class="kpi-label">Closed This Week</span></td>
            <td><span class="kpi-value">{ticket_kpis.get('closed_last_30_days', '-')}</span><span class="kpi-label">Closed This Month</span></td>
            <td><span class="kpi-value">{ticket_kpis.get('opened_today_assigned', '-')}</span><span class="kpi-label">Assigned Today</span></td>
            <td><span class="kpi-value">{ticket_kpis.get('opened_today_unassigned', '-')}</span><span class="kpi-label">Unassigned Today</span></td>
          </tr>
        </table>
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

    with open(path, "wb") as f:
        result = pisa.CreatePDF(html, dest=f)
    if result.err:
        raise RuntimeError(f"PDF generation failed with {result.err} error(s)")
