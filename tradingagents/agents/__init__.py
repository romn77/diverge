from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "FinancialSituationMemory": ("tradingagents.agents.utils.memory", "FinancialSituationMemory"),
    "AgentState": ("tradingagents.agents.utils.agent_states", "AgentState"),
    "InvestDebateState": ("tradingagents.agents.utils.agent_states", "InvestDebateState"),
    "RiskDebateState": ("tradingagents.agents.utils.agent_states", "RiskDebateState"),
    "create_msg_delete": ("tradingagents.agents.utils.agent_utils", "create_msg_delete"),
    "create_fundamentals_analyst": ("tradingagents.agents.analysts.fundamentals_analyst", "create_fundamentals_analyst"),
    "create_market_analyst": ("tradingagents.agents.analysts.market_analyst", "create_market_analyst"),
    "create_news_analyst": ("tradingagents.agents.analysts.news_analyst", "create_news_analyst"),
    "create_social_media_analyst": ("tradingagents.agents.analysts.social_media_analyst", "create_social_media_analyst"),
    "create_bear_researcher": ("tradingagents.agents.researchers.bear_researcher", "create_bear_researcher"),
    "create_bull_researcher": ("tradingagents.agents.researchers.bull_researcher", "create_bull_researcher"),
    "create_aggressive_debator": ("tradingagents.agents.risk_mgmt.aggressive_debator", "create_aggressive_debator"),
    "create_conservative_debator": ("tradingagents.agents.risk_mgmt.conservative_debator", "create_conservative_debator"),
    "create_neutral_debator": ("tradingagents.agents.risk_mgmt.neutral_debator", "create_neutral_debator"),
    "create_research_manager": ("tradingagents.agents.managers.research_manager", "create_research_manager"),
    "create_summary_agent": ("tradingagents.agents.managers.summary_agent", "create_summary_agent"),
    "create_portfolio_manager": ("tradingagents.agents.managers.portfolio_manager", "create_portfolio_manager"),
    "create_risk_manager": ("tradingagents.agents.managers.risk_manager", "create_risk_manager"),
    "create_trader": ("tradingagents.agents.trader.trader", "create_trader"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value
