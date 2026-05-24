from diverge.agents.debate_state import (
    append_investment_argument,
    append_risk_argument,
    record_portfolio_decision,
    record_research_decision,
)


def test_investment_debate_transitions_track_current_speaker():
    debate = {
        "history": "prior",
        "bull_history": "",
        "bear_history": "Bear Analyst: prior bear",
        "current_response": "Bear Analyst: prior bear",
        "current_bull_response": "",
        "current_bear_response": "Bear Analyst: prior bear",
        "count": 1,
    }

    updated = append_investment_argument(
        debate,
        speaker="bull",
        argument="Bull Analyst: new bull",
    )
    decided = record_research_decision(updated, decision="Research Manager: HOLD")

    assert updated["current_bull_response"] == "Bull Analyst: new bull"
    assert updated["current_bear_response"] == "Bear Analyst: prior bear"
    assert updated["count"] == 2
    assert decided["judge_decision"] == "Research Manager: HOLD"
    assert decided["count"] == 2


def test_risk_debate_transitions_track_latest_speaker():
    debate = {
        "history": "prior",
        "aggressive_history": "",
        "conservative_history": "",
        "neutral_history": "",
        "latest_speaker": "",
        "current_aggressive_response": "",
        "current_conservative_response": "",
        "current_neutral_response": "",
        "count": 0,
    }

    updated = append_risk_argument(
        debate,
        speaker="neutral",
        argument="Neutral Analyst: wait",
    )

    assert updated["latest_speaker"] == "Neutral"
    assert updated["neutral_history"].endswith("Neutral Analyst: wait")
    assert updated["current_neutral_response"] == "Neutral Analyst: wait"
    assert updated["count"] == 1


def test_portfolio_decision_preserves_risk_debate_histories():
    debate = {
        "history": "risk history",
        "aggressive_history": "aggressive",
        "conservative_history": "conservative",
        "neutral_history": "neutral",
        "latest_speaker": "Neutral",
        "current_aggressive_response": "aggressive current",
        "current_conservative_response": "conservative current",
        "current_neutral_response": "neutral current",
        "count": 3,
    }

    updated = record_portfolio_decision(debate, decision="Portfolio Manager: HOLD")

    assert updated["judge_decision"] == "Portfolio Manager: HOLD"
    assert updated["latest_speaker"] == "Judge"
    assert updated["history"] == "risk history"
    assert updated["count"] == 3
