from pathlib import Path


def _source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_news_and_sentiment_prompts_explain_conditional_web_search_budget():
    for path in (
        "diverge/agents/analysts/news_analyst.py",
        "diverge/agents/analysts/social_media_analyst.py",
    ):
        source = _source(path)
        assert "Web Search is an optional evidence supplement" in source
        assert "at most 2 times" in source
        assert "Prefer existing financial news tools first" in source
        assert "If Web Search returns no results or warnings, continue" in source
        assert "Do not make web-search-backed claims" in source
        assert "Brave" not in source
        assert "Tavily" not in source
        assert "Bocha" not in source


def test_portfolio_and_other_non_news_agents_do_not_reference_web_search_tool():
    for path in (
        "diverge/agents/managers/portfolio_manager.py",
        "diverge/agents/analysts/market_analyst.py",
        "diverge/agents/analysts/fundamentals_analyst.py",
    ):
        source = _source(path)
        assert "web_search_evidence" not in source
