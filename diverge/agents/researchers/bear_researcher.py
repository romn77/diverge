from diverge.agents.base import AgentCallSpec, DivergeAgentNode
from diverge.agents.report_output import (
    BearCaseStructuredOutput,
    merge_structured_agent_output,
    render_markdown_with_highlights,
    structured_agent_output_instruction,
)
from diverge.agents.utils.agent_utils import (
    get_evidence_rules_instruction,
    get_language_instruction,
    get_research_note_style_instruction,
    get_thesis_stress_test_instruction,
    get_trade_feedback_message,
    get_upstream_decision_boundary_instruction,
)
from diverge.runtime.messages import AdkPrompt
from diverge.runtime.structured_output import parse_structured_output


class BearResearcher(DivergeAgentNode):
    name = "bear_researcher"

    def build_call(self, state) -> AgentCallSpec:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")

        current_response = investment_debate_state.get(
            "current_bull_response",
            investment_debate_state.get("current_response", ""),
        )
        output_language = state.get("output_language", "en")
        language_instruction = get_language_instruction(output_language)
        style_instruction = get_research_note_style_instruction(output_language)
        trade_feedback_message = get_trade_feedback_message(state)
        evidence_rules_instruction = get_evidence_rules_instruction()
        decision_boundary_instruction = get_upstream_decision_boundary_instruction()
        stress_test_instruction = get_thesis_stress_test_instruction("bearish")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = self.memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""You are a Bear Analyst stress-testing the bearish case against the stock. Your goal is to present a well-reasoned argument emphasizing risks, challenges, and negative indicators while clearly acknowledging material contrary evidence. Leverage the provided research and data to highlight potential downsides and counter bullish arguments effectively.

{stress_test_instruction}
{decision_boundary_instruction}
{evidence_rules_instruction}

Key points to focus on:

- Risks and Challenges: Highlight factors like market saturation, financial instability, or macroeconomic threats that could hinder the stock's performance.
- Competitive Weaknesses: Emphasize vulnerabilities such as weaker market positioning, declining innovation, or threats from competitors.
- Negative Indicators: Use evidence from financial data, market trends, or recent adverse news to support your position.
- Bull Counterpoints: Critically analyze the bull argument with specific data and sound reasoning, exposing weaknesses or over-optimistic assumptions.
- Engagement: Present your argument in a conversational style, directly engaging with the bull analyst's points and debating effectively rather than simply listing facts.

Resources available:

Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
Company fundamentals report: {fundamentals_report}
Conversation history of the debate: {history}
Last bull argument: {current_response}
Reflections from similar situations and lessons learned: {past_memory_str}
{trade_feedback_message}
Use this information to deliver a compelling bear argument, refute the bull's claims, and engage in a dynamic debate that demonstrates the risks and weaknesses of investing in the stock. You must also address reflections and learn from lessons and mistakes you made in the past.

Use the following structure for the `highlights` field in your structured response:

```json-highlights
{{
  "category": "bear_case",
  "signal": "BUY or OVERWEIGHT or HOLD or UNDERWEIGHT or SELL",
  "signal_confidence": "high or medium or low",
  "summary": "1-2 sentence executive summary of your bear case",
  "stance": "bearish",
  "contrary_evidence": ["strongest evidence against the bear case"],
  "key_arguments": [
    {{"point": "core argument title", "evidence": "supporting evidence or data"}}
  ],
  "counterpoints": ["rebuttal to bull argument 1", "rebuttal 2"],
  "evidence_blocks": [
    {{
      "claim": "bearish claim",
      "evidence": "specific report-backed fact",
      "source": "analyst report or memory source",
      "data_date": "YYYY-MM-DD or unknown",
      "confidence": "high or medium or low",
      "limitation": "missing/stale/ambiguous input, or null"
    }}
  ],
  "unknowns": ["material unresolved question"]
}}
```
Keep the JSON keys and enum literals in English exactly as shown, even when the rest of the report is in another language. Free-form string values should follow the report language.
{style_instruction}
{language_instruction}
{structured_agent_output_instruction()}
"""

        return AgentCallSpec(
            prompt=AdkPrompt(system_message=prompt),
            output_schema=BearCaseStructuredOutput,
            output_key="bear_case_structured",
            metadata={
                "history": history,
                "bear_history": bear_history,
                "bull_history": investment_debate_state.get("bull_history", ""),
                "current_bull_response": investment_debate_state.get(
                    "current_bull_response", current_response
                ),
                "count": investment_debate_state["count"],
            },
        )

    def apply_response(self, state, spec, response) -> dict:
        try:
            structured = parse_structured_output(
                response.content,
                BearCaseStructuredOutput,
            )
        except Exception:
            rendered = response.content
        else:
            rendered = render_markdown_with_highlights(
                structured.report_markdown,
                structured.highlights,
            )

        argument = f"Bear Analyst: {rendered}"

        new_investment_debate_state = {
            "history": spec.metadata["history"] + "\n" + argument,
            "bear_history": spec.metadata["bear_history"] + "\n" + argument,
            "bull_history": spec.metadata["bull_history"],
            "current_response": argument,
            "current_bull_response": spec.metadata["current_bull_response"],
            "current_bear_response": argument,
            "count": spec.metadata["count"] + 1,
        }

        result = {"investment_debate_state": new_investment_debate_state}
        if "structured" in locals():
            result["structured_agent_outputs"] = merge_structured_agent_output(
                state,
                agent_name=self.name,
                payload=structured.model_dump(mode="json"),
            )
        return result
