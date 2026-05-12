from diverge.agents.base import DivergeAgentNode
from diverge.agents.utils.agent_utils import (
    get_evidence_rules_instruction,
    get_language_instruction,
    get_risk_budget_role_instruction,
    get_research_note_style_instruction,
    get_trade_feedback_message,
    get_upstream_decision_boundary_instruction,
)
from diverge.agents.risk_mgmt.debate_phase import (
    REBUTTAL_MODE,
    get_risk_debate_mode,
)
from diverge.runtime.messages import AdkPrompt


class NeutralDebator(DivergeAgentNode):
    name = "neutral_analyst"

    def run(self, state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response = risk_debate_state.get(
            "current_aggressive_response", ""
        )
        current_conservative_response = risk_debate_state.get(
            "current_conservative_response", ""
        )

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]
        output_language = state.get("output_language", "en")
        language_instruction = get_language_instruction(output_language)
        style_instruction = get_research_note_style_instruction(output_language)
        trade_feedback_message = get_trade_feedback_message(state)
        evidence_rules_instruction = get_evidence_rules_instruction()
        decision_boundary_instruction = get_upstream_decision_boundary_instruction()
        risk_budget_instruction = get_risk_budget_role_instruction("neutral")
        debate_mode = get_risk_debate_mode(risk_debate_state.get("count", 0))

        if debate_mode == REBUTTAL_MODE:
            mode_instruction = """Debate mode: rebuttal
This is a rebuttal round. Respond directly to the latest aggressive and conservative arguments. Challenge where either side becomes too extreme and defend a balanced risk posture with specific evidence."""
            task_instruction = """Your task is to challenge both the Aggressive and Conservative Analysts, pointing out where each perspective may be overly optimistic or overly cautious."""
            engagement_instruction = """Engage actively by analyzing both sides critically, addressing weaknesses in the aggressive and conservative arguments to advocate for a more balanced approach. Challenge each of their points to illustrate why a moderate risk strategy might offer the best of both worlds, providing growth potential while safeguarding against extreme volatility. Focus on debating rather than simply presenting data, aiming to show that a balanced view can lead to the most reliable outcomes."""
        else:
            mode_instruction = """Debate mode: thesis
This is the opening cycle of the risk debate. Lead with your own neutral thesis on the trader's plan, balancing upside and downside while proposing a moderate execution path. If earlier comments exist, you may reference them briefly, but do not structure the response as a point-by-point rebuttal and do not mention missing counterpart arguments."""
            task_instruction = """Your task is to present a standalone neutral risk thesis for the trader's decision, balancing upside participation against downside protection and proposing a moderate execution path."""
            engagement_instruction = """Focus on building your own balanced case in a conversational voice. Explain how you would combine participation and protection, and avoid meta commentary about whether counterpart arguments are available."""

        if debate_mode == REBUTTAL_MODE:
            counterpart_context = (
                f"Here is the last response from the aggressive analyst: {current_aggressive_response or 'None yet.'} "
                f"Here is the last response from the conservative analyst: {current_conservative_response or 'None yet.'}."
            )
        else:
            parts = []
            if current_aggressive_response:
                parts.append(
                    f"Here is the last response from the aggressive analyst: {current_aggressive_response}"
                )
            if current_conservative_response:
                parts.append(
                    f"Here is the last response from the conservative analyst: {current_conservative_response}"
                )
            counterpart_context = " ".join(parts)

        prompt = f"""As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing both the potential benefits and risks of the trader's decision or plan. You prioritize a well-rounded approach, evaluating the upsides and downsides while factoring in broader market trends, potential economic shifts, and diversification strategies.

{risk_budget_instruction}
{decision_boundary_instruction}
{evidence_rules_instruction}

{mode_instruction}

Here is the trader's decision:

{trader_decision}

{task_instruction}
Use insights from the following data sources to support a moderate, sustainable strategy to adjust the trader's decision:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} {counterpart_context}
{trade_feedback_message}

{engagement_instruction}
Output conversationally, then append a structured highlights block as shown below.

After your complete argument, append a structured highlights block:

```json-highlights
{{
  "category": "risk_neutral",
  "signal": "BUY or OVERWEIGHT or HOLD or UNDERWEIGHT or SELL",
  "signal_confidence": "high or medium or low",
  "summary": "1-2 sentence summary of your neutral risk stance",
  "stance_label": "Neutral",
  "core_argument": "one sentence core thesis",
  "risk_assessment": "high or moderate or low",
  "key_recommendations": ["recommendation 1", "recommendation 2"],
  "risk_budget": {{
    "max_position_size": "position size limit or unknown",
    "portfolio_exposure_impact": "expected exposure impact",
    "stop_or_invalidation": ["condition, not invented price level"],
    "liquidity_risk": "low or medium or high or unknown",
    "event_risk": ["event risk"],
    "correlation_or_factor_risk": ["factor or concentration risk"],
    "required_pm_adjustment": "ADD or MAINTAIN or TRIM or WATCH or AVOID"
  }},
  "evidence_blocks": [
    {{
      "claim": "risk claim",
      "evidence": "specific report-backed fact",
      "source": "analyst report or trader plan",
      "data_date": "YYYY-MM-DD or unknown",
      "confidence": "high or medium or low",
      "limitation": "missing/stale/ambiguous input, or null"
    }}
  ]
}}
```

Keep the `json-highlights` fence, JSON keys, and enum literals in English exactly as shown, even when the rest of the report is in another language. Free-form string values should follow the report language.

{style_instruction}
{language_instruction}"""

        response = self.llm.invoke(AdkPrompt(system_message=prompt))

        argument = f"Neutral Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": risk_debate_state.get(
                "current_conservative_response", ""
            ),
            "current_neutral_response": argument,
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}


def create_neutral_debator(llm):
    return NeutralDebator(llm)
