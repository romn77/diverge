from datetime import datetime, timezone

from diverge.research.search.schema import SearchResponse, SearchResult, SearchWarning
from diverge.research.search.session import (
    SearchBudget,
    SearchSessionRegistry,
)


def _response(
    *,
    agent: str = "News Analyst",
    query: str = "AAPL latest news",
    url: str = "https://example.com/aapl",
    warning: SearchWarning | None = None,
) -> SearchResponse:
    now = datetime(2026, 5, 8, tzinfo=timezone.utc)
    return SearchResponse(
        agent=agent,
        ticker="AAPL",
        analysis_date="2026-05-08",
        query=query,
        requested_at=now,
        warnings=[warning] if warning else [],
        results=[
            SearchResult(
                id=f"{agent}-{query}",
                provider="brave",
                query=query,
                title="Apple news",
                url=url,
                retrieved_at=now,
            )
        ]
        if url
        else [],
    )


def test_registry_creates_gets_and_pops_session_by_analysis_run_id():
    registry = SearchSessionRegistry()

    session = registry.create(
        analysis_run_id="run-1",
        ticker="AAPL",
        analysis_date="2026-05-08",
    )

    assert registry.get("run-1") is session
    assert registry.pop("run-1") is session
    assert registry.get("run-1") is None


def test_session_enforces_per_analysis_and_per_agent_budget():
    registry = SearchSessionRegistry()
    session = registry.create(
        analysis_run_id="run-1",
        ticker="AAPL",
        analysis_date="2026-05-08",
        budget=SearchBudget(per_analysis_max_queries=4, per_agent_max_queries=2),
    )

    assert session.can_search("News Analyst")[0]
    session.record(_response(agent="News Analyst", query="q1"))
    session.record(_response(agent="News Analyst", query="q2"))

    allowed, warning = session.can_search("News Analyst")
    assert not allowed
    assert warning is not None
    assert warning.reason == "agent_budget_exhausted"

    session.record(_response(agent="Social Analyst", query="q3"))
    session.record(_response(agent="Social Analyst", query="q4"))
    allowed, warning = session.can_search("Other Analyst")
    assert not allowed
    assert warning is not None
    assert warning.reason == "analysis_budget_exhausted"


def test_budget_exhausted_response_does_not_increment_budget_when_recorded():
    session = SearchSessionRegistry().create(
        analysis_run_id="run-1",
        ticker="AAPL",
        analysis_date="2026-05-08",
    )
    response = session.warning_response(
        agent="News Analyst",
        query="AAPL latest news",
        warning=SearchWarning(reason="analysis_budget_exhausted", message="Budget exhausted."),
    )

    session.record(response, count_budget=False)

    assert session.used_queries == 0
    assert session.calls == [response]


def test_session_dedupes_duplicate_result_urls_for_artifact_summary():
    session = SearchSessionRegistry().create(
        analysis_run_id="run-1",
        ticker="AAPL",
        analysis_date="2026-05-08",
    )
    session.record(_response(query="q1", url="https://example.com/aapl?utm_source=x"))
    session.record(_response(query="q2", url="https://example.com/aapl"))

    assert len(session.unique_results()) == 1


def test_failed_or_disabled_calls_are_retained():
    session = SearchSessionRegistry().create(
        analysis_run_id="run-1",
        ticker="AAPL",
        analysis_date="2026-05-08",
    )
    warning = SearchWarning(
        provider=None,
        reason="search_disabled",
        message="Global Web Search is disabled.",
    )

    session.record(_response(warning=warning, url=""))

    assert len(session.calls) == 1
    assert session.calls[0].warnings[0].reason == "search_disabled"
