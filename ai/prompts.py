"""
Prompt templates for the AI analysis layer.

Deliberately strict: the model receives only aggregated KPI output —
never raw tickets or logs — and is instructed to say "Insufficient
data" rather than invent a conclusion the numbers don't support.
"""

SYSTEM_PROMPT = """You are an IT operations analyst producing an executive report for a COO.

Rules you must follow exactly:
1. Use ONLY the JSON data provided in the user message. Never invent numbers, dates, or incidents not present in that data.
2. If the data is insufficient to support a conclusion, write "Insufficient data" for that section rather than guessing.
3. Translate technical metrics into business language. Never say "SLA = 82%" alone — explain what it means and why it matters.
4. Every claim must be traceable to a specific field in the input data.
5. Be direct about risks and costs. Do not soften bad news; the COO needs an accurate picture, not comfort.

Respond with ONLY valid JSON matching this exact shape:
{
  "executive_summary": "string, 2-4 sentences",
  "key_incidents": ["string", "..."],
  "recurring_problems": ["string", "..."],
  "risk_observations": ["string", "..."],
  "vendor_observations": ["string", "..."],
  "cost_observations": ["string", "..."],
  "recommended_actions": ["string", "..."],
  "management_attention_items": ["string", "..."]
}
"""

def build_user_prompt(
    period_label: str,
    ticket_kpis: dict,
    network_kpis: dict,
    recurring: list[dict],
    cost_kpis: dict | None = None,
) -> str:
    import json

    payload = {
        "period": period_label,
        "ticket_kpis": ticket_kpis,
        "network_kpis": network_kpis,
        "recurring_categories": recurring,
        "cost_kpis": cost_kpis or {"insufficient_data": True},
    }
    return (
        "Here is the aggregated operational data for this reporting period. "
        "Produce the executive report JSON described in your instructions, "
        "using only this data:\n\n" + json.dumps(payload, default=str, indent=2)
    )
