"""
AI report generator.

Calls Claude with the KPI engine's *output only* (never raw records)
and returns a structured executive report. If no ANTHROPIC_API_KEY is
configured, falls back to a plain template so the rest of the
pipeline (PDF/Excel export) can still be built and tested without a
live API key — you can wire the real key in whenever you're ready.
"""

import json
import os

from ai.prompts import SYSTEM_PROMPT, build_user_prompt

REQUIRED_KEYS = {
    "executive_summary",
    "key_incidents",
    "recurring_problems",
    "risk_observations",
    "vendor_observations",
    "cost_observations",
    "recommended_actions",
    "management_attention_items",
}


def _template_fallback(
    ticket_kpis: dict, network_kpis: dict, recurring: list[dict], cost_kpis: dict | None = None
) -> dict:
    """No API key configured — produce a deterministic, non-AI report
    so the pipeline still runs end to end during setup/testing."""
    cost_kpis = cost_kpis or {}
    if ticket_kpis.get("insufficient_data"):
        summary = "Insufficient data."
    else:
        summary = (
            f"IT handled {ticket_kpis['total_tickets']} tickets this period "
            f"({ticket_kpis['open_tickets']} still open). "
            f"SLA compliance was {ticket_kpis.get('sla_compliance_pct', 'Insufficient data')}%."
        )

    cost_observations = []
    if not cost_kpis.get("insufficient_data"):
        cost_observations.append(f"Total tracked annual spend: {cost_kpis.get('total_annual_cost')}")
        for r in cost_kpis.get("contracts_renewing_soon", []):
            cost_observations.append(
                f"{r['vendor_name']} / {r['service_name']} renews in {r['days_until_renewal']} days"
            )
        for u in cost_kpis.get("underutilized_licenses", []):
            cost_observations.append(
                f"{u['vendor_name']} / {u['service_name']} at {u['utilization_pct']}% license utilization"
            )

    return {
        "executive_summary": summary,
        "key_incidents": [],
        "recurring_problems": [f"{r['category']} ({r['count']} occurrences)" for r in recurring] or ["Insufficient data"],
        "risk_observations": [f"Flagged site: {s}" for s in network_kpis.get("flagged_sites", [])] or ["Insufficient data"],
        "vendor_observations": ["Insufficient data"],
        "cost_observations": cost_observations or ["Insufficient data"],
        "recommended_actions": ["Insufficient data"],
        "management_attention_items": ["Insufficient data"],
        "generated_by": "template_fallback",
    }


def _validate_shape(report: dict) -> bool:
    return REQUIRED_KEYS.issubset(report.keys())


def generate_report(
    period_label: str,
    ticket_kpis: dict,
    network_kpis: dict,
    recurring: list[dict],
    cost_kpis: dict | None = None,
) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _template_fallback(ticket_kpis, network_kpis, recurring, cost_kpis)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(period_label, ticket_kpis, network_kpis, recurring, cost_kpis)}],
        )
        # Claude's response can include a thinking block before the text
        # block, so find the first text block rather than assuming index 0.
        text_blocks = [block.text for block in message.content if block.type == "text" and block.text.strip()]
        if not text_blocks:
            raise RuntimeError(
                f"No non-empty text block in Claude's response (stop_reason={message.stop_reason})"
            )
        raw_text = text_blocks[0].strip()
        # Models sometimes wrap JSON in markdown code fences even when told
        # not to; strip them defensively before parsing.
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
        report = json.loads(raw_text)
        if not _validate_shape(report):
            raise ValueError("AI response missing required keys; falling back to template.")
        report["generated_by"] = "claude"
        return report
    except Exception as exc:  # noqa: BLE001 - MVP: any AI failure degrades gracefully
        fallback = _template_fallback(ticket_kpis, network_kpis, recurring, cost_kpis)
        fallback["ai_error"] = str(exc)
        return fallback
