from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from diverge.agents.analysts.fundamentals_analyst import (
    FundamentalsAnalyst,
)
from diverge.agents.analysts.news_analyst import NewsAnalyst


class _FakeLLM:
    def __init__(self):
        self.prompts = []

    def bind_tools(self, tools):
        def _invoke(prompt):
            self.prompts.append(prompt.to_string())
            return AIMessage(
                content=(
                    "analysis body\n\n"
                    "```json-highlights\n"
                    '{\n  "category": "news",\n  "signal": "HOLD",\n'
                    '  "signal_confidence": "medium",\n  "summary": "Summary",\n'
                    '  "market_impact": "mixed",\n  "key_events": [],\n'
                    '  "macro_outlook": "Stable"\n}\n'
                    "```"
                ),
                tool_calls=[],
            )

        return RunnableLambda(_invoke)


def _base_state():
    return {
        "trade_date": "2026-03-20",
        "company_of_interest": "AAPL",
        "output_language": "en",
        "messages": [HumanMessage(content="Analyze the company")],
    }


def test_news_analyst_uses_preview_mode_prompt_when_future_earnings_event_exists():
    llm = _FakeLLM()
    node = NewsAnalyst(llm)
    state = _base_state()
    state["earnings_event"] = {
        "earnings_date": "2026-03-25",
        "fiscal_period": "Q1 2026",
        "consensus_revenue": "95B",
        "consensus_eps": "1.60",
    }

    node(state)

    prompt = llm.prompts[-1]
    assert "Earnings mode: preview" in prompt
    assert "Frame the analysis as a pre-earnings setup" in prompt
    assert "Consensus revenue: 95B" in prompt


@patch("diverge.agents.analysts.fundamentals_analyst.get_valuation_ready_fundamentals")
def test_fundamentals_analyst_uses_post_earnings_mode_prompt_when_event_has_passed(
    mock_get_valuation_ready_fundamentals,
):
    mock_get_valuation_ready_fundamentals.side_effect = RuntimeError("skip valuation")
    llm = _FakeLLM()
    node = FundamentalsAnalyst(llm)
    state = _base_state()
    state["earnings_event"] = {
        "earnings_date": "2026-03-15",
        "fiscal_period": "Q1 2026",
        "reported_revenue": "97B",
        "reported_eps": "1.72",
        "guidance_change": "Raised services outlook",
    }

    node(state)

    prompt = llm.prompts[-1]
    assert "Earnings mode: review" in prompt
    assert "Compare reported results, guidance, and quality of earnings" in prompt
    assert "Reported EPS: 1.72" in prompt


def test_news_analyst_falls_back_cleanly_when_no_earnings_event_data_exists():
    llm = _FakeLLM()
    node = NewsAnalyst(llm)

    node(_base_state())

    prompt = llm.prompts[-1]
    assert "Earnings mode: general" in prompt
    assert "No earnings-specific event data is available." in prompt
