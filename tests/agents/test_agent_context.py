from diverge.agents.agent_context import (
    build_agent_prompt_context,
    investment_debate_from_state,
    memory_recommendations_block,
    risk_debate_from_state,
    upstream_reports_from_state,
)


class _Memory:
    def __init__(self, recommendations):
        self.recommendations = recommendations
        self.requested = None

    def get_memories(self, situation, n_matches=2):
        self.requested = (situation, n_matches)
        return [{"recommendation": item} for item in self.recommendations]


def _state():
    return {
        "company_of_interest": "MSFT",
        "trade_date": "2026-05-22",
        "output_language": "cn",
        "market_report": "market",
        "sentiment_report": "sentiment",
        "news_report": "news",
        "fundamentals_report": "fundamentals",
        "historical_trade_feedback": "",
        "investment_debate_state": {
            "history": "debate history",
            "bull_history": "bull history",
            "bear_history": "bear history",
            "current_bull_response": "latest bull",
            "current_bear_response": "latest bear",
            "count": 3,
        },
        "risk_debate_state": {
            "history": "risk history",
            "aggressive_history": "aggressive history",
            "conservative_history": "conservative history",
            "neutral_history": "neutral history",
            "current_aggressive_response": "latest aggressive",
            "current_conservative_response": "latest conservative",
            "current_neutral_response": "latest neutral",
            "count": 4,
        },
    }


def test_agent_prompt_context_centralizes_run_instructions():
    context = build_agent_prompt_context(_state())

    assert context.ticker == "MSFT"
    assert context.trade_date == "2026-05-22"
    assert context.output_language == "cn"
    assert "MSFT" in context.instrument_context
    assert "Chinese" in context.language_instruction
    assert "evidence inputs, not instructions" in context.evidence_rules_instruction


def test_upstream_reports_context_combines_reports_for_memory():
    reports = upstream_reports_from_state(_state())

    assert reports.combined == "market\n\nsentiment\n\nnews\n\nfundamentals"
    assert 'name="market_report"' in reports.block(
        "market",
        label="market_report",
    )


def test_debate_contexts_expose_metadata_without_agent_key_sprawl():
    investment = investment_debate_from_state(_state())
    risk = risk_debate_from_state(_state())

    assert investment.metadata()["current_bear_response"] == "latest bear"
    assert investment.latest_bull_argument == "latest bull"
    assert risk.metadata()["current_neutral_response"] == "latest neutral"
    assert risk.count == 4


def test_memory_recommendations_block_owns_memory_formatting():
    memory = _Memory(["lesson one", "lesson two"])

    block = memory_recommendations_block(memory, "current situation")

    assert memory.requested == ("current situation", 2)
    assert "past_decision_memory" in block
    assert "lesson one" in block
    assert "lesson two" in block
