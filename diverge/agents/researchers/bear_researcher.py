from diverge.agents.report_output import (
    BearCaseStructuredOutput,
    structured_agent_output_instruction,
)
from diverge.agents.agent_context import (
    build_agent_prompt_context,
    context_block,
    investment_debate_from_state,
    memory_recommendations_block,
    upstream_reports_from_state,
)
from diverge.agents.debate_state import append_investment_argument
from diverge.agents.structured_commit import (
    merge_structured_output,
    render_structured_report,
)
from diverge.agents.structured_turn import StructuredAgentTurn
from diverge.agents.utils.agent_utils import get_thesis_stress_test_instruction
from diverge.runtime.messages import AdkPrompt


AGENT_NAME = "bear_researcher"


def build_bear_researcher_prompt(state, memory):
    context = build_agent_prompt_context(state)
    debate_context = investment_debate_from_state(state)
    reports = upstream_reports_from_state(state)
    history = debate_context.history
    current_response = debate_context.latest_bull_argument
    stress_test_instruction = get_thesis_stress_test_instruction("bearish")

    past_memory_block = memory_recommendations_block(
        memory,
        reports.combined,
        default="",
    )
    market_report_block = reports.block(
        "market",
        label="market_research_report",
        limit=4000,
    )
    sentiment_report_block = reports.block(
        "sentiment",
        label="sentiment_report",
        limit=4000,
    )
    news_report_block = reports.block(
        "news",
        label="news_report",
        limit=4000,
    )
    fundamentals_report_block = reports.block(
        "fundamentals",
        label="fundamentals_report",
        limit=4000,
    )
    history_block = context_block(
        "investment_debate_history",
        history,
        limit=4000,
    )
    current_response_block = context_block(
        "latest_bull_argument",
        current_response,
        limit=4000,
    )

    prompt = f"""You are a Bear Analyst stress-testing the bearish case against the stock. Your goal is to present a well-reasoned argument emphasizing risks, challenges, and negative indicators while clearly acknowledging material contrary evidence. Leverage the provided research and data to highlight potential downsides and counter bullish arguments effectively.

{stress_test_instruction}
{context.decision_boundary_instruction}
{context.evidence_rules_instruction}
{context.memory_skepticism_instruction}

Key points to focus on:

- Risks and Challenges: Highlight factors like market saturation, financial instability, or macroeconomic threats that could hinder the stock's performance.
- Competitive Weaknesses: Emphasize vulnerabilities such as weaker market positioning, declining innovation, or threats from competitors.
- Negative Indicators: Use evidence from financial data, market trends, or recent adverse news to support your position.
- Bull Counterpoints: Critically analyze the bull argument with specific data and sound reasoning, exposing weaknesses or over-optimistic assumptions.
- Engagement: Present your argument in a conversational style, directly engaging with the bull analyst's points and debating effectively rather than simply listing facts.

Resources available:

Market research report:
{market_report_block}
Social media sentiment report:
{sentiment_report_block}
Latest world affairs news:
{news_report_block}
Company fundamentals report:
{fundamentals_report_block}
Conversation history of the debate:
{history_block}
Last bull argument:
{current_response_block}
Reflections from similar situations and lessons learned:
{past_memory_block}
{context.trade_feedback_message}
Use this information to deliver a compelling bear argument, refute the bull's claims, and engage in a dynamic debate that demonstrates the risks and weaknesses of investing in the stock. You must also address reflections and learn from lessons and mistakes you made in the past.

Use the following structure for the `highlights` field in your structured response. Values in this example are illustrative placeholders, not defaults; choose enum values based on the actual analysis:

```json-highlights
{{
  "category": "bear_case",
  "signal": "HOLD",
  "signal_confidence": "medium",
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
      "confidence": "medium",
      "limitation": "missing/stale/ambiguous input, or null"
    }}
  ],
  "unknowns": ["material unresolved question"]
}}
```
Keep the JSON keys and enum literals in English exactly as shown, even when the rest of the report is in another language. Free-form string values should follow the report language.
{context.style_instruction}
{context.language_instruction}
{structured_agent_output_instruction()}
"""

    return (
        AdkPrompt(system_message=prompt),
        (),
        {
            "history": history,
            "bear_history": debate_context.bear_history,
            "bull_history": debate_context.bull_history,
            "current_bull_response": debate_context.current_bull_response,
            "count": debate_context.count,
        },
    )


def commit_bear_researcher_output(state, structured_payload):
    debate = state["investment_debate_state"]
    rendered = render_structured_report(
        structured_payload,
        BearCaseStructuredOutput,
    )
    argument = f"Bear Analyst: {rendered}"
    result = {
        "investment_debate_state": append_investment_argument(
            debate,
            speaker="bear",
            argument=argument,
        )
    }
    merge_structured_output(
        result,
        state,
        agent_name=AGENT_NAME,
        schema=BearCaseStructuredOutput,
        structured_payload=structured_payload,
    )
    return result


BEAR_RESEARCHER_AGENT = StructuredAgentTurn(
    agent_name=AGENT_NAME,
    display_name="Bear Researcher",
    output_schema=BearCaseStructuredOutput,
    output_key="bear_case_structured",
    build_prompt=build_bear_researcher_prompt,
    commit_output=commit_bear_researcher_output,
    memory_key="bear_memory",
)
