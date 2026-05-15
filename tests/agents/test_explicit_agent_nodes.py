from __future__ import annotations

import functools
import inspect

from google.adk.workflow import FunctionNode

from diverge.agents.analysts.fundamentals_analyst import FundamentalsAnalyst
from diverge.agents.analysts.market_analyst import MarketAnalyst
from diverge.agents.analysts.news_analyst import NewsAnalyst
from diverge.agents.analysts.social_media_analyst import SocialMediaAnalyst
from diverge.agents.base import DivergeAgentNode
from diverge.agents.managers.portfolio_manager import PortfolioManager
from diverge.agents.managers.research_manager import ResearchManager
from diverge.agents.managers.summary_agent import SummaryAgent
from diverge.agents.researchers.bear_researcher import BearResearcher
from diverge.agents.researchers.bull_researcher import BullResearcher
from diverge.agents.risk_mgmt.aggressive_debator import AggressiveDebator
from diverge.agents.risk_mgmt.conservative_debator import ConservativeDebator
from diverge.agents.risk_mgmt.neutral_debator import NeutralDebator
from diverge.agents.trader.trader import Trader


class FakeMemory:
    def get_memories(self, _current_situation, n_matches=2):
        return []


def test_prompt_agent_classes_create_explicit_agent_node_objects():
    llm = object()
    memory = FakeMemory()
    agents = [
        MarketAnalyst(llm),
        SocialMediaAnalyst(llm),
        NewsAnalyst(llm),
        FundamentalsAnalyst(llm),
        BullResearcher(llm, memory),
        BearResearcher(llm, memory),
        ResearchManager(llm, memory),
        Trader(llm, memory),
        AggressiveDebator(llm),
        ConservativeDebator(llm),
        NeutralDebator(llm),
        PortfolioManager(llm, memory),
        SummaryAgent(llm),
    ]

    names = [agent.name for agent in agents]

    assert len(names) == len(set(names))
    for agent in agents:
        assert isinstance(agent, DivergeAgentNode)
        assert callable(agent)
        assert agent.llm is llm
        assert agent.name
        assert not inspect.isfunction(agent)
        assert not isinstance(agent, functools.partial)
        assert agent.__call__.__closure__ is None


def test_explicit_agent_nodes_are_plain_callable_objects():
    agent = SummaryAgent(object())

    assert not hasattr(agent, "to_adk_function_node")


def test_adk_can_wrap_explicit_agent_objects_directly():
    agent = SummaryAgent(object())
    node = FunctionNode(func=agent, name=agent.name)

    assert node.name == agent.name
