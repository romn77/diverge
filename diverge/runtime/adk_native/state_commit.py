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
from diverge.runtime.structured_output import parse_structured_output


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
