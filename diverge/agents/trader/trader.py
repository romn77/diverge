from diverge.agents.base import AgentCallSpec, DivergeAgentNode
from diverge.agents.report_output import (
    TraderStructuredOutput,
    merge_structured_agent_output,
    render_markdown_with_highlights,
    structured_agent_output_instruction,
)
from diverge.agents.utils.agent_utils import build_instrument_context
from diverge.agents.utils.agent_utils import (
    get_evidence_rules_instruction,
    get_language_instruction,
    get_research_note_style_instruction,
    get_trader_execution_role_instruction,
    get_trade_feedback_message,
    get_upstream_decision_boundary_instruction,
)
from diverge.runtime.messages import AdkPrompt
from diverge.runtime.structured_output import parse_structured_output


class Trader(DivergeAgentNode):
    name = "trader"
    sender_name = "Trader"

    def build_call(self, state):
        company_name = state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)
        investment_plan = state["investment_plan"]
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        output_language = state.get("output_language", "en")
        language_instruction = get_language_instruction(output_language)
        style_instruction = get_research_note_style_instruction(output_language)
        trade_feedback_message = get_trade_feedback_message(state)
        evidence_rules_instruction = get_evidence_rules_instruction()
        decision_boundary_instruction = get_upstream_decision_boundary_instruction()
        execution_role_instruction = get_trader_execution_role_instruction()

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = self.memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        context = {
            "role": "user",
            "content": f"Based on a comprehensive analysis by a team of analysts, here is an investment plan tailored for {company_name}. {instrument_context} This plan incorporates insights from current technical market trends, macroeconomic indicators, and social media sentiment. Use this plan as a foundation for evaluating your next trading decision.\n\nProposed Investment Plan: {investment_plan}\n\nLeverage these insights to make an informed and strategic decision.",
        }

        system_prompt = f"""You are a trading execution planner translating the research plan into an actionable trade framework for the Portfolio Manager. Provide a provisional directional read for compatibility, but focus on execution conditions, invalidation, sizing, and risk controls. Apply lessons from past decisions to strengthen your analysis. Here are reflections from similar situations you traded in and the lessons learned: {past_memory_str}

{execution_role_instruction}
{decision_boundary_instruction}
{evidence_rules_instruction}

{trade_feedback_message}

Use the following structure for the `highlights` field in your structured response:

```json-highlights
{{
  "category": "trader",
  "signal": "BUY or OVERWEIGHT or HOLD or UNDERWEIGHT or SELL",
  "signal_confidence": "high or medium or low",
  "summary": "1-2 sentence executive summary of your trading decision",
  "stance": "bullish or neutral or bearish or mixed",
  "decision": "BUY or OVERWEIGHT or HOLD or UNDERWEIGHT or SELL",
  "entry_exit": {{
    "action": "core trading action description",
    "entry_condition": "entry or add condition",
    "exit_target": "target condition, or null/unknown if unsupported",
    "stop_loss": "stop condition, or null/unknown if unsupported",
    "invalidation": "condition that invalidates the setup",
    "re_entry": "conditions for re-entry"
  }},
  "position_sizing": "sizing guidance or unknown",
  "risk_budget": "risk budget or unknown",
  "risk_factors": ["risk 1", "risk 2"],
  "evidence_blocks": [
    {{
      "claim": "execution claim",
      "evidence": "specific report-backed fact",
      "source": "research manager plan or analyst report",
      "data_date": "YYYY-MM-DD or unknown",
      "confidence": "high or medium or low",
      "limitation": "missing/stale/ambiguous input, or null"
    }}
  ],
  "unknowns": ["missing current price, ATR, liquidity, or other execution input"]
}}
```

Keep the JSON keys and enum literals in English exactly as shown, even when the rest of the report is in another language. Free-form string values should follow the report language.

{style_instruction}
{language_instruction}
{structured_agent_output_instruction()}"""

        return AgentCallSpec(
            prompt=AdkPrompt(
                system_message=system_prompt,
                messages=(context,),
            ),
            output_schema=TraderStructuredOutput,
            output_key="trader_structured",
        )

    def apply_response(self, state, spec, response):
        try:
            structured = parse_structured_output(
                response.content,
                TraderStructuredOutput,
            )
        except Exception:
            rendered = response.content
        else:
            rendered = render_markdown_with_highlights(
                structured.report_markdown,
                structured.highlights,
            )

        result = {
            "messages": [response],
            "trader_investment_plan": rendered,
            "sender": self.sender_name,
        }
        if "structured" in locals():
            result["structured_agent_outputs"] = merge_structured_agent_output(
                state,
                agent_name=self.name,
                payload=structured.model_dump(mode="json"),
            )
        return result
