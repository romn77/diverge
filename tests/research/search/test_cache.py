from datetime import datetime, timedelta, timezone

from diverge.research.search.cache import SearchCache, SearchCacheKey
from diverge.research.search.schema import SearchResponse, SearchResult


def _response() -> SearchResponse:
    retrieved_at = datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc)
    return SearchResponse(
        agent="News Analyst",
        ticker="AAPL",
        analysis_date="2026-05-08",
        query="AAPL latest news",
        requested_at=retrieved_at,
        successful_provider="brave",
        attempted_providers=["brave"],
        results=[
            SearchResult(
                id="r1",
                provider="brave",
                query="AAPL latest news",
                title="Apple news",
                url="https://example.com/apple",
                retrieved_at=retrieved_at,
            )
        ],
    )


def test_cache_key_includes_search_context_fields():
    base = SearchCacheKey(
        provider="brave",
        query="AAPL latest news",
        ticker="AAPL",
        analysis_date="2026-05-08",
        market="us",
        language="en",
        purpose="fresh_news",
        max_results=5,
    )
    changed_query = base.model_copy(update={"query": "AAPL sentiment"})
    changed_market = base.model_copy(update={"market": "cn"})

    assert base.digest() != changed_query.digest()
    assert base.digest() != changed_market.digest()


def test_fresh_cache_hit_returns_response_and_sets_cache_hit_and_served_at(tmp_path):
    now = datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc)
    cache = SearchCache(cache_dir=tmp_path, now_func=lambda: now)
    key = SearchCacheKey(
        provider="brave",
        query="AAPL latest news",
        ticker="AAPL",
        analysis_date="2026-05-08",
        market="us",
        language="en",
        purpose="fresh_news",
        max_results=5,
    )
    response = _response()

    cache.set(key, response)
    cached = cache.get(key)

    assert cached is not None
    assert cached.cache_hit
    assert cached.results[0].retrieved_at == response.results[0].retrieved_at
    assert cached.results[0].served_at == now


def test_stale_cache_after_twelve_hours_misses(tmp_path):
    first_now = datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc)
    key = SearchCacheKey(
        provider="brave",
        query="AAPL latest news",
        ticker="AAPL",
        analysis_date="2026-05-08",
        market="us",
        language="en",
        purpose="fresh_news",
        max_results=5,
    )
    SearchCache(cache_dir=tmp_path, now_func=lambda: first_now).set(key, _response())

    stale_cache = SearchCache(
        cache_dir=tmp_path,
        now_func=lambda: first_now + timedelta(hours=12, seconds=1),
    )

    assert stale_cache.get(key) is None
