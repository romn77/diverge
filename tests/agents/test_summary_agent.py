from tradingagents.agents.managers.summary_agent import create_summary_agent


class _FakeResponse:
    content = "BUY with disciplined sizing because cash generation is durable while valuation risk remains the key constraint."


class _FakeLLM:
    def __init__(self):
        self.prompt = ""

    def invoke(self, prompt):
        self.prompt = prompt
        return _FakeResponse()


def test_summary_agent_builds_concise_report_summary_from_final_state():
    llm = _FakeLLM()
    agent = create_summary_agent(llm)

    result = agent(
        {
            "company_of_interest": "MSFT",
            "trade_date": "2026-04-01",
            "output_language": "en",
            "market_report": "Market trend remains constructive.",
            "sentiment_report": "Sentiment is neutral.",
            "news_report": "Cloud demand remains a catalyst.",
            "fundamentals_report": "Cash generation remains durable.",
            "trader_investment_plan": "Scale in gradually.",
            "investment_debate_state": {
                "bull_history": "Bull Analyst: upside remains intact.",
                "bear_history": "Bear Analyst: valuation is stretched.",
                "judge_decision": "Research Manager: BUY with discipline.",
            },
            "risk_debate_state": {
                "aggressive_history": "Aggressive Analyst: momentum supports adding.",
                "conservative_history": "Conservative Analyst: protect downside.",
                "neutral_history": "Neutral Analyst: keep balanced sizing.",
                "judge_decision": "Portfolio Manager: BUY with tight risk controls.",
            },
        }
    )

    assert result["report_summary"].startswith("BUY with disciplined sizing")
    assert "about 150 English words" in llm.prompt
    assert "Do not include markdown headings" in llm.prompt
    assert "Bull Analyst: upside remains intact." in llm.prompt
    assert "Conservative Analyst: protect downside." in llm.prompt
