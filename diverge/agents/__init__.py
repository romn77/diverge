from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "DivergeAgentNode": ("diverge.agents.base", "DivergeAgentNode"),
    "FinancialSituationMemory": (
        "diverge.agents.utils.memory",
        "FinancialSituationMemory",
    ),
    "AgentState": ("diverge.agents.utils.agent_states", "AgentState"),
    "InvestDebateState": ("diverge.agents.utils.agent_states", "InvestDebateState"),
    "RiskDebateState": ("diverge.agents.utils.agent_states", "RiskDebateState"),
    "create_msg_delete": ("diverge.agents.utils.agent_utils", "create_msg_delete"),
    "FundamentalsAnalyst": (
        "diverge.agents.analysts.fundamentals_analyst",
        "FundamentalsAnalyst",
    ),
    "create_fundamentals_analyst": (
        "diverge.agents.analysts.fundamentals_analyst",
        "create_fundamentals_analyst",
    ),
    "MarketAnalyst": ("diverge.agents.analysts.market_analyst", "MarketAnalyst"),
    "create_market_analyst": (
        "diverge.agents.analysts.market_analyst",
        "create_market_analyst",
    ),
    "NewsAnalyst": ("diverge.agents.analysts.news_analyst", "NewsAnalyst"),
    "create_news_analyst": (
        "diverge.agents.analysts.news_analyst",
        "create_news_analyst",
    ),
    "SocialMediaAnalyst": (
        "diverge.agents.analysts.social_media_analyst",
        "SocialMediaAnalyst",
    ),
    "create_social_media_analyst": (
        "diverge.agents.analysts.social_media_analyst",
        "create_social_media_analyst",
    ),
    "BearResearcher": ("diverge.agents.researchers.bear_researcher", "BearResearcher"),
    "create_bear_researcher": (
        "diverge.agents.researchers.bear_researcher",
        "create_bear_researcher",
    ),
    "BullResearcher": ("diverge.agents.researchers.bull_researcher", "BullResearcher"),
    "create_bull_researcher": (
        "diverge.agents.researchers.bull_researcher",
        "create_bull_researcher",
    ),
    "AggressiveDebator": (
        "diverge.agents.risk_mgmt.aggressive_debator",
        "AggressiveDebator",
    ),
    "create_aggressive_debator": (
        "diverge.agents.risk_mgmt.aggressive_debator",
        "create_aggressive_debator",
    ),
    "ConservativeDebator": (
        "diverge.agents.risk_mgmt.conservative_debator",
        "ConservativeDebator",
    ),
    "create_conservative_debator": (
        "diverge.agents.risk_mgmt.conservative_debator",
        "create_conservative_debator",
    ),
    "NeutralDebator": ("diverge.agents.risk_mgmt.neutral_debator", "NeutralDebator"),
    "create_neutral_debator": (
        "diverge.agents.risk_mgmt.neutral_debator",
        "create_neutral_debator",
    ),
    "ResearchManager": ("diverge.agents.managers.research_manager", "ResearchManager"),
    "create_research_manager": (
        "diverge.agents.managers.research_manager",
        "create_research_manager",
    ),
    "SummaryAgent": ("diverge.agents.managers.summary_agent", "SummaryAgent"),
    "create_summary_agent": (
        "diverge.agents.managers.summary_agent",
        "create_summary_agent",
    ),
    "PortfolioManager": (
        "diverge.agents.managers.portfolio_manager",
        "PortfolioManager",
    ),
    "create_portfolio_manager": (
        "diverge.agents.managers.portfolio_manager",
        "create_portfolio_manager",
    ),
    "create_risk_manager": (
        "diverge.agents.managers.risk_manager",
        "create_risk_manager",
    ),
    "Trader": ("diverge.agents.trader.trader", "Trader"),
    "create_trader": ("diverge.agents.trader.trader", "create_trader"),
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
