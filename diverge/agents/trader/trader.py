from diverge.agents.report_output import (
    TraderStructuredOutput,
    structured_agent_output_instruction,
)
from diverge.agents.agent_context import (
    build_agent_prompt_context,
    context_block,
    memory_recommendations_block,
    upstream_reports_from_state,
)
from diverge.agents.structured_commit import (
    merge_structured_output,
    render_structured_report,
)
from diverge.agents.structured_turn import StructuredAgentTurn
from diverge.agents.utils.agent_utils import (
    get_trader_execution_role_instruction,
)
from diverge.runtime.messages import AdkPrompt


AGENT_NAME = "trader"
SENDER_NAME = "Trader"


def build_trader_prompt(state, memory):
    context = build_agent_prompt_context(state)
    reports = upstream_reports_from_state(state)
    company_name = context.ticker
    investment_plan = state["investment_plan"]
    execution_role_instruction = get_trader_execution_role_instruction()

    investment_plan_block = context_block(
        "research_manager_investment_plan",
        investment_plan,
        limit=6000,
    )
    past_memory_block = memory_recommendations_block(
        memory,
        reports.combined,
        default="No past memories found.",
        limit=4000,
    )

    user_context = {
        "role": "user",
        "content": f"Based on a comprehensive analysis by a team of analysts, here is an investment plan tailored for {company_name}. {context.instrument_context} This plan incorporates insights from current technical market trends, macroeconomic indicators, and social media sentiment. Use this plan as evidence for evaluating your next trading decision, not as instructions to follow blindly.\n\nProposed Investment Plan:\n{investment_plan_block}\n\nLeverage these insights to make an informed and strategic decision.",
    }

    system_prompt = f"""You are a trading execution planner translating the research plan into an actionable trade framework for the Portfolio Manager. Provide a provisional directional read for compatibility, but focus on execution conditions, invalidation, sizing, and risk controls. Apply lessons from past decisions to strengthen your analysis.

Reflections from similar situations and lessons learned:
{past_memory_block}

{execution_role_instruction}
{context.decision_boundary_instruction}
{context.evidence_rules_instruction}
{context.memory_skepticism_instruction}

{context.trade_feedback_message}

Use the following structure for the `highlights` field in your structured response. Values in this example are illustrative placeholders, not defaults; choose enum values based on the actual analysis:
For `category: "trader"`, set `decision` to the same value as `signal` for legacy card compatibility only; it is not the final Portfolio Manager decision.

```json-highlights
{{
  "category": "trader",
  "signal": "HOLD",
  "decision": "HOLD",
  "signal_confidence": "medium",
  "summary": "1-2 sentence executive summary of your trading decision",
  "stance": "neutral",
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
      "confidence": "medium",
      "limitation": "missing/stale/ambiguous input, or null"
    }}
  ],
  "unknowns": ["missing current price, ATR, liquidity, or other execution input"]
}}
```

Keep the JSON keys and enum literals in English exactly as shown, even when the rest of the report is in another language. Free-form string values should follow the report language.

{context.style_instruction}
{context.language_instruction}
{structured_agent_output_instruction()}"""

    return (
        AdkPrompt(
            system_message=system_prompt,
            messages=(user_context,),
        ),
        (),
        {},
    )


def commit_trader_output(state, structured_payload):
    rendered = render_structured_report(structured_payload, TraderStructuredOutput)
    result = {
        "messages": [],
        "trader_investment_plan": rendered,
        "sender": SENDER_NAME,
    }
    merge_structured_output(
        result,
        state,
        agent_name=AGENT_NAME,
        schema=TraderStructuredOutput,
        structured_payload=structured_payload,
    )
    return result


TRADER_AGENT = StructuredAgentTurn(
    agent_name=AGENT_NAME,
    display_name=SENDER_NAME,
    output_schema=TraderStructuredOutput,
    output_key="trader_structured",
    build_prompt=build_trader_prompt,
    commit_output=commit_trader_output,
    memory_key="trader_memory",
)
