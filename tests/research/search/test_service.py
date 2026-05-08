from datetime import datetime, timezone

from diverge.research.search.cache import SearchCache, SearchCacheKey
from diverge.research.search.providers.base import (
    SearchProviderEmptyResult,
    SearchProviderQuotaError,
    SearchProviderTemporaryError,
)
from diverge.research.search.schema import SearchResponse, SearchResult
from diverge.research.search.service import SearchService


class FakeProvider:
    def __init__(self, name: str, result_urls: list[str] | None = None, error=None):
        self.name = name
        self.result_urls = result_urls or [f"https://example.com/{name}"]
        self.error = error
        self.calls: list[dict] = []

    def search(self, query: str, *, max_results: int, language: str | None, market: str | None):
        self.calls.append(
            {
                "query": query,
                "max_results": max_results,
                "language": language,
                "market": market,
            }
        )
        if self.error:
            raise self.error
        return [
            SearchResult(
                id=f"{self.name}-{index}",
                provider=self.name,
                query=query,
                title=f"{self.name} result {index}",
                url=url,
                snippet="Snippet",
                published_at=datetime(2026, 5, 8, tzinfo=timezone.utc)
                if index == 0
                else None,
                retrieved_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
                relevance_score=1.0 - index / 10,
            )
            for index, url in enumerate(self.result_urls)
        ][:max_results]


class FakeQuotaRepository:
    def __init__(self, summary: dict):
        self.summary = summary
        self.recorded: list[tuple[str, bool, str | None]] = []
        self.disabled_providers: list[tuple[str, str]] = []
        self.global_disabled: list[str] = []

    def get_summary(self) -> dict:
        return self.summary

    def record_call(self, provider: str, *, success: bool, error: str | None = None) -> None:
        self.recorded.append((provider, success, error))

    def disable_provider_until_month_end(self, provider: str, reason: str) -> None:
        self.disabled_providers.append((provider, reason))

    def disable_global_until_month_end(self, reason: str) -> None:
        self.global_disabled.append(reason)


def _summary(global_enabled: bool = True, **provider_overrides):
    providers = []
    for provider in ("brave", "tavily", "bocha"):
        payload = {
            "provider": provider,
            "enabled": True,
            "key_status": "configured",
            "hard_cap_reached": False,
            "remaining_to_hard_cap": 10,
        }
        payload.update(provider_overrides.get(provider, {}))
        providers.append(payload)
    return {"global": {"enabled": global_enabled}, "providers": providers}


def _service(repo, providers=None, cache=None):
    resolved_providers = providers or {
        "brave": FakeProvider("brave"),
        "tavily": FakeProvider("tavily"),
        "bocha": FakeProvider("bocha"),
    }
    return SearchService(
        providers=resolved_providers,
        quota_repository=repo,
        cache=cache or SearchCache(cache_dir="/tmp/nonexistent-search-cache-tests"),
    )


def test_global_disabled_returns_warning_without_provider_calls(tmp_path):
    repo = FakeQuotaRepository(_summary(global_enabled=False))
    brave = FakeProvider("brave")

    response = _service(
        repo,
        providers={"brave": brave},
        cache=SearchCache(cache_dir=tmp_path),
    ).search_recent_evidence(
        agent="News Analyst",
        ticker="AAPL",
        analysis_date="2026-05-08",
        query="AAPL",
        purpose="fresh_news",
        market="us",
        language="en",
        max_results=5,
    )

    assert response.warnings[0].reason == "search_disabled"
    assert brave.calls == []
    assert repo.recorded == []


def test_unavailable_providers_are_skipped_before_request(tmp_path):
    repo = FakeQuotaRepository(
        _summary(
            brave={"enabled": False},
            tavily={"key_status": "missing"},
            bocha={"hard_cap_reached": True},
        )
    )
    brave = FakeProvider("brave")
    tavily = FakeProvider("tavily")

    response = _service(
        repo,
        providers={"brave": brave, "tavily": tavily},
        cache=SearchCache(cache_dir=tmp_path),
    ).search_recent_evidence(
        agent="News Analyst",
        ticker="AAPL",
        analysis_date="2026-05-08",
        query="AAPL",
        purpose="fresh_news",
        market="us",
        language="en",
        max_results=5,
    )

    assert response.warnings[0].reason == "no_search_provider_available"
    assert brave.calls == []
    assert tavily.calls == []
    assert repo.recorded == []
    assert repo.global_disabled == ["all_providers_unavailable"]


def test_cache_hit_skips_provider_and_quota(tmp_path):
    repo = FakeQuotaRepository(_summary())
    cache = SearchCache(cache_dir=tmp_path)
    query = "AAPL latest news stock"
    key = SearchCacheKey(
        provider="brave",
        query=query,
        ticker="AAPL",
        analysis_date="2026-05-08",
        market="us",
        language="en",
        purpose="fresh_news",
        max_results=5,
    )
    cache.set(
        key,
        SearchResponse(
            agent="News Analyst",
            ticker="AAPL",
            analysis_date="2026-05-08",
            query=query,
            requested_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
            successful_provider="brave",
            results=[
                SearchResult(
                    id="cached",
                    provider="brave",
                    query=query,
                    title="Cached",
                    url="https://example.com/cached",
                    retrieved_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
                )
            ],
        ),
    )
    brave = FakeProvider("brave")

    response = _service(
        repo,
        providers={"brave": brave},
        cache=cache,
    ).search_recent_evidence(
        agent="Social Analyst",
        ticker="AAPL",
        analysis_date="2026-05-08",
        query="AAPL",
        purpose="fresh_news",
        market="us",
        language="en",
        max_results=5,
    )

    assert response.cache_hit
    assert response.agent == "Social Analyst"
    assert brave.calls == []
    assert repo.recorded == []


def test_primary_failure_falls_back_and_records_each_external_request(tmp_path):
    repo = FakeQuotaRepository(_summary())
    brave = FakeProvider("brave", error=SearchProviderTemporaryError("timeout", "timeout"))
    tavily = FakeProvider("tavily")

    response = _service(
        repo,
        providers={"brave": brave, "tavily": tavily},
        cache=SearchCache(cache_dir=tmp_path),
    ).search_recent_evidence(
        agent="News Analyst",
        ticker="AAPL",
        analysis_date="2026-05-08",
        query="AAPL",
        purpose="fresh_news",
        market="us",
        language="en",
        max_results=5,
    )

    assert response.successful_provider == "tavily"
    assert response.fallback_used
    assert repo.recorded[0][0:2] == ("brave", False)
    assert repo.recorded[1][0:2] == ("tavily", True)


def test_monthly_disable_error_disables_provider_until_month_end(tmp_path):
    repo = FakeQuotaRepository(_summary())
    brave = FakeProvider(
        "brave",
        error=SearchProviderQuotaError("quota_exhausted", "quota exhausted"),
    )
    tavily = FakeProvider("tavily")

    _service(
        repo,
        providers={"brave": brave, "tavily": tavily},
        cache=SearchCache(cache_dir=tmp_path),
    ).search_recent_evidence(
        agent="News Analyst",
        ticker="AAPL",
        analysis_date="2026-05-08",
        query="AAPL",
        purpose="fresh_news",
        market="us",
        language="en",
        max_results=5,
    )

    assert repo.disabled_providers == [("brave", "quota_exhausted")]


def test_empty_and_temporary_errors_fallback_without_monthly_disable(tmp_path):
    repo = FakeQuotaRepository(_summary())
    brave = FakeProvider(
        "brave",
        error=SearchProviderEmptyResult("empty_results", "empty"),
    )
    tavily = FakeProvider(
        "tavily",
        error=SearchProviderTemporaryError("rate_limited", "rate limited"),
    )

    response = _service(
        repo,
        providers={"brave": brave, "tavily": tavily},
        cache=SearchCache(cache_dir=tmp_path),
    ).search_recent_evidence(
        agent="News Analyst",
        ticker="AAPL",
        analysis_date="2026-05-08",
        query="AAPL",
        purpose="fresh_news",
        market="us",
        language="en",
        max_results=5,
    )

    assert response.warnings
    assert repo.disabled_providers == []
    assert repo.recorded == [
        ("brave", False, "empty_results"),
        ("tavily", False, "rate_limited"),
    ]


def test_results_are_normalized_ranked_deduped_and_clamped(tmp_path):
    repo = FakeQuotaRepository(_summary())
    brave = FakeProvider(
        "brave",
        result_urls=[
            "https://example.com/a?utm_source=x",
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
            "https://example.com/d",
            "https://example.com/e",
        ],
    )

    response = _service(
        repo,
        providers={"brave": brave},
        cache=SearchCache(cache_dir=tmp_path),
    ).search_recent_evidence(
        agent="News Analyst",
        ticker="AAPL",
        analysis_date="2026-05-08",
        query="AAPL",
        purpose="fresh_news",
        market="us",
        language="en",
        max_results=5,
    )

    assert 0 < len(response.results) <= 5
    assert len({result.canonical_url for result in response.results}) == len(response.results)
    assert response.results[0].published_at is not None
