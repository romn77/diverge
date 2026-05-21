from diverge.agents.report_output import (
    ResearchDecisionStructuredOutput,
    merge_structured_agent_output,
    render_markdown_with_highlights,
    structured_agent_output_instruction,
)
from diverge.agents.utils.agent_utils import (
    format_untrusted_context_block,
    get_evidence_rules_instruction,
    get_language_instruction,
    get_memory_skepticism_instruction,
    get_research_note_style_instruction,
    get_trade_feedback_message,
    get_upstream_decision_boundary_instruction,
)

from diverge.agents.utils.agent_utils import build_instrument_context
from diverge.runtime.messages import AdkPrompt
from diverge.runtime.structured_output import parse_structured_output


AGENT_NAME = "research_manager"


def build_research_manager_prompt(state, memory):
    instrument_context = build_instrument_context(state["company_of_interest"])
    history = state["investment_debate_state"].get("history", "")
    market_research_report = state["market_report"]
    sentiment_report = state["sentiment_report"]
    news_report = state["news_report"]
    fundamentals_report = state["fundamentals_report"]

    investment_debate_state = state["investment_debate_state"]
    output_language = state.get("output_language", "en")
    language_instruction = get_language_instruction(output_language)
    style_instruction = get_research_note_style_instruction(output_language)
    trade_feedback_message = get_trade_feedback_message(state)
    evidence_rules_instruction = get_evidence_rules_instruction()
    memory_skepticism_instruction = get_memory_skepticism_instruction()
    decision_boundary_instruction = get_upstream_decision_boundary_instruction()

    curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
    past_memories = memory.get_memories(curr_situation, n_matches=2)

    past_memory_str = ""
    for _i, rec in enumerate(past_memories, 1):
        past_memory_str += rec["recommendation"] + "\n\n"

    past_memory_block = format_untrusted_context_block(
        "past_decision_memory",
        past_memory_str,
        limit=4000,
    )
    history_block = format_untrusted_context_block(
        "investment_debate_history",
        history,
        limit=6000,
    )

    prompt = f"""As the research debate facilitator, your role is to critically evaluate this round of debate and produce a provisional research stance for the trader and Portfolio Manager: align with the bear analyst, align with the bull analyst, or recommend a neutral/hold research posture only if it is strongly justified based on the evidence.

{decision_boundary_instruction}
{evidence_rules_instruction}
{memory_skepticism_instruction}

Summarize the key points from both sides concisely, focusing on the most compelling evidence or reasoning. Your provisional recommendation must be clear and actionable for the trader, but it is not the final user-facing portfolio verdict. Do not force a directional stance when the evidence is mixed, stale, or incomplete; HOLD or a neutral posture is valid when supported by evidence quality and unresolved risks.

Additionally, develop a detailed investment plan for the trader. This should include:

Your Recommendation: A decisive stance supported by the most convincing arguments.
Rationale: An explanation of why these arguments lead to your conclusion.
Strategic Actions: Concrete steps for implementing the recommendation.
Take into account your past mistakes on similar situations. Use these insights to refine your decision-making and ensure you are learning and improving. Present your analysis conversationally, as if speaking naturally, with a structured decision block at the end.

Here are your past reflections on mistakes:
{past_memory_block}

{trade_feedback_message}

{instrument_context}

Here is the debate:
Debate History:
{history_block}

Use the following structure for the `highlights` field in your structured response. Values in this example are illustrative placeholders, not defaults; choose enum values based on the actual analysis:

```json-highlights
{{
  "category": "research_decision",
  "signal": "HOLD",
  "signal_confidence": "medium",
  "summary": "1-2 sentence executive summary of your ruling",
  "stance": "neutral",
  "decision": "HOLD",
  "aligned_with": "bull",
  "rationale": "one sentence explaining why you sided this way",
  "action_items": ["action 1", "action 2", "action 3"],
  "evidence_blocks": [
    {{
      "claim": "research synthesis claim",
      "evidence": "specific debate or analyst-report evidence",
      "source": "bull researcher, bear researcher, or analyst report",
      "data_date": "YYYY-MM-DD or unknown",
      "confidence": "medium",
      "limitation": "missing/stale/ambiguous input, or null"
    }}
  ],
  "unknowns": ["material unresolved research question"]
}}
```

Keep the JSON keys and enum literals in English exactly as shown, even when the rest of the report is in another language; free-form string values should follow the report language.

{style_instruction}
{language_instruction}
{structured_agent_output_instruction()}"""
    return (
        AdkPrompt(system_message=prompt),
        (),
        {
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_bull_response": investment_debate_state.get(
                "current_bull_response", ""
            ),
            "current_bear_response": investment_debate_state.get(
                "current_bear_response", ""
            ),
            "count": investment_debate_state["count"],
        },
    )


def build_research_manager_result(
    state,
    *,
    response_content,
    history,
    bear_history,
    bull_history,
    current_bull_response,
    current_bear_response,
    count,
    **_unused,
) -> dict:
    try:
        structured = parse_structured_output(
            response_content,
            ResearchDecisionStructuredOutput,
        )
    except Exception:
        rendered = response_content
    else:
        rendered = render_markdown_with_highlights(
            structured.report_markdown,
            structured.highlights,
        )

    new_investment_debate_state = {
        "judge_decision": rendered,
        "history": history,
        "bear_history": bear_history,
        "bull_history": bull_history,
        "current_response": rendered,
        "current_bull_response": current_bull_response,
        "current_bear_response": current_bear_response,
        "count": count,
    }

    result = {
        "investment_debate_state": new_investment_debate_state,
        "investment_plan": rendered,
    }
    if "structured" in locals():
        result["structured_agent_outputs"] = merge_structured_agent_output(
            state,
            agent_name=AGENT_NAME,
            payload=structured.model_dump(mode="json"),
        )
    return result
