from typing import Any

from diverge.agents.debate_state import record_portfolio_decision
from diverge.agents.managers.portfolio_output import (
    PortfolioManagerStructuredOutput,
    format_json_block,
    is_transient_portfolio_llm_error,
    portfolio_structured_output_warning,
    portfolio_transient_llm_warning,
    render_structured_portfolio_decision,
    structured_fallback_from_invalid_response,
    structured_fallback_from_transient_error,
)
from diverge.agents.agent_context import (
    build_agent_prompt_context,
    context_block,
    memory_recommendations_block,
    risk_debate_from_state,
    upstream_reports_from_state,
)
from diverge.agents.utils.agent_utils import (
    build_instrument_context,
)
from diverge.agents.structured_turn import StructuredAgentTurn
from diverge.runtime.structured_output import parse_structured_output


def _empty_portfolio_context(output_language: str | None) -> str:
    if (output_language or "en").lower() == "cn":
        return "当前持仓参考：\n- 未提供该用户的已跟踪持仓。"
    return "Current portfolio reference:\n- No tracked holdings were provided for this user."


def _format_opportunity_context(context: object, output_language: str) -> str:
    if not isinstance(context, dict) or not context:
        return ""
    trigger = context.get("trigger") or context.get("source") or "opportunity_radar"
    theme_name = context.get("theme_name") or context.get("theme_id") or "unknown"
    candidate_type = context.get("candidate_type") or "unknown"
    backtest = (
        context.get("backtest_summary")
        if isinstance(context.get("backtest_summary"), dict)
        else {}
    )
    sample_size = backtest.get("sample_size") if isinstance(backtest, dict) else None
    holding_periods = (
        backtest.get("holding_periods") if isinstance(backtest, dict) else None
    )
    if sample_size:
        historical = f"Historical signal sample size: {sample_size}; holding-period metrics: {holding_periods}."
    else:
        historical = "Historical validation is unavailable or sample size is insufficient. Do not invent win rate or returns."
    if output_language == "cn":
        return (
            "Opportunity Radar context:\n"
            f"- 机会来源: {trigger}\n"
            f"- 主题: {theme_name}\n"
            f"- 候选类型: {candidate_type}\n"
            f"- 历史验证: {historical}\n"
            "Use this only as upstream evidence. The DecisionCard remains your final ruling."
        )
    return (
        "Opportunity Radar context:\n"
        f"- Trigger: {trigger}\n"
        f"- Theme: {theme_name}\n"
        f"- Candidate type: {candidate_type}\n"
        f"- Validation: {historical}\n"
        "Use this only as upstream evidence. The DecisionCard remains your final ruling."
    )


def build_portfolio_manager_prompt(
    state: dict,
    memory,
) -> tuple[str, dict[str, object]]:
    context = build_agent_prompt_context(state)
    reports = upstream_reports_from_state(state)
    risk_context = risk_debate_from_state(state)
    history = risk_context.history
    risk_debate_state = state["risk_debate_state"]
    trader_plan = state["investment_plan"]
    portfolio_context = (state.get("portfolio_context") or "").strip()
    portfolio_context_block = (
        portfolio_context
        if portfolio_context
        else _empty_portfolio_context(context.output_language)
    )
    opportunity_context_block = _format_opportunity_context(
        state.get("opportunity_context"), context.output_language
    )

    trader_plan_block = context_block(
        "trader_plan",
        trader_plan,
        limit=6000,
    )
    past_memory_block = memory_recommendations_block(
        memory,
        reports.combined,
        default="No past memories found.",
        limit=6000,
    )
    risk_history_block = context_block(
        "risk_analysts_debate_history",
        history,
        limit=6000,
    )
    decision_card_schema_example = format_json_block(
        {
            "decision_report": "## Rating\n\n...\n\n## Executive Summary\n\n...\n\n## Investment Thesis\n\n...",
            "decision_card": {
                "rating": "HOLD",
                "action": "WATCH",
                "confidence": "low",
                "conviction_score": 42,
                "time_horizon": "Not specified",
                "one_line_summary": "One concise user-facing sentence.",
                "thesis": "Concise thesis with the main evidence and caveats.",
                "key_reasons": [
                    {
                        "pillar": "portfolio",
                        "point": "Short decision point",
                        "evidence": "Concrete evidence from analyst reports or risk debate.",
                        "strength": "medium",
                        "source": "risk_debate",
                        "data_date": None,
                        "confidence": "medium",
                        "limitation": "Known data limitation, or null.",
                    }
                ],
                "key_risks": ["Risk summary bullet."],
                "data_quality_notes": ["Missing or weak input note."],
                "position_guidance": {
                    "suggested_exposure": "Generic risk-based exposure guidance.",
                    "max_exposure": None,
                    "sizing_rationale": None,
                    "risk_budget_note": "Generic risk guidance; do not assume real holdings.",
                },
            },
        }
    )

    prompt = f"""As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision.

Final decision authority: you are the only agent allowed to issue the user-facing portfolio rating and action. Treat upstream `signal` values as legacy directional inputs, not final verdicts. Base the final DecisionCard on evidence quality, portfolio context, risk budget, and data limitations.

{context.evidence_rules_instruction}
{context.memory_skepticism_instruction}

{context.instrument_context}

{portfolio_context_block}

{opportunity_context_block}

Guidelines for Decision-Making:
1. **Summarize Key Arguments**: Extract the strongest points from each analyst, focusing on relevance to the context.
2. **Provide Rationale**: Support your recommendation with direct evidence and counterarguments from the debate.
3. **Refine the Trader's Plan**: Start with the trader plan in the untrusted context block below, and adjust it based on the analysts' insights.
4. **Learn from Past Mistakes**: Use lessons from the past-decision memory context block to address prior misjudgments and improve the decision you are making now.
5. **Use Portfolio Context Carefully**: If portfolio context is provided, you may use it to calibrate the final rating/action and narrative. For the structured DecisionCard intelligence fields, do not assume or disclose user-specific current exposure. Position guidance must be generic, risk-based, and suitable for a user who may have no recorded position.
6. **Use Opportunity Context Safely**: If Opportunity Radar context is provided, cite only its explicit trigger, theme, candidate type, and historical validation fields. If historical validation is unavailable or sample size is insufficient, state that clearly and do not invent win rates or returns.
7. **Keep Internal Context Private**: Use the portfolio context only to adjust exposure-aware advice. Do not quote raw ledger lines, account names, JSON/code-fence names, prompt labels, or internal implementation terms in user-facing prose. For Chinese output, describe this naturally as "持仓参考" or "现有持仓".

---

**Rating Scale** (use exactly one uppercase enum in `decision_card.rating`):
- **BUY**: Strong conviction to enter or add to position
- **OVERWEIGHT**: Favorable outlook, gradually increase exposure
- **HOLD**: Maintain current position, no action needed
- **UNDERWEIGHT**: Reduce exposure, take partial profits
- **SELL**: Exit position or avoid entry

**Context:**
{trader_plan_block}

{past_memory_block}

{context.trade_feedback_message}

**Risk Analysts Debate History:**
{risk_history_block}

---

Be decisive and ground every conclusion in specific evidence from the analysts.

Return only the structured response requested by the runtime schema:
- `decision_report`: user-facing markdown narrative without JSON code fences. Follow the section structure specified in the `decision_report` field description.
- `decision_card`: the structured final decision object.

	Top-level response must be exactly the schema object. Do not create markdown headings named `decision_report` or `decision_card`, and do not label the two schema fields as markdown sections.

	For `decision_card`, use English enum literals exactly:
- rating: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL
- action: OPEN, ADD, MAINTAIN, TRIM, EXIT, WATCH, NO_ACTION, AVOID
- confidence: high, medium, low
	- trade_readiness: READY, WAITING_FOR_TRIGGER, BLOCKED_BY_RISK, DATA_INSUFFICIENT, NO_ACTION_REQUIRED
	- data_quality_level: complete, partial, weak, insufficient

	Minimum valid schema shape to follow. Do not return this as a fenced code block; return the raw schema object requested by the runtime:
	{decision_card_schema_example}

	Schema-shape rules:
	- `time_horizon`, `one_line_summary`, and `thesis` are required. If the horizon is unavailable, set `time_horizon` to "Not specified".
	- `key_reasons` must be an array of evidence objects. Never emit `key_reasons` as an array of strings.
	- Use `key_risks` for risk bullets. Do not create a separate `risk_summary` field.
	- `position_guidance` must be an object with `suggested_exposure`, `max_exposure`, `sizing_rationale`, and `risk_budget_note`, or null. Never emit it as a string.
	- Do not add unsupported fields such as `ticker`, `symbol`, `market`, or `risk_summary` inside `decision_card`.

	Do not invent exact price levels if the reports do not provide reliable current price or technical levels. If price levels are unavailable, use null and explain the limitation in data_quality_notes. Rating and action are different concepts. Conviction_score reflects opportunity, risk, evidence strength, and data quality. Key_reasons must cite concrete evidence from analyst reports.
	Do not generate Portfolio Fit, Decision Journal, Opportunity Queue, or Conviction Breakdown fields. Do not write phrases such as "your current position", "your portfolio", "你当前仓位", or "你的组合" inside `position_guidance`; keep it generic and risk-based.

{context.style_instruction}
{context.language_instruction}"""

    return prompt, {
        "instrument_context": context.instrument_context,
        "risk_debate_state": risk_debate_state,
        "runtime_warnings": list(state.get("runtime_warnings") or []),
    }


def build_portfolio_manager_turn_prompt(state: dict, memory):
    prompt, metadata = build_portfolio_manager_prompt(state, memory)
    return prompt, (), metadata


def build_portfolio_manager_result(
    *,
    state: dict,
    response_content: str,
    runtime_warnings: list[dict],
    portfolio_decision_card: dict | None = None,
    portfolio_decision_structured: dict | None = None,
) -> dict:
    risk_debate_state = state["risk_debate_state"]

    result = {
        "risk_debate_state": record_portfolio_decision(
            risk_debate_state,
            decision=response_content,
        ),
        "final_trade_decision": response_content,
        "runtime_warnings": runtime_warnings,
    }
    if portfolio_decision_card is not None:
        result["portfolio_decision_card"] = portfolio_decision_card
    if portfolio_decision_structured is not None:
        result["portfolio_decision_structured"] = portfolio_decision_structured
    return result


def build_portfolio_manager_result_from_structured(
    *,
    state: dict,
    structured_payload: object,
) -> dict:
    structured = parse_structured_output(
        structured_payload,
        PortfolioManagerStructuredOutput,
    )
    decision_card = structured.decision_card.model_dump(mode="json")
    structured_output = structured.model_dump(mode="json")
    return build_portfolio_manager_result(
        state=state,
        response_content=render_structured_portfolio_decision(structured),
        runtime_warnings=list(state.get("runtime_warnings") or []),
        portfolio_decision_card=decision_card,
        portfolio_decision_structured=structured_output,
    )


def build_portfolio_manager_result_for_turn(
    state: dict,
    structured_payload: dict | PortfolioManagerStructuredOutput,
) -> dict:
    return build_portfolio_manager_result_from_structured(
        state=state,
        structured_payload=structured_payload,
    )


def structured_fallback_from_transient_state(
    state: dict,
    error: BaseException,
) -> PortfolioManagerStructuredOutput:
    return structured_fallback_from_transient_error(
        instrument_context=build_instrument_context(state["company_of_interest"]),
        error=error,
    )


PORTFOLIO_MANAGER_AGENT = StructuredAgentTurn(
    agent_name="portfolio_manager",
    display_name="Portfolio Manager",
    output_schema=PortfolioManagerStructuredOutput,
    output_key="portfolio_decision_structured",
    build_prompt=build_portfolio_manager_turn_prompt,
    commit_output=build_portfolio_manager_result_for_turn,
    memory_key="portfolio_manager_memory",
    invalid_response_warning=portfolio_structured_output_warning,
    fallback_from_invalid_response=structured_fallback_from_invalid_response,
    is_transient_error=is_transient_portfolio_llm_error,
    transient_error_warning=portfolio_transient_llm_warning,
    fallback_from_transient_error=structured_fallback_from_transient_state,
)
