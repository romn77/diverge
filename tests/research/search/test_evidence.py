from datetime import datetime, timezone

from diverge.research.search.evidence import build_search_evidence_artifact
from diverge.research.search.schema import SearchResponse, SearchResult, SearchWarning
from diverge.research.search.session import SearchSessionRegistry


def _session():
    return SearchSessionRegistry().create(
        analysis_run_id="run-1",
        ticker="AAPL",
        analysis_date="2026-05-08",
    )


def _response(
    *,
    query: str = "AAPL latest news",
    url: str = "https://example.com/aapl",
    cache_hit: bool = False,
    warning: SearchWarning | None = None,
) -> SearchResponse:
    retrieved_at = datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc)
    served_at = datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc) if cache_hit else None
    return SearchResponse(
        agent="News Analyst",
        ticker="AAPL",
        analysis_date="2026-05-08",
        query=query,
        requested_at=retrieved_at,
        cache_hit=cache_hit,
        warnings=[warning] if warning else [],
        results=[
            SearchResult(
                id=query,
                provider="brave",
                query=query,
                title="Apple news",
                url=url,
                canonical_url=url,
                retrieved_at=retrieved_at,
                served_at=served_at,
            )
        ]
        if url
        else [],
    )


def test_empty_session_returns_none():
    assert build_search_evidence_artifact(_session()) is None


def test_calls_produce_search_evidence_artifact_with_summary():
    session = _session()
    session.record(_response())

    artifact = build_search_evidence_artifact(session)

    assert artifact["type"] == "search_evidence"
    assert artifact["schema_version"] == 1
    assert artifact["analysis_run_id"] == "run-1"
    assert artifact["summary"]["call_count"] == 1
    assert artifact["summary"]["result_count"] == 1


def test_cache_hit_call_includes_original_retrieved_at_and_served_at():
    session = _session()
    session.record(_response(cache_hit=True))

    artifact = build_search_evidence_artifact(session)
    result = artifact["calls"][0]["results"][0]

    assert artifact["calls"][0]["cache_hit"]
    assert result["retrieved_at"].startswith("2026-05-08T10:00:00")
    assert result["served_at"].startswith("2026-05-08T12:00:00")


def test_failed_call_includes_warnings_and_empty_results():
    session = _session()
    session.record(
        _response(
            url="",
            warning=SearchWarning(
                provider="brave",
                reason="timeout",
                message="Timed out.",
            ),
        )
    )

    artifact = build_search_evidence_artifact(session)

    assert artifact["calls"][0]["results"] == []
    assert artifact["calls"][0]["warnings"][0]["reason"] == "timeout"


def test_duplicate_urls_are_deduped_in_report_level_results():
    session = _session()
    session.record(_response(query="q1", url="https://example.com/a?utm_source=x"))
    session.record(_response(query="q2", url="https://example.com/a"))

    artifact = build_search_evidence_artifact(session)

    assert artifact["summary"]["call_count"] == 2
    assert artifact["summary"]["result_count"] == 2
    assert artifact["summary"]["unique_result_count"] == 1
    assert len(artifact["results"]) == 1
