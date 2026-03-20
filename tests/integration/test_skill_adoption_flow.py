import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from tradingagents.agents.analysts.fundamentals_analyst import (
    create_fundamentals_analyst,
)
from tradingagents.runner import save_report_to_disk


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


def _vendor_payloads():
    return {
        "get_fundamentals": (
            "# Company Fundamentals for MSFT\n"
            "# Data retrieved on: 2026-03-20 10:00:00\n\n"
            "Market Cap: 2500\n"
            "Shares Outstanding: 100\n"
            "Free Cash Flow: 120\n"
            "EBITDA: 220\n"
            "Net Income: 120\n"
        ),
        "get_balance_sheet": (
            "# Balance Sheet data for MSFT (annual)\n"
            "# Data retrieved on: 2026-03-20 10:00:00\n\n"
            ",2025-12-31\n"
            "Cash And Cash Equivalents,80\n"
            "Total Debt,150\n"
            "Stockholders Equity,600\n"
            "Ordinary Shares Number,100\n"
        ),
        "get_cashflow": (
            "# Cash Flow data for MSFT (annual)\n"
            "# Data retrieved on: 2026-03-20 10:00:00\n\n"
            ",2025-12-31\n"
            "Free Cash Flow,120\n"
        ),
        "get_income_statement": (
            "# Income Statement data for MSFT (annual)\n"
            "# Data retrieved on: 2026-03-20 10:00:00\n\n"
            ",2025-12-31\n"
            "Total Revenue,1000\n"
            "EBITDA,220\n"
            "Net Income,120\n"
        ),
    }


@patch("tradingagents.dataflows.interface.route_to_vendor")
def test_skill_adoption_flow_generates_valuation_report_and_artifacts(
    mock_route_to_vendor,
):
    payloads = _vendor_payloads()
    mock_route_to_vendor.side_effect = lambda method, *args, **kwargs: payloads[method]

    llm = _FakeLLM()
    node = create_fundamentals_analyst(llm)
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
