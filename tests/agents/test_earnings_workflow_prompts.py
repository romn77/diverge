from unittest.mock import patch

from langchain_core.messages import HumanMessage

from diverge.agents.analysts.fundamentals_analyst import (
    build_fundamentals_analyst_prompt,
)
from diverge.agents.analysts.news_analyst import build_news_analyst_prompt


def _base_state():
    return {
        "trade_date": "2026-03-20",
        "company_of_interest": "AAPL",
        "output_language": "en",
        "messages": [HumanMessage(content="Analyze the company")],
    }


def test_news_analyst_uses_preview_mode_prompt_when_future_earnings_event_exists():
    state = _base_state()
    state["earnings_event"] = {
        "earnings_date": "2026-03-25",
        "fiscal_period": "Q1 2026",
        "consensus_revenue": "95B",
        "consensus_eps": "1.60",
    }

    prompt, _tools, _metadata = build_news_analyst_prompt(state)
    prompt = prompt.to_string()
    assert "Earnings mode: preview" in prompt
    assert "Frame the analysis as a pre-earnings setup" in prompt
    assert "Consensus revenue: 95B" in prompt


@patch("diverge.agents.analysts.fundamentals_analyst.get_valuation_ready_fundamentals")
def test_fundamentals_analyst_uses_post_earnings_mode_prompt_when_event_has_passed(
    mock_get_valuation_ready_fundamentals,
):
    mock_get_valuation_ready_fundamentals.side_effect = RuntimeError("skip valuation")
    state = _base_state()
    state["earnings_event"] = {
        "earnings_date": "2026-03-15",
        "fiscal_period": "Q1 2026",
        "reported_revenue": "97B",
        "reported_eps": "1.72",
        "guidance_change": "Raised services outlook",
    }

    prompt, _tools, _metadata = build_fundamentals_analyst_prompt(state)
    prompt = prompt.to_string()
    assert "Earnings mode: review" in prompt
    assert "Compare reported results, guidance, and quality of earnings" in prompt
    assert "Reported EPS: 1.72" in prompt


def test_news_analyst_falls_back_cleanly_when_no_earnings_event_data_exists():
    prompt, _tools, _metadata = build_news_analyst_prompt(_base_state())
    prompt = prompt.to_string()
    assert "Earnings mode: general" in prompt
    assert "No earnings-specific event data is available." in prompt
