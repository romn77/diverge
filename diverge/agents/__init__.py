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
    "MarketAnalyst": ("diverge.agents.analysts.market_analyst", "MarketAnalyst"),
    "NewsAnalyst": ("diverge.agents.analysts.news_analyst", "NewsAnalyst"),
    "SocialMediaAnalyst": (
        "diverge.agents.analysts.social_media_analyst",
        "SocialMediaAnalyst",
    ),
    "BearResearcher": ("diverge.agents.researchers.bear_researcher", "BearResearcher"),
    "BullResearcher": ("diverge.agents.researchers.bull_researcher", "BullResearcher"),
    "AggressiveDebator": (
        "diverge.agents.risk_mgmt.aggressive_debator",
        "AggressiveDebator",
    ),
    "ConservativeDebator": (
        "diverge.agents.risk_mgmt.conservative_debator",
        "ConservativeDebator",
    ),
    "NeutralDebator": ("diverge.agents.risk_mgmt.neutral_debator", "NeutralDebator"),
    "ResearchManager": ("diverge.agents.managers.research_manager", "ResearchManager"),
    "SummaryAgent": ("diverge.agents.managers.summary_agent", "SummaryAgent"),
    "PortfolioManager": (
        "diverge.agents.managers.portfolio_manager",
        "PortfolioManager",
    ),
    "Trader": ("diverge.agents.trader.trader", "Trader"),
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
