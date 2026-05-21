from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "FinancialSituationMemory": (
        "diverge.agents.utils.memory",
        "FinancialSituationMemory",
    ),
    "AgentState": ("diverge.agents.utils.agent_states", "AgentState"),
    "InvestDebateState": ("diverge.agents.utils.agent_states", "InvestDebateState"),
    "RiskDebateState": ("diverge.agents.utils.agent_states", "RiskDebateState"),
    "create_msg_delete": ("diverge.agents.utils.agent_utils", "create_msg_delete"),
    "build_fundamentals_analyst_prompt": (
        "diverge.agents.analysts.fundamentals_analyst",
        "build_fundamentals_analyst_prompt",
    ),
    "build_fundamentals_analyst_result": (
        "diverge.agents.analysts.fundamentals_analyst",
        "build_fundamentals_analyst_result",
    ),
    "build_market_analyst_prompt": (
        "diverge.agents.analysts.market_analyst",
        "build_market_analyst_prompt",
    ),
    "build_market_analyst_result": (
        "diverge.agents.analysts.market_analyst",
        "build_market_analyst_result",
    ),
    "build_news_analyst_prompt": (
        "diverge.agents.analysts.news_analyst",
        "build_news_analyst_prompt",
    ),
    "build_news_analyst_result": (
        "diverge.agents.analysts.news_analyst",
        "build_news_analyst_result",
    ),
    "build_social_media_analyst_prompt": (
        "diverge.agents.analysts.social_media_analyst",
        "build_social_media_analyst_prompt",
    ),
    "build_social_media_analyst_result": (
        "diverge.agents.analysts.social_media_analyst",
        "build_social_media_analyst_result",
    ),
    "build_bear_researcher_prompt": (
        "diverge.agents.researchers.bear_researcher",
        "build_bear_researcher_prompt",
    ),
    "build_bear_researcher_result": (
        "diverge.agents.researchers.bear_researcher",
        "build_bear_researcher_result",
    ),
    "build_bull_researcher_prompt": (
        "diverge.agents.researchers.bull_researcher",
        "build_bull_researcher_prompt",
    ),
    "build_bull_researcher_result": (
        "diverge.agents.researchers.bull_researcher",
        "build_bull_researcher_result",
    ),
    "build_aggressive_risk_prompt": (
        "diverge.agents.risk_mgmt.aggressive_debator",
        "build_aggressive_risk_prompt",
    ),
    "build_aggressive_risk_result": (
        "diverge.agents.risk_mgmt.aggressive_debator",
        "build_aggressive_risk_result",
    ),
    "build_conservative_risk_prompt": (
        "diverge.agents.risk_mgmt.conservative_debator",
        "build_conservative_risk_prompt",
    ),
    "build_conservative_risk_result": (
        "diverge.agents.risk_mgmt.conservative_debator",
        "build_conservative_risk_result",
    ),
    "build_neutral_risk_prompt": (
        "diverge.agents.risk_mgmt.neutral_debator",
        "build_neutral_risk_prompt",
    ),
    "build_neutral_risk_result": (
        "diverge.agents.risk_mgmt.neutral_debator",
        "build_neutral_risk_result",
    ),
    "build_research_manager_prompt": (
        "diverge.agents.managers.research_manager",
        "build_research_manager_prompt",
    ),
    "build_research_manager_result": (
        "diverge.agents.managers.research_manager",
        "build_research_manager_result",
    ),
    "build_summary_agent_prompt": (
        "diverge.agents.managers.summary_agent",
        "build_summary_agent_prompt",
    ),
    "build_summary_agent_result": (
        "diverge.agents.managers.summary_agent",
        "build_summary_agent_result",
    ),
    "PortfolioManagerStructuredOutput": (
        "diverge.agents.managers.portfolio_manager",
        "PortfolioManagerStructuredOutput",
    ),
    "build_portfolio_manager_prompt": (
        "diverge.agents.managers.portfolio_manager",
        "build_portfolio_manager_prompt",
    ),
    "build_portfolio_manager_result": (
        "diverge.agents.managers.portfolio_manager",
        "build_portfolio_manager_result",
    ),
    "build_portfolio_manager_result_from_structured": (
        "diverge.agents.managers.portfolio_manager",
        "build_portfolio_manager_result_from_structured",
    ),
    "build_trader_prompt": ("diverge.agents.trader.trader", "build_trader_prompt"),
    "build_trader_result": ("diverge.agents.trader.trader", "build_trader_result"),
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
