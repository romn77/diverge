from __future__ import annotations

import functools
import inspect

from google.adk.workflow import FunctionNode

from diverge.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
from diverge.agents.analysts.market_analyst import create_market_analyst
from diverge.agents.analysts.news_analyst import create_news_analyst
from diverge.agents.analysts.social_media_analyst import create_social_media_analyst
from diverge.agents.base import DivergeAgentNode
from diverge.agents.managers.portfolio_manager import create_portfolio_manager
from diverge.agents.managers.research_manager import create_research_manager
from diverge.agents.managers.summary_agent import create_summary_agent
from diverge.agents.researchers.bear_researcher import create_bear_researcher
from diverge.agents.researchers.bull_researcher import create_bull_researcher
from diverge.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from diverge.agents.risk_mgmt.conservative_debator import create_conservative_debator
from diverge.agents.risk_mgmt.neutral_debator import create_neutral_debator
from diverge.agents.trader.trader import create_trader


class FakeMemory:
    def get_memories(self, _current_situation, n_matches=2):
        return []


def test_prompt_agent_factories_return_explicit_agent_node_objects():
    llm = object()
    memory = FakeMemory()
    agents = [
        create_market_analyst(llm),
        create_social_media_analyst(llm),
        create_news_analyst(llm),
        create_fundamentals_analyst(llm),
        create_bull_researcher(llm, memory),
        create_bear_researcher(llm, memory),
        create_research_manager(llm, memory),
        create_trader(llm, memory),
        create_aggressive_debator(llm),
        create_conservative_debator(llm),
        create_neutral_debator(llm),
        create_portfolio_manager(llm, memory),
        create_summary_agent(llm),
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
    agent = create_summary_agent(object())

    assert not hasattr(agent, "to_adk_function_node")


def test_adk_can_wrap_explicit_agent_objects_directly():
    agent = create_summary_agent(object())
    node = FunctionNode(func=agent, name=agent.name)

    assert node.name == agent.name
