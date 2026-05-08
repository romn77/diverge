from datetime import datetime, timezone

from diverge.agents.utils.search_tools import (
    clear_search_service_for_testing,
    set_search_service_for_testing,
    web_search_evidence,
)
from diverge.research.search.schema import SearchResponse, SearchResult, SearchWarning
from diverge.research.search.session import (
    SearchToolContext,
    current_search_context,
    search_sessions,
)


class FakeSearchService:
    def __init__(self, response: SearchResponse):
        self.response = response
        self.calls = []

    def search_recent_evidence(self, **kwargs):
        self.calls.append(kwargs)
        return self.response.model_copy(
            update={
                "agent": kwargs["agent"],
                "ticker": kwargs["ticker"],
                "analysis_date": kwargs["analysis_date"],
                "query": kwargs["query"] or self.response.query,
            }
        )


def _response(*, warning: SearchWarning | None = None) -> SearchResponse:
    now = datetime(2026, 5, 8, tzinfo=timezone.utc)
    return SearchResponse(
        agent="News Analyst",
        ticker="AAPL",
        analysis_date="2026-05-08",
        query="AAPL latest news",
        requested_at=now,
        successful_provider="brave",
        warnings=[warning] if warning else [],
        results=[
            SearchResult(
                id="r1",
                provider="brave",
                query="AAPL latest news",
                title="Apple shares rise",
                url="https://example.com/aapl",
                source="Reuters",
                snippet="Shares rose after guidance.",
                published_at=now,
                retrieved_at=now,
            )
        ]
        if warning is None
        else [],
    )


def _set_context():
    session = search_sessions.create(
        analysis_run_id="tool-run",
        ticker="AAPL",
        analysis_date="2026-05-08",
    )
    token = current_search_context.set(
        SearchToolContext(
            analysis_run_id="tool-run",
            agent="News Analyst",
            ticker="AAPL",
            analysis_date="2026-05-08",
            market="us",
            language="en",
        )
    )
    return session, token


def teardown_function():
    clear_search_service_for_testing()
    search_sessions.pop("tool-run")
    current_search_context.set(None)


def test_tool_returns_readable_markdown_and_records_session_response():
    session, token = _set_context()
    service = FakeSearchService(_response())
    set_search_service_for_testing(service)

    try:
        markdown = web_search_evidence.invoke(
            {"query": "AAPL latest news", "purpose": "fresh_news", "max_results": 99}
        )
    finally:
        current_search_context.reset(token)

    assert "Web Search Evidence for query: AAPL latest news" in markdown
    assert "Reuters - Apple shares rise" in markdown
    assert "Published: 2026-05-08" in markdown
    assert "URL: https://example.com/aapl" in markdown
    assert "Snippet: Shares rose after guidance." in markdown
    assert "{" not in markdown
    assert service.calls[0]["max_results"] == 5
    assert len(session.calls) == 1


def test_tool_renders_warnings_when_search_is_disabled():
    _session, token = _set_context()
    service = FakeSearchService(
        _response(
            warning=SearchWarning(
                provider=None,
                reason="search_disabled",
                message="Global Web Search is disabled.",
            )
        )
    )
    set_search_service_for_testing(service)

    try:
        markdown = web_search_evidence.invoke(
            {"query": "AAPL", "purpose": "fresh_news", "max_results": 5}
        )
    finally:
        current_search_context.reset(token)

    assert "No web search results returned." in markdown
    assert "Warnings:" in markdown
    assert "- search_disabled: Global Web Search is disabled." in markdown


def test_budget_exhausted_does_not_call_service():
    session, token = _set_context()
    service = FakeSearchService(_response())
    set_search_service_for_testing(service)
    for index in range(session.budget.per_agent_max_queries):
        session.record(_response().model_copy(update={"query": f"q{index}"}))

    try:
        markdown = web_search_evidence.invoke(
            {"query": "AAPL", "purpose": "fresh_news", "max_results": 5}
        )
    finally:
        current_search_context.reset(token)

    assert "agent_budget_exhausted" in markdown
    assert service.calls == []
    assert len(session.calls) == session.budget.per_agent_max_queries + 1


def test_tool_does_not_allow_provider_selection():
    assert "provider" not in web_search_evidence.args
