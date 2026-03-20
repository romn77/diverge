from datetime import date
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from tradingagents.agents.analysts.fundamentals_analyst import (
    create_fundamentals_analyst,
)
from tradingagents.valuation.schemas import FinancialSnapshot, MarketContext, ValuationInput


class _FakeLLM:
    def __init__(self, response: AIMessage):
        self.prompts = []
        self.response = response

    def bind_tools(self, tools):
        def _invoke(prompt):
            self.prompts.append(prompt.to_string())
            return self.response

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
            enterprise_value=2_570.0,
        ),
        financials=[
            FinancialSnapshot(
                period="annual",
                report_date=date(2025, 12, 31),
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


def _state():
    return {
        "trade_date": "2026-03-20",
        "company_of_interest": "MSFT",
        "output_language": "en",
        "messages": [HumanMessage(content="Analyze fundamentals")],
    }


@patch("tradingagents.agents.analysts.fundamentals_analyst.get_valuation_ready_fundamentals")
def test_fundamentals_report_includes_valuation_sections_before_highlights(
    mock_get_valuation_ready_fundamentals,
):
    mock_get_valuation_ready_fundamentals.return_value = _valuation_input()
    llm = _FakeLLM(
        AIMessage(
            content=(
                "Fundamentals analysis body.\n\n"
                "```json-highlights\n"
                '{\n  "category": "fundamentals",\n  "signal": "BUY",\n'
                '  "signal_confidence": "medium",\n  "summary": "Stable cash generation.",\n'
                '  "metrics": [],\n  "financial_health": "Strong"\n}\n'
                "```"
            ),
            tool_calls=[],
        )
    )

    node = create_fundamentals_analyst(llm)
    result = node(_state())
    report = result["fundamentals_report"]

    assert "## DCF Summary" in report
    assert "## Multiples Summary" in report
    assert "## Valuation Assumptions" in report
    assert report.index("## DCF Summary") < report.index("```json-highlights")
    assert '"category": "fundamentals"' in report
