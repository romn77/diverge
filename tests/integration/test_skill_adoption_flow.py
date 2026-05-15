import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from diverge.agents.analysts.fundamentals_analyst import (
    FundamentalsAnalyst,
)
from diverge.runner import save_report_to_disk
from diverge.valuation.schemas import FinancialSnapshot, MarketContext, ValuationInput


class _FakeLLM:
    def __init__(self):
        self.prompts = []

    def bind_tools(self, tools):
        def _invoke(prompt):
            self.prompts.append(prompt.to_string())
            return AIMessage(
                content=(
                    "# Fundamentals\n\n"
                    "Core operations remain resilient after the quarter.\n\n"
                    "```json-highlights\n"
                    '{\n  "category": "fundamentals",\n  "signal": "BUY",\n'
                    '  "signal_confidence": "medium",\n  "summary": "Cash generation remains durable.",\n'
                    '  "metrics": [\n    {"name": "Revenue Growth", "value": "8%", "assessment": "Healthy"}\n  ],\n'
                    '  "financial_health": "Solid"\n}\n'
                    "```"
                ),
                tool_calls=[],
            )

        return RunnableLambda(_invoke)


def _valuation_input() -> ValuationInput:
    return ValuationInput(
        ticker="MSFT",
        market=MarketContext(
            market="us",
            currency="USD",
            share_price=25.0,
            shares_outstanding=100.0,
            market_cap=2_500.0,
        ),
        financials=[
            FinancialSnapshot(
                period="FY2025",
                revenue=1_000.0,
                ebitda=220.0,
                net_income=120.0,
                free_cash_flow=120.0,
                cash_and_equivalents=80.0,
                total_debt=150.0,
                shareholders_equity=600.0,
            )
        ],
    )


@patch("diverge.agents.analysts.fundamentals_analyst.get_valuation_ready_fundamentals")
def test_skill_adoption_flow_generates_valuation_report_and_artifacts(
    mock_get_valuation_ready_fundamentals,
):
    mock_get_valuation_ready_fundamentals.return_value = _valuation_input()

    llm = _FakeLLM()
    node = FundamentalsAnalyst(llm)
    state = {
        "trade_date": "2026-03-20",
        "company_of_interest": "MSFT",
        "output_language": "en",
        "messages": [HumanMessage(content="Analyze fundamentals")],
        "earnings_event": {
            "earnings_date": "2026-03-15",
            "fiscal_period": "Q1 2026",
            "reported_revenue": "97B",
            "reported_eps": "1.72",
            "guidance_change": "Raised services outlook",
        },
    }

    result = node(state)
    fundamentals_report = result["fundamentals_report"]

    assert "## Post-Earnings Review Focus" in fundamentals_report
    assert "## DCF Summary" in fundamentals_report
    assert "## Multiples Summary" in fundamentals_report
    assert '"category": "fundamentals"' in fundamentals_report

    final_state = {
        "market_report": "# Market\n\nConstructive backdrop.",
        "sentiment_report": "# Sentiment\n\nConstructive positioning.",
        "news_report": "# News\n\nCatalysts remain favorable.",
        "fundamentals_report": fundamentals_report,
        "investment_plan": "Accumulate on durable cash generation.",
        "trader_investment_plan": "Scale in over multiple sessions.",
        "investment_debate_state": {
            "bull_history": "Bull Analyst: Cash generation and guidance support upside.",
            "bear_history": "Bear Analyst: Valuation leaves less margin for error.",
            "judge_decision": "Research Manager: BUY with a focus on earnings follow-through.",
        },
        "risk_debate_state": {
            "aggressive_history": "Aggressive Analyst: Momentum supports adding risk.",
            "conservative_history": "Conservative Analyst: Keep position sizing disciplined.",
            "neutral_history": "Neutral Analyst: Respect volatility around catalysts.",
            "judge_decision": "Portfolio Manager: BUY with risk controls.",
        },
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = save_report_to_disk(final_state, "MSFT", Path(temp_dir))
        saved_fundamentals = Path(temp_dir) / "1_analysts" / "fundamentals.md"
        thesis_path = Path(temp_dir) / "artifacts" / "thesis.json"

        assert report_path.is_file()
        assert saved_fundamentals.is_file()
        assert thesis_path.is_file()
        assert "## DCF Summary" in saved_fundamentals.read_text(encoding="utf-8")

        thesis_payload = json.loads(thesis_path.read_text(encoding="utf-8"))
        assert thesis_payload["ticker"] == "MSFT"
        assert thesis_payload["next_catalysts"]
