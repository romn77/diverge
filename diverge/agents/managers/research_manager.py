from diverge.agents.report_output import (
    ResearchDecisionStructuredOutput,
    structured_agent_output_instruction,
)
from diverge.agents.agent_context import (
    build_agent_prompt_context,
    context_block,
    investment_debate_from_state,
    memory_recommendations_block,
    upstream_reports_from_state,
)
from diverge.agents.debate_state import record_research_decision
from diverge.agents.structured_commit import (
    merge_structured_output,
    render_structured_report,
)
from diverge.agents.structured_turn import StructuredAgentTurn
from diverge.runtime.messages import AdkPrompt


AGENT_NAME = "research_manager"


def build_research_manager_prompt(state, memory):
    context = build_agent_prompt_context(state)
    debate_context = investment_debate_from_state(state)
    reports = upstream_reports_from_state(state)
    past_memory_block = memory_recommendations_block(
        memory,
        reports.combined,
        default="",
        limit=4000,
    )
    history_block = context_block(
        "investment_debate_history",
        debate_context.history,
        limit=6000,
    )

    prompt = f"""As the research debate facilitator, your role is to critically evaluate this round of debate and produce a provisional research stance for the trader and Portfolio Manager: align with the bear analyst, align with the bull analyst, or recommend a neutral/hold research posture only if it is strongly justified based on the evidence.

{context.decision_boundary_instruction}
{context.evidence_rules_instruction}
{context.memory_skepticism_instruction}

Summarize the key points from both sides concisely, focusing on the most compelling evidence or reasoning. Your provisional recommendation must be clear and actionable for the trader, but it is not the final user-facing portfolio verdict. Do not force a directional stance when the evidence is mixed, stale, or incomplete; HOLD or a neutral posture is valid when supported by evidence quality and unresolved risks.

Additionally, develop a detailed investment plan for the trader. This should include:

Your Recommendation: A decisive stance supported by the most convincing arguments.
Rationale: An explanation of why these arguments lead to your conclusion.
Strategic Actions: Concrete steps for implementing the recommendation.
Take into account your past mistakes on similar situations. Use these insights to refine your decision-making and ensure you are learning and improving. Present your analysis conversationally, as if speaking naturally, with a structured decision block at the end.

Here are your past reflections on mistakes:
{past_memory_block}

{context.trade_feedback_message}

{context.instrument_context}

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

{context.style_instruction}
{context.language_instruction}
{structured_agent_output_instruction()}"""
    return (
        AdkPrompt(system_message=prompt),
        (),
        debate_context.metadata(),
    )


def commit_research_manager_output(state, structured_payload):
    debate = state["investment_debate_state"]
    rendered = render_structured_report(
        structured_payload,
        ResearchDecisionStructuredOutput,
    )
    result = {
        "investment_debate_state": record_research_decision(
            debate,
            decision=rendered,
        ),
        "investment_plan": rendered,
    }
    merge_structured_output(
        result,
        state,
        agent_name=AGENT_NAME,
        schema=ResearchDecisionStructuredOutput,
        structured_payload=structured_payload,
    )
    return result


RESEARCH_MANAGER_AGENT = StructuredAgentTurn(
    agent_name=AGENT_NAME,
    display_name="Research Manager",
    output_schema=ResearchDecisionStructuredOutput,
    output_key="research_decision_structured",
    build_prompt=build_research_manager_prompt,
    commit_output=commit_research_manager_output,
    memory_key="invest_judge_memory",
)
