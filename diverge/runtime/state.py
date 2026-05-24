from __future__ import annotations

from typing import Any

from diverge.agents.utils.agent_states import InvestDebateState, RiskDebateState
from diverge.runtime.analysis_schema import (
    HISTORICAL_TRADE_FEEDBACK_KEY,
    HISTORICAL_TRADE_REVIEWS_KEY,
)


def create_initial_state(
    company_name: str,
    trade_date: str,
    output_language: str = "en",
    historical_trade_feedback: str = "",
    historical_trade_reviews: list[dict] | None = None,
    portfolio_context: str = "",
    opportunity_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    messages: list[object] = [("human", company_name)]
    if historical_trade_feedback:
        messages.insert(0, ("human", historical_trade_feedback))
    return {
        "messages": messages,
        "company_of_interest": company_name,
        "trade_date": str(trade_date),
        "output_language": output_language,
        "earnings_event": None,
        "instrument_type": None,
        "valuation_applicability": None,
        "valuation_applicability_reason": None,
        HISTORICAL_TRADE_FEEDBACK_KEY: historical_trade_feedback,
        HISTORICAL_TRADE_REVIEWS_KEY: historical_trade_reviews or [],
        "portfolio_context": portfolio_context or "",
        "opportunity_context": opportunity_context or None,
        "investment_debate_state": InvestDebateState(
            {
                "bull_history": "",
                "bear_history": "",
                "history": "",
                "current_response": "",
                "current_bull_response": "",
                "current_bear_response": "",
                "judge_decision": "",
                "count": 0,
            }
        ),
        "risk_debate_state": RiskDebateState(
            {
                "aggressive_history": "",
                "conservative_history": "",
                "neutral_history": "",
                "history": "",
                "latest_speaker": "",
                "current_aggressive_response": "",
                "current_conservative_response": "",
                "current_neutral_response": "",
                "judge_decision": "",
                "count": 0,
            }
        ),
        "market_report": "",
        "fundamentals_report": "",
        "sentiment_report": "",
        "news_report": "",
        "investment_plan": "",
        "trader_investment_plan": "",
        "final_trade_decision": "",
        "portfolio_decision_card": None,
        "portfolio_decision_structured": None,
        "structured_agent_outputs": {},
        "runtime_warnings": [],
        "report_summary": "",
        "report_summary_structured": None,
    }
