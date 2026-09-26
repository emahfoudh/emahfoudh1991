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


def _template_fallback(ticket_kpis: dict, network_kpis: dict, recurring: list[dict]) -> dict:
    """No API key configured — produce a deterministic, non-AI report
    so the pipeline still runs end to end during setup/testing."""
    if ticket_kpis.get("insufficient_data"):
        summary = "Insufficient data."
    else:
        summary = (
            f"IT handled {ticket_kpis['total_tickets']} tickets this period "
            f"({ticket_kpis['open_tickets']} still open). "
            f"SLA compliance was {ticket_kpis.get('sla_compliance_pct', 'Insufficient data')}%."
        )

    return {
        "executive_summary": summary,
        "key_incidents": [],
        "recurring_problems": [f"{r['category']} ({r['count']} occurrences)" for r in recurring] or ["Insufficient data"],
        "risk_observations": [f"Flagged site: {s}" for s in network_kpis.get("flagged_sites", [])] or ["Insufficient data"],
        "vendor_observations": ["Insufficient data"],
        "cost_observations": ["Insufficient data"],
        "recommended_actions": ["Insufficient data"],
        "management_attention_items": ["Insufficient data"],
        "generated_by": "template_fallback",
    }


def _validate_shape(report: dict) -> bool:
    return REQUIRED_KEYS.issubset(report.keys())


def generate_report(period_label: str, ticket_kpis: dict, network_kpis: dict, recurring: list[dict]) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _template_fallback(ticket_kpis, network_kpis, recurring)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(period_label, ticket_kpis, network_kpis, recurring)}],
        )
        # Claude's response can include a thinking block before the text
        # block, so find the first text block rather than assuming index 0.
        text_blocks = [block.text for block in message.content if block.type == "text"]
        if not text_blocks:
            raise RuntimeError("No text block in Claude's response")
        report = json.loads(text_blocks[0])
        if not _validate_shape(report):
            raise ValueError("AI response missing required keys; falling back to template.")
        report["generated_by"] = "claude"
        return report
    except Exception as exc:  # noqa: BLE001 - MVP: any AI failure degrades gracefully
        fallback = _template_fallback(ticket_kpis, network_kpis, recurring)
        fallback["ai_error"] = str(exc)
        return fallback
