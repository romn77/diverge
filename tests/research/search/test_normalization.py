from datetime import datetime, timezone

from diverge.research.search.normalization import (
    canonicalize_url,
    normalize_and_rank_results,
)
from diverge.research.search.schema import SearchResult


def _result(
    *,
    id: str = "r1",
    url: str = "https://example.com/news",
    title: str = "Title",
    snippet: str | None = "Snippet",
    published_at: datetime | None = None,
    relevance_score: float | None = None,
    freshness_status: str = "unknown",
    source: str | None = "Example",
) -> SearchResult:
    return SearchResult(
        id=id,
        provider="brave",
        query="AAPL latest news",
        title=title,
        url=url,
        source=source,
        snippet=snippet,
        published_at=published_at,
        retrieved_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        freshness_status=freshness_status,
        relevance_score=relevance_score,
    )


def test_canonicalize_url_removes_tracking_parameters():
    canonical = canonicalize_url(
        "HTTPS://Example.com/news?utm_source=x&b=2&ref=feed&source=abc&fbclid=1&gclid=2&a=1#section"
    )

    assert canonical == "https://example.com/news?a=1&b=2"


def test_normalize_dedupes_identical_canonical_urls_and_keeps_newer_result():
    older = _result(
        id="old",
        url="https://example.com/news?utm_medium=email",
        published_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
        relevance_score=0.9,
    )
    newer = _result(
        id="new",
        url="https://example.com/news",
        published_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        relevance_score=0.1,
    )

    results = normalize_and_rank_results([older, newer], max_results=5)

    assert [result.id for result in results] == ["new"]
    assert results[0].canonical_url == "https://example.com/news"


def test_normalize_keeps_higher_relevance_score_when_dates_tie():
    lower = _result(
        id="lower",
        url="https://example.com/news?ref=1",
        published_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        relevance_score=0.2,
    )
    higher = _result(
        id="higher",
        url="https://example.com/news",
        published_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        relevance_score=0.7,
    )

    results = normalize_and_rank_results([lower, higher], max_results=5)

    assert [result.id for result in results] == ["higher"]


def test_normalize_drops_empty_urls_and_empty_content():
    empty_url = _result(id="empty-url", url="")
    empty_content = _result(id="empty-content", title=" ", snippet=" ")
    valid = _result(id="valid", url="https://example.com/valid", title="Valid")

    results = normalize_and_rank_results(
        [empty_url, empty_content, valid],
        max_results=5,
    )

    assert [result.id for result in results] == ["valid"]


def test_missing_published_at_sorts_after_fresh_dated_results():
    unknown = _result(
        id="unknown",
        url="https://example.com/unknown",
        published_at=None,
        relevance_score=1.0,
    )
    fresh = _result(
        id="fresh",
        url="https://example.com/fresh",
        published_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        relevance_score=0.1,
        freshness_status="fresh",
    )

    results = normalize_and_rank_results([unknown, fresh], max_results=5)

    assert [result.id for result in results] == ["fresh", "unknown"]
