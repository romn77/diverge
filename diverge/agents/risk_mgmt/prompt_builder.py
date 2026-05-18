from diverge.agents.report_output import structured_agent_output_instruction
from diverge.agents.utils.agent_utils import format_untrusted_context_block


def build_risk_debator_prompt(
    *,
    posture_title: str,
    opening_role: str,
    risk_budget_instruction: str,
    decision_boundary_instruction: str,
    evidence_rules_instruction: str,
    mode_instruction: str,
    trader_decision: str,
    task_instruction: str,
    source_intro: str,
    market_research_report: str,
    sentiment_report: str,
    news_report: str,
    fundamentals_report: str,
    history: str,
    counterpart_context: str,
    trade_feedback_message: str,
    engagement_instruction: str,
    highlights_intro: str,
    category: str,
    stance_label: str,
    style_instruction: str,
    language_instruction: str,
) -> str:
    trader_decision_block = format_untrusted_context_block(
        "trader_plan",
        trader_decision,
        limit=4000,
    )
    market_report_block = format_untrusted_context_block(
        "market_research_report",
        market_research_report,
        limit=4000,
    )
    sentiment_report_block = format_untrusted_context_block(
        "sentiment_report",
        sentiment_report,
        limit=4000,
    )
    news_report_block = format_untrusted_context_block(
        "news_report",
        news_report,
        limit=4000,
    )
    fundamentals_report_block = format_untrusted_context_block(
        "fundamentals_report",
        fundamentals_report,
        limit=4000,
    )
    history_block = format_untrusted_context_block(
        "risk_debate_history",
        history,
        limit=4000,
    )
    counterpart_context_block = format_untrusted_context_block(
        "counterpart_latest_arguments",
        counterpart_context,
        limit=4000,
    )

    return f"""{opening_role}

{risk_budget_instruction}
{decision_boundary_instruction}
{evidence_rules_instruction}

{mode_instruction}

Here is the trader's decision:

{trader_decision_block}

{task_instruction}
{source_intro}

{market_report_block}

{sentiment_report_block}

{news_report_block}

{fundamentals_report_block}

{history_block}

{counterpart_context_block}
{trade_feedback_message}

{engagement_instruction}
{highlights_intro} the following structure for the `highlights` field in your structured response. Values in this example are illustrative placeholders, not defaults; choose enum values based on the actual analysis:

```json-highlights
{{
  "category": "{category}",
  "signal": "HOLD",
  "signal_confidence": "medium",
  "summary": "1-2 sentence summary of your {posture_title.lower()} risk stance",
  "stance_label": "{stance_label}",
  "core_argument": "one sentence core thesis",
  "risk_assessment": "moderate",
  "key_recommendations": ["recommendation 1", "recommendation 2"],
  "risk_budget": {{
    "max_position_size": "position size limit or unknown",
    "portfolio_exposure_impact": "expected exposure impact",
    "stop_or_invalidation": ["condition, not invented price level"],
    "liquidity_risk": "medium",
    "event_risk": ["event risk"],
    "correlation_or_factor_risk": ["factor or concentration risk"],
    "required_pm_adjustment": "WATCH"
  }},
  "evidence_blocks": [
    {{
      "claim": "risk claim",
      "evidence": "specific report-backed fact",
      "source": "analyst report or trader plan",
      "data_date": "YYYY-MM-DD or unknown",
      "confidence": "medium",
      "limitation": "missing/stale/ambiguous input, or null"
    }}
  ]
}}
```
Keep the JSON keys and enum literals in English exactly as shown, even when the rest of the report is in another language. Free-form string values should follow the report language.
{style_instruction}
{language_instruction}
{structured_agent_output_instruction()}"""
