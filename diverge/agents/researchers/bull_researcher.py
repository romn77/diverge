from diverge.agents.report_output import (
    BullCaseStructuredOutput,
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
from diverge.agents.utils.agent_utils import (
    get_thesis_stress_test_instruction,
)
from diverge.runtime.messages import AdkPrompt


AGENT_NAME = "bull_researcher"


def build_bull_researcher_prompt(state, memory):
    context = build_agent_prompt_context(state)
    debate_context = investment_debate_from_state(state)
    reports = upstream_reports_from_state(state)
    history = debate_context.history
    current_response = debate_context.latest_bear_argument
    stress_test_instruction = get_thesis_stress_test_instruction("bullish")

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
        "latest_bear_argument",
        current_response,
        limit=4000,
    )

    prompt = f"""You are a Bull Analyst stress-testing the bullish case for the stock. Your task is to build a strong, evidence-based case emphasizing growth potential, competitive advantages, and positive market indicators while clearly acknowledging material contrary evidence. Leverage the provided research and data to address concerns and counter bearish arguments effectively.

{stress_test_instruction}
{context.decision_boundary_instruction}
{context.evidence_rules_instruction}
{context.memory_skepticism_instruction}

Key points to focus on:
- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning, addressing concerns thoroughly and showing why the bull perspective holds stronger merit.
- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points and debating effectively rather than just listing data.

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
Last bear argument:
{current_response_block}
Reflections from similar situations and lessons learned:
{past_memory_block}
{context.trade_feedback_message}
Use this information to deliver a compelling bull argument, refute the bear's concerns, and engage in a dynamic debate that demonstrates the strengths of the bull position. You must also address reflections and learn from lessons and mistakes you made in the past.

Use the following structure for the `highlights` field in your structured response. Values in this example are illustrative placeholders, not defaults; choose enum values based on the actual analysis:

```json-highlights
{{
  "category": "bull_case",
  "signal": "HOLD",
  "signal_confidence": "medium",
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
            "bull_history": debate_context.bull_history,
            "bear_history": debate_context.bear_history,
            "current_bear_response": debate_context.current_bear_response,
            "count": debate_context.count,
        },
    )


def commit_bull_researcher_output(state, structured_payload):
    debate = state["investment_debate_state"]
    rendered = render_structured_report(
        structured_payload,
        BullCaseStructuredOutput,
    )
    argument = f"Bull Analyst: {rendered}"
    result = {
        "investment_debate_state": append_investment_argument(
            debate,
            speaker="bull",
            argument=argument,
        )
    }
    merge_structured_output(
        result,
        state,
        agent_name=AGENT_NAME,
        schema=BullCaseStructuredOutput,
        structured_payload=structured_payload,
    )
    return result


BULL_RESEARCHER_AGENT = StructuredAgentTurn(
    agent_name=AGENT_NAME,
    display_name="Bull Researcher",
    output_schema=BullCaseStructuredOutput,
    output_key="bull_case_structured",
    build_prompt=build_bull_researcher_prompt,
    commit_output=commit_bull_researcher_output,
    memory_key="bull_memory",
)
