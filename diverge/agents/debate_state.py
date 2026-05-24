from __future__ import annotations

from typing import Any, Literal


InvestmentSpeaker = Literal["bull", "bear"]
RiskSpeaker = Literal["aggressive", "conservative", "neutral"]


def append_investment_argument(
    debate: dict[str, Any],
    *,
    speaker: InvestmentSpeaker,
    argument: str,
) -> dict[str, Any]:
    if speaker == "bull":
        return {
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
    return {
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


def record_research_decision(
    debate: dict[str, Any],
    *,
    decision: str,
) -> dict[str, Any]:
    return {
        "judge_decision": decision,
        "history": debate.get("history", ""),
        "bear_history": debate.get("bear_history", ""),
        "bull_history": debate.get("bull_history", ""),
        "current_response": decision,
        "current_bull_response": debate.get("current_bull_response", ""),
        "current_bear_response": debate.get("current_bear_response", ""),
        "count": debate["count"],
    }


def append_risk_argument(
    debate: dict[str, Any],
    *,
    speaker: RiskSpeaker,
    argument: str,
) -> dict[str, Any]:
    speaker_fields = {
        "aggressive": (
            "Aggressive",
            "aggressive_history",
            "current_aggressive_response",
        ),
        "conservative": (
            "Conservative",
            "conservative_history",
            "current_conservative_response",
        ),
        "neutral": (
            "Neutral",
            "neutral_history",
            "current_neutral_response",
        ),
    }
    latest_speaker, history_key, current_key = speaker_fields[speaker]
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
    return new_debate


def record_portfolio_decision(
    debate: dict[str, Any],
    *,
    decision: str,
) -> dict[str, Any]:
    return {
        "judge_decision": decision,
        "history": debate["history"],
        "aggressive_history": debate["aggressive_history"],
        "conservative_history": debate["conservative_history"],
        "neutral_history": debate["neutral_history"],
        "latest_speaker": "Judge",
        "current_aggressive_response": debate["current_aggressive_response"],
        "current_conservative_response": debate["current_conservative_response"],
        "current_neutral_response": debate["current_neutral_response"],
        "count": debate["count"],
    }
