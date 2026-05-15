import unittest
import json
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from diverge.agents.analysts.fundamentals_analyst import FundamentalsAnalyst
from diverge.agents.managers.portfolio_manager import (
    PortfolioManager,
    PortfolioManagerStructuredOutput,
)
from diverge.agents.managers.research_manager import ResearchManager
from diverge.agents.researchers.bear_researcher import BearResearcher
from diverge.agents.researchers.bull_researcher import BullResearcher
from diverge.agents.risk_mgmt.aggressive_debator import AggressiveDebator
from diverge.agents.risk_mgmt.conservative_debator import ConservativeDebator
from diverge.agents.risk_mgmt.neutral_debator import NeutralDebator
from diverge.agents.trader.trader import Trader
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


class _StructuredLLM:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []
        self.output_schema = None

    def invoke(self, prompt, *, output_schema=None):
        self.prompts.append(prompt)
        self.output_schema = output_schema
        return _FakeResponse(json.dumps(self.payload))


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
            ("bull", BullResearcher(_FakeLLM(), _FakeMemory()), _base_state()),
            ("bear", BearResearcher(_FakeLLM(), _FakeMemory()), _base_state()),
            (
                "research_manager",
                ResearchManager(_FakeLLM(), _FakeMemory()),
                _base_state(),
            ),
            ("trader", Trader(_FakeLLM(), _FakeMemory()), _base_state()),
            ("aggressive", AggressiveDebator(_FakeLLM()), _base_state()),
            ("conservative", ConservativeDebator(_FakeLLM()), _base_state()),
            ("neutral", NeutralDebator(_FakeLLM()), _base_state()),
            (
                "portfolio_manager",
                PortfolioManager(_FakeLLM(), _FakeMemory()),
                _base_state(),
            ),
        ]

        for name, node, state in cases:
            with self.subTest(node=name):
                result = node(state)
                self.assertIsInstance(result, dict)

    def test_upstream_prompts_define_evidence_contracts_without_final_verdict(self):
        trader_llm = _FakeLLM()
        Trader(trader_llm, _FakeMemory())(_base_state())
        trader_prompt = trader_llm.prompts[0].to_string()

        self.assertIn("execution planner", trader_prompt)
        self.assertIn('"evidence_blocks"', trader_prompt)
        self.assertIn('"risk_budget"', trader_prompt)
        self.assertIn("Do not write `FINAL TRANSACTION PROPOSAL`", trader_prompt)
        self.assertNotIn("Conclude your narrative analysis", trader_prompt)

        risk_llm = _FakeLLM()
        AggressiveDebator(risk_llm)(_base_state())
        risk_prompt = risk_llm.prompts[0].to_string()

        self.assertIn('"risk_budget"', risk_prompt)
        self.assertIn('"required_pm_adjustment"', risk_prompt)
        self.assertIn('"evidence_blocks"', risk_prompt)
        self.assertIn("Do not write `FINAL TRANSACTION PROPOSAL`", risk_prompt)

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
        node = FundamentalsAnalyst(llm)
        state = _base_state()
        state["messages"] = [HumanMessage(content="Analyze fundamentals")]

        result = node(state)

        self.assertIn("## DCF Summary", result["fundamentals_report"])
        self.assertIn('"category": "fundamentals"', result["fundamentals_report"])

    def test_portfolio_manager_gateway_timeout_returns_fallback_decision(self):
        node = PortfolioManager(_FailingLLM(), _FakeMemory())

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

    def test_portfolio_manager_prompt_uses_user_facing_portfolio_context(self):
        llm = _FakeLLM()
        node = PortfolioManager(llm, _FakeMemory())
        state = _base_state()
        state["output_language"] = "cn"

        node(state)

        prompt = llm.prompts[0].to_string()
        self.assertIn("当前持仓参考", prompt)
        self.assertIn("未提供该用户的已跟踪持仓", prompt)
        self.assertNotIn("Portfolio Ledger Context", prompt)
        self.assertIn("internal implementation terms", prompt)

    def test_portfolio_manager_connection_error_returns_fallback_decision(self):
        node = PortfolioManager(_ConnectionFailingLLM(), _FakeMemory())

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

    def test_portfolio_manager_schema_output_sets_decision_card_state(self):
        llm = _StructuredLLM(
            {
                "decision_report": "## Portfolio Manager Decision\n\nRating: OVERWEIGHT.",
                "decision_card": {
                    "rating": "OVERWEIGHT",
                    "action": "ADD",
                    "confidence": "medium",
                    "conviction_score": 72,
                    "time_horizon": "5-20 trading days",
                    "one_line_summary": "Add gradually while respecting valuation risk.",
                    "thesis": "The setup is constructive, but sizing should remain staged.",
                    "key_reasons": [
                        {
                            "pillar": "portfolio",
                            "point": "Balanced upside",
                            "evidence": "Risk debate supports staged exposure.",
                            "strength": "medium",
                        }
                    ],
                    "key_risks": ["Valuation risk"],
                    "trade_readiness": "WAITING_FOR_TRIGGER",
                    "data_quality_level": "partial",
                },
            }
        )
        node = PortfolioManager(llm, _FakeMemory())

        result = node(_base_state())

        self.assertIs(llm.output_schema, PortfolioManagerStructuredOutput)
        self.assertEqual(result["portfolio_decision_card"]["rating"], "OVERWEIGHT")
        self.assertIn("```json-decision-card", result["final_trade_decision"])
        self.assertIn('"rating": "OVERWEIGHT"', result["final_trade_decision"])
        self.assertEqual(result["runtime_warnings"], [])


if __name__ == "__main__":
    unittest.main()
