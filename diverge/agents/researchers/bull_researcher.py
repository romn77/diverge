from diverge.agents.base import AgentCallSpec, DivergeAgentNode
from diverge.agents.report_output import (
    BullCaseStructuredOutput,
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


class BullResearcher(DivergeAgentNode):
    name = "bull_researcher"

    def build_call(self, state) -> AgentCallSpec:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

        current_response = investment_debate_state.get(
            "current_bear_response",
            investment_debate_state.get("current_response", ""),
        )
        output_language = state.get("output_language", "en")
        language_instruction = get_language_instruction(output_language)
        style_instruction = get_research_note_style_instruction(output_language)
        trade_feedback_message = get_trade_feedback_message(state)
        evidence_rules_instruction = get_evidence_rules_instruction()
        decision_boundary_instruction = get_upstream_decision_boundary_instruction()
        stress_test_instruction = get_thesis_stress_test_instruction("bullish")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = self.memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""You are a Bull Analyst stress-testing the bullish case for the stock. Your task is to build a strong, evidence-based case emphasizing growth potential, competitive advantages, and positive market indicators while clearly acknowledging material contrary evidence. Leverage the provided research and data to address concerns and counter bearish arguments effectively.

{stress_test_instruction}
{decision_boundary_instruction}
{evidence_rules_instruction}

Key points to focus on:
- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning, addressing concerns thoroughly and showing why the bull perspective holds stronger merit.
- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points and debating effectively rather than just listing data.

Resources available:
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
Company fundamentals report: {fundamentals_report}
Conversation history of the debate: {history}
Last bear argument: {current_response}
Reflections from similar situations and lessons learned: {past_memory_str}
{trade_feedback_message}
Use this information to deliver a compelling bull argument, refute the bear's concerns, and engage in a dynamic debate that demonstrates the strengths of the bull position. You must also address reflections and learn from lessons and mistakes you made in the past.

Use the following structure for the `highlights` field in your structured response:

```json-highlights
{{
  "category": "bull_case",
  "signal": "BUY or OVERWEIGHT or HOLD or UNDERWEIGHT or SELL",
  "signal_confidence": "high or medium or low",
  "summary": "1-2 sentence executive summary of your bull case",
  "stance": "bullish",
  "contrary_evidence": ["strongest evidence against the bull case"],
  "key_arguments": [
    {{"point": "core argument title", "evidence": "supporting evidence or data"}}
  ],
  "counterpoints": ["rebuttal to bear argument 1", "rebuttal 2"],
  "evidence_blocks": [
    {{
      "claim": "bullish claim",
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
            output_schema=BullCaseStructuredOutput,
            output_key="bull_case_structured",
            metadata={
                "history": history,
                "bull_history": bull_history,
                "bear_history": investment_debate_state.get("bear_history", ""),
                "current_bear_response": investment_debate_state.get(
                    "current_bear_response", current_response
                ),
                "count": investment_debate_state["count"],
            },
        )

    def apply_response(self, state, spec, response) -> dict:
        try:
            structured = parse_structured_output(
                response.content,
                BullCaseStructuredOutput,
            )
        except Exception:
            rendered = response.content
        else:
            rendered = render_markdown_with_highlights(
                structured.report_markdown,
                structured.highlights,
            )

        argument = f"Bull Analyst: {rendered}"

        new_investment_debate_state = {
            "history": spec.metadata["history"] + "\n" + argument,
            "bull_history": spec.metadata["bull_history"] + "\n" + argument,
            "bear_history": spec.metadata["bear_history"],
            "current_response": argument,
            "current_bull_response": argument,
            "current_bear_response": spec.metadata["current_bear_response"],
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
