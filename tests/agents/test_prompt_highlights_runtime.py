import unittest

from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.managers.risk_manager import create_risk_manager
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from tradingagents.agents.risk_mgmt.conservative_debator import (
    create_conservative_debator,
)
from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
from tradingagents.agents.trader.trader import create_trader


class _FakeResponse:
    def __init__(self, content="stub response"):
        self.content = content


class _FakeLLM:
    def __init__(self):
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return _FakeResponse()


class _FakeMemory:
    def get_memories(self, _curr_situation, n_matches=2):
        return [{"recommendation": f"memory {idx}"} for idx in range(n_matches)]


def _base_state():
    return {
        "company_of_interest": "QQQ",
        "trade_date": "2026-03-06",
        "output_language": "en",
        "market_report": "market report",
        "sentiment_report": "sentiment report",
        "news_report": "news report",
        "fundamentals_report": "fundamentals report",
        "investment_plan": "investment plan",
        "trader_investment_plan": "trader plan",
        "investment_debate_state": {
            "history": "debate history",
            "bull_history": "bull history",
            "bear_history": "bear history",
            "current_response": "prior response",
            "count": 1,
        },
        "risk_debate_state": {
            "history": "risk history",
            "aggressive_history": "aggressive history",
            "conservative_history": "conservative history",
            "neutral_history": "neutral history",
            "current_aggressive_response": "agg response",
            "current_conservative_response": "con response",
            "current_neutral_response": "neu response",
            "latest_speaker": "Aggressive",
            "count": 1,
        },
    }


class PromptHighlightsRuntimeTests(unittest.TestCase):
    def test_prompt_nodes_with_json_highlights_do_not_raise_runtime_format_errors(self):
        cases = [
            ("bull", create_bull_researcher(_FakeLLM(), _FakeMemory()), _base_state()),
            ("bear", create_bear_researcher(_FakeLLM(), _FakeMemory()), _base_state()),
            ("research_manager", create_research_manager(_FakeLLM(), _FakeMemory()), _base_state()),
            ("trader", create_trader(_FakeLLM(), _FakeMemory()), _base_state()),
            ("aggressive", create_aggressive_debator(_FakeLLM()), _base_state()),
            ("conservative", create_conservative_debator(_FakeLLM()), _base_state()),
            ("neutral", create_neutral_debator(_FakeLLM()), _base_state()),
            ("risk_manager", create_risk_manager(_FakeLLM(), _FakeMemory()), _base_state()),
        ]

        for name, node, state in cases:
            with self.subTest(node=name):
                result = node(state)
                self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
