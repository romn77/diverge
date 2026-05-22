from __future__ import annotations

from typing import Any

from diverge.agents.report_output import (
    AggressiveRiskStructuredOutput,
    BearCaseStructuredOutput,
    BullCaseStructuredOutput,
    ConservativeRiskStructuredOutput,
    NeutralRiskStructuredOutput,
    ResearchDecisionStructuredOutput,
    TraderStructuredOutput,
    merge_structured_agent_output,
    render_markdown_with_highlights,
)
from diverge.agents.utils.fundamental_data_tools import (
    get_valuation_ready_fundamentals,
)
from diverge.research.earnings import (
    build_earnings_workflow_context,
    inject_earnings_section,
)
from diverge.runtime.structured_output import parse_structured_output
from diverge.valuation.formatter import (
    format_valuation_sections,
    inject_valuation_sections,
)


def commit_analyst_output(
    state: dict[str, Any],
    *,
    spec: Any,
    structured_payload: Any,
) -> dict[str, Any]:
    """Commit an analyst ADK output directly into Diverge's read-model state."""

    structured = parse_structured_output(structured_payload, spec.output_schema)
    payload = structured.model_dump(mode="json")
    report_markdown = structured.report_markdown
    result: dict[str, Any] = {}

    if spec.analyst_key in {"news", "fundamentals"}:
        earnings_context = build_earnings_workflow_context(
            trade_date=state["trade_date"],
            ticker=state["company_of_interest"],
            earnings_event=state.get("earnings_event"),
        )
        report_markdown = inject_earnings_section(
            report_markdown,
            earnings_context.report_section,
        )

    if spec.analyst_key == "fundamentals":
        valuation_result = _valuation_report_sections(state)
        report_markdown = inject_valuation_sections(
            report_markdown,
            valuation_result.pop("valuation_sections"),
        )
        result.update(valuation_result)

    result[spec.report_key] = render_markdown_with_highlights(
        report_markdown,
        structured.highlights,
    )
    result["structured_agent_outputs"] = merge_structured_agent_output(
        state,
        agent_name=spec.structured_agent_name,
        payload=payload,
    )
    return result


def commit_bull_researcher_output(
    state: dict[str, Any],
    structured_payload: Any,
) -> dict[str, Any]:
    debate = state["investment_debate_state"]
    rendered = _render_structured_report(
        structured_payload,
        BullCaseStructuredOutput,
    )
    argument = f"Bull Analyst: {rendered}"
    result = {
        "investment_debate_state": {
            "history": debate.get("history", "") + "\n" + argument,
            "bull_history": debate.get("bull_history", "") + "\n" + argument,
            "bear_history": debate.get("bear_history", ""),
            "current_response": argument,
            "current_bull_response": argument,
            "current_bear_response": debate.get(
                "current_bear_response",
                debate.get("current_response", ""),
            ),
            "count": debate["count"] + 1,
        }
    }
    _merge_structured_output(
        result,
        state,
        agent_name="bull_researcher",
        schema=BullCaseStructuredOutput,
        structured_payload=structured_payload,
    )
    return result


def commit_bear_researcher_output(
    state: dict[str, Any],
    structured_payload: Any,
) -> dict[str, Any]:
    debate = state["investment_debate_state"]
    rendered = _render_structured_report(
        structured_payload,
        BearCaseStructuredOutput,
    )
    argument = f"Bear Analyst: {rendered}"
    result = {
        "investment_debate_state": {
            "history": debate.get("history", "") + "\n" + argument,
            "bear_history": debate.get("bear_history", "") + "\n" + argument,
            "bull_history": debate.get("bull_history", ""),
            "current_response": argument,
            "current_bull_response": debate.get(
                "current_bull_response",
                debate.get("current_response", ""),
            ),
            "current_bear_response": argument,
            "count": debate["count"] + 1,
        }
    }
    _merge_structured_output(
        result,
        state,
        agent_name="bear_researcher",
        schema=BearCaseStructuredOutput,
        structured_payload=structured_payload,
    )
    return result


def commit_research_manager_output(
    state: dict[str, Any],
    structured_payload: Any,
) -> dict[str, Any]:
    debate = state["investment_debate_state"]
    rendered = _render_structured_report(
        structured_payload,
        ResearchDecisionStructuredOutput,
    )
    result = {
        "investment_debate_state": {
            "judge_decision": rendered,
            "history": debate.get("history", ""),
            "bear_history": debate.get("bear_history", ""),
            "bull_history": debate.get("bull_history", ""),
            "current_response": rendered,
            "current_bull_response": debate.get("current_bull_response", ""),
            "current_bear_response": debate.get("current_bear_response", ""),
            "count": debate["count"],
        },
        "investment_plan": rendered,
    }
    _merge_structured_output(
        result,
        state,
        agent_name="research_manager",
        schema=ResearchDecisionStructuredOutput,
        structured_payload=structured_payload,
    )
    return result


def commit_trader_output(
    state: dict[str, Any],
    structured_payload: Any,
) -> dict[str, Any]:
    rendered = _render_structured_report(structured_payload, TraderStructuredOutput)
    result = {
        "messages": [],
        "trader_investment_plan": rendered,
        "sender": "Trader",
    }
    _merge_structured_output(
        result,
        state,
        agent_name="trader",
        schema=TraderStructuredOutput,
        structured_payload=structured_payload,
    )
    return result


def commit_aggressive_risk_output(
    state: dict[str, Any],
    structured_payload: Any,
) -> dict[str, Any]:
    return _commit_risk_debater_output(
        state,
        structured_payload,
        schema=AggressiveRiskStructuredOutput,
        agent_name="aggressive_analyst",
        speaker_label="Aggressive Analyst",
        latest_speaker="Aggressive",
        history_key="aggressive_history",
        current_key="current_aggressive_response",
    )


def commit_conservative_risk_output(
    state: dict[str, Any],
    structured_payload: Any,
) -> dict[str, Any]:
    return _commit_risk_debater_output(
        state,
        structured_payload,
        schema=ConservativeRiskStructuredOutput,
        agent_name="conservative_analyst",
        speaker_label="Conservative Analyst",
        latest_speaker="Conservative",
        history_key="conservative_history",
        current_key="current_conservative_response",
    )


def commit_neutral_risk_output(
    state: dict[str, Any],
    structured_payload: Any,
) -> dict[str, Any]:
    return _commit_risk_debater_output(
        state,
        structured_payload,
        schema=NeutralRiskStructuredOutput,
        agent_name="neutral_analyst",
        speaker_label="Neutral Analyst",
        latest_speaker="Neutral",
        history_key="neutral_history",
        current_key="current_neutral_response",
    )


def _commit_risk_debater_output(
    state: dict[str, Any],
    structured_payload: Any,
    *,
    schema: Any,
    agent_name: str,
    speaker_label: str,
    latest_speaker: str,
    history_key: str,
    current_key: str,
) -> dict[str, Any]:
    debate = state["risk_debate_state"]
    rendered = _render_structured_report(structured_payload, schema)
    argument = f"{speaker_label}: {rendered}"

    new_debate = {
        "history": debate.get("history", "") + "\n" + argument,
        "aggressive_history": debate.get("aggressive_history", ""),
        "conservative_history": debate.get("conservative_history", ""),
        "neutral_history": debate.get("neutral_history", ""),
        "latest_speaker": latest_speaker,
        "current_aggressive_response": debate.get("current_aggressive_response", ""),
        "current_conservative_response": debate.get(
            "current_conservative_response",
            "",
        ),
        "current_neutral_response": debate.get("current_neutral_response", ""),
        "count": debate["count"] + 1,
    }
    new_debate[history_key] = debate.get(history_key, "") + "\n" + argument
    new_debate[current_key] = argument

    result = {"risk_debate_state": new_debate}
    _merge_structured_output(
        result,
        state,
        agent_name=agent_name,
        schema=schema,
        structured_payload=structured_payload,
    )
    return result


def _render_structured_report(structured_payload: Any, schema: Any) -> str:
    structured = parse_structured_output(structured_payload, schema)
    return render_markdown_with_highlights(
        structured.report_markdown,
        structured.highlights,
    )


def _merge_structured_output(
    result: dict[str, Any],
    state: dict[str, Any],
    *,
    agent_name: str,
    schema: Any,
    structured_payload: Any,
) -> None:
    structured = parse_structured_output(structured_payload, schema)
    result["structured_agent_outputs"] = merge_structured_agent_output(
        state,
        agent_name=agent_name,
        payload=structured.model_dump(mode="json"),
    )


def _valuation_report_sections(state: dict[str, Any]) -> dict[str, Any]:
    instrument_type = state.get("instrument_type")
    valuation_applicability = state.get("valuation_applicability")
    valuation_applicability_reason = state.get("valuation_applicability_reason")

    try:
        valuation_input = get_valuation_ready_fundamentals(
            state["company_of_interest"],
            curr_date=state["trade_date"],
            freq="annual",
        )
        instrument_type = valuation_input.instrument_type
        valuation_applicability = valuation_input.valuation_applicability
        valuation_applicability_reason = valuation_input.valuation_applicability_reason
        valuation_sections = format_valuation_sections(valuation_input)
    except ValueError as exc:
        valuation_sections = (
            f"## Valuation Availability\n\nValuation sections unavailable: {exc}"
        )
    except Exception:
        valuation_sections = "## Valuation Availability\n\nValuation sections unavailable due to unexpected preparation failure."

    return {
        "instrument_type": instrument_type,
        "valuation_applicability": valuation_applicability,
        "valuation_applicability_reason": valuation_applicability_reason,
        "valuation_sections": valuation_sections,
    }
