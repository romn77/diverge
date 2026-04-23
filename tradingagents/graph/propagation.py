# TradingAgents/graph/propagation.py

from typing import Any, Dict, List, Optional

from tradingagents.agents.utils.agent_states import (
    InvestDebateState,
    RiskDebateState,
)


class Propagator:
    """Handles state initialization and propagation through the graph."""

    def __init__(self, max_recur_limit=100):
        """Initialize with configuration parameters."""
        self.max_recur_limit = max_recur_limit

    def create_initial_state(
        self,
        company_name: str,
        trade_date: str,
        output_language: str = "en",
        historical_trade_feedback: str = "",
        historical_trade_reviews: Optional[List[dict]] = None,
        portfolio_context: str = "",
    ) -> Dict[str, Any]:
        """Create the initial state for the agent graph."""
        messages = [("human", company_name)]
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
            "historical_trade_feedback": historical_trade_feedback,
            "historical_trade_reviews": historical_trade_reviews or [],
            "portfolio_context": portfolio_context or "",
            "investment_debate_state": InvestDebateState(
                {
                    "bull_history": "",
                    "bear_history": "",
                    "history": "",
                    "current_response": "",
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
        }

    def get_graph_args(self, callbacks: Optional[List] = None) -> Dict[str, Any]:
        """Get arguments for the graph invocation.

        Args:
            callbacks: Optional list of callback handlers for tool execution tracking.
                       Note: LLM callbacks are handled separately via LLM constructor.
        """
        config: Dict[str, Any] = {"recursion_limit": self.max_recur_limit}
        if callbacks:
            config["callbacks"] = callbacks
        return {
            "stream_mode": "values",
            "config": config,
        }
