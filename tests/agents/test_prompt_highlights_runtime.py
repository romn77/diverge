import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from diverge.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
from diverge.agents.managers.portfolio_manager import create_portfolio_manager
from diverge.agents.managers.research_manager import create_research_manager
from diverge.agents.researchers.bear_researcher import create_bear_researcher
from diverge.agents.researchers.bull_researcher import create_bull_researcher
from diverge.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from diverge.agents.risk_mgmt.conservative_debator import (
    create_conservative_debator,
)
from diverge.agents.risk_mgmt.neutral_debator import create_neutral_debator
from diverge.agents.trader.trader import create_trader
from diverge.valuation.schemas import FinancialSnapshot, MarketContext, ValuationInput


class _FakeResponse:
    def __init__(self, content="stub response"):
        self.content = content


class _FakeLLM:
    def __init__(self, tool_response=None):
        self.prompts = []
        self.tool_response = tool_response or AIMessage(
            content="stub response", tool_calls=[]
        )

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return _FakeResponse()

    def bind_tools(self, tools):
        def _invoke(prompt):
            self.prompts.append(prompt.to_string())
            return self.tool_response

        return RunnableLambda(_invoke)


class _FakeMemory:
    def get_memories(self, _curr_situation, n_matches=2):
        return [{"recommendation": f"memory {idx}"} for idx in range(n_matches)]


class _FakeGatewayTimeout(Exception):
    status_code = 504


class _FailingLLM:
    def invoke(self, _prompt):
        raise _FakeGatewayTimeout("504 Gateway Time-out")


class _ConnectionFailingLLM:
    def invoke(self, _prompt):
        raise RuntimeError("Connection error.")


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


def _valuation_input():
    return ValuationInput(
        ticker="QQQ",
        market=MarketContext(
            market="us",
            currency="USD",
            share_price=50.0,
            shares_outstanding=100.0,
            market_cap=5_000.0,
            enterprise_value=5_150.0,
        ),
        financials=[
            FinancialSnapshot(
                period="annual",
                report_date=None,
                revenue=1_000.0,
                ebitda=240.0,
                net_income=120.0,
                free_cash_flow=100.0,
                cash_and_equivalents=50.0,
                total_debt=200.0,
                shareholders_equity=800.0,
            )
        ],
    )


class PromptHighlightsRuntimeTests(unittest.TestCase):
    def test_prompt_nodes_with_json_highlights_do_not_raise_runtime_format_errors(self):
        cases = [
            ("bull", create_bull_researcher(_FakeLLM(), _FakeMemory()), _base_state()),
            ("bear", create_bear_researcher(_FakeLLM(), _FakeMemory()), _base_state()),
            (
                "research_manager",
                create_research_manager(_FakeLLM(), _FakeMemory()),
                _base_state(),
            ),
            ("trader", create_trader(_FakeLLM(), _FakeMemory()), _base_state()),
            ("aggressive", create_aggressive_debator(_FakeLLM()), _base_state()),
            ("conservative", create_conservative_debator(_FakeLLM()), _base_state()),
            ("neutral", create_neutral_debator(_FakeLLM()), _base_state()),
            (
                "portfolio_manager",
                create_portfolio_manager(_FakeLLM(), _FakeMemory()),
                _base_state(),
            ),
        ]

        for name, node, state in cases:
            with self.subTest(node=name):
                result = node(state)
                self.assertIsInstance(result, dict)

    @patch(
        "diverge.agents.analysts.fundamentals_analyst.get_valuation_ready_fundamentals"
    )
    def test_fundamentals_analyst_runtime_supports_valuation_sections(
        self,
        mock_get_valuation_ready_fundamentals,
    ):
        mock_get_valuation_ready_fundamentals.return_value = _valuation_input()
        llm = _FakeLLM(
            AIMessage(
                content=(
                    "fundamentals report\n\n"
                    "```json-highlights\n"
                    '{\n  "category": "fundamentals",\n  "signal": "HOLD",\n'
                    '  "signal_confidence": "medium",\n  "summary": "Balanced.",\n'
                    '  "metrics": [],\n  "financial_health": "Stable"\n}\n'
                    "```"
                ),
                tool_calls=[],
            )
        )
        node = create_fundamentals_analyst(llm)
        state = _base_state()
        state["messages"] = [HumanMessage(content="Analyze fundamentals")]

        result = node(state)

        self.assertIn("## DCF Summary", result["fundamentals_report"])
        self.assertIn('"category": "fundamentals"', result["fundamentals_report"])

    def test_portfolio_manager_gateway_timeout_returns_fallback_decision(self):
        node = create_portfolio_manager(_FailingLLM(), _FakeMemory())

        result = node(_base_state())

        self.assertIn(
            "Portfolio Manager Fallback Decision", result["final_trade_decision"]
        )
        self.assertIn("```json-decision-card", result["final_trade_decision"])
        self.assertIn('"rating": "HOLD"', result["final_trade_decision"])
        self.assertIn('"action": "NO_ACTION"', result["final_trade_decision"])
        self.assertEqual(
            result["risk_debate_state"]["judge_decision"],
            result["final_trade_decision"],
        )

    def test_portfolio_manager_connection_error_returns_fallback_decision(self):
        node = create_portfolio_manager(_ConnectionFailingLLM(), _FakeMemory())

        result = node(_base_state())

        self.assertIn(
            "Portfolio Manager Fallback Decision", result["final_trade_decision"]
        )
        self.assertIn("```json-decision-card", result["final_trade_decision"])
        self.assertIn('"rating": "HOLD"', result["final_trade_decision"])
        self.assertIn(
            "transient LLM connection failure", result["final_trade_decision"]
        )
        self.assertEqual(result["runtime_warnings"][0]["stage"], "Portfolio Manager")
        self.assertIn("Connection error.", result["runtime_warnings"][0]["message"])


if __name__ == "__main__":
    unittest.main()
