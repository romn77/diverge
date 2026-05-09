from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from diverge.research.search.cache import SearchCache, SearchCacheKey
from diverge.research.search.normalization import normalize_and_rank_results
from diverge.research.search.providers.base import SearchProvider, SearchProviderError
from diverge.research.search.query_builder import build_search_query
from diverge.research.search.routing import (
    available_provider_chain,
    provider_order_for_context,
)
from diverge.research.search.schema import (
    SearchPurpose,
    SearchResponse,
    SearchWarning,
    clamp_max_results,
)


class SearchQuotaRepository(Protocol):
    def get_summary(self) -> dict: ...

    def record_call(
        self, provider: str, *, success: bool, error: str | None = None
    ) -> None: ...

    def disable_provider_until_month_end(self, provider: str, reason: str) -> None: ...

    def disable_global_until_month_end(self, reason: str) -> None: ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SearchService:
    def __init__(
        self,
        *,
        providers: dict[str, SearchProvider],
        quota_repository: SearchQuotaRepository,
        cache: SearchCache | None = None,
    ) -> None:
        self.providers = providers
        self.quota_repository = quota_repository
        self.cache = cache or SearchCache()

    def search_recent_evidence(
        self,
        *,
        agent: str,
        ticker: str,
        analysis_date: str,
        query: str | None,
        purpose: SearchPurpose,
        market: str,
        language: str | None,
        max_results: int | None,
    ) -> SearchResponse:
        requested_at = _utcnow()
        result_limit = clamp_max_results(max_results)
        built_query = build_search_query(
            query,
            ticker=ticker,
            market=market,
            language=language,
            purpose=purpose,
        )
        summary = self.quota_repository.get_summary()
        if not (summary.get("global") or {}).get("enabled"):
            return self._warning_response(
                agent=agent,
                ticker=ticker,
                analysis_date=analysis_date,
                query=built_query,
                purpose=purpose,
                requested_at=requested_at,
                warning=SearchWarning(
                    reason="search_disabled",
                    message="Global Web Search is disabled.",
                ),
            )

        order = provider_order_for_context(market=market, language=language)
        provider_chain = [
            provider
            for provider in available_provider_chain(order, summary)
            if provider in self.providers
        ]
        if not provider_chain:
            self.quota_repository.disable_global_until_month_end(
                "all_providers_unavailable"
            )
            return self._warning_response(
                agent=agent,
                ticker=ticker,
                analysis_date=analysis_date,
                query=built_query,
                purpose=purpose,
                requested_at=requested_at,
                warning=SearchWarning(
                    reason="no_search_provider_available",
                    message="No configured Web Search provider is available.",
                ),
            )

        attempted: list[str] = []
        warnings: list[SearchWarning] = []
        monthly_disabled_attempts = 0
        for provider_name in provider_chain:
            cache_key = SearchCacheKey(
                provider=provider_name,
                query=built_query,
                ticker=ticker,
                analysis_date=analysis_date,
                market=market,
                language=language,
                purpose=purpose,
                max_results=result_limit,
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached.model_copy(
                    update={
                        "agent": agent,
                        "ticker": ticker,
                        "analysis_date": analysis_date,
                        "query": built_query,
                        "purpose": purpose,
                        "attempted_providers": [],
                    }
                )

            provider = self.providers[provider_name]
            attempted.append(provider_name)
            try:
                provider_results = provider.search(
                    built_query,
                    max_results=result_limit,
                    language=language,
                    market=market,
                )
            except SearchProviderError as exc:
                self.quota_repository.record_call(
                    provider_name,
                    success=False,
                    error=exc.reason,
                )
                warnings.append(
                    SearchWarning(
                        provider=provider_name,
                        reason=exc.reason,
                        message=exc.message,
                    )
                )
                if exc.monthly_disable:
                    monthly_disabled_attempts += 1
                    self.quota_repository.disable_provider_until_month_end(
                        provider_name,
                        exc.reason,
                    )
                continue
            except Exception as exc:  # pragma: no cover - defensive adapter boundary
                self.quota_repository.record_call(
                    provider_name,
                    success=False,
                    error=exc.__class__.__name__,
                )
                warnings.append(
                    SearchWarning(
                        provider=provider_name,
                        reason="provider_exception",
                        message=str(exc) or exc.__class__.__name__,
                    )
                )
                continue

            self.quota_repository.record_call(provider_name, success=True)
            results = normalize_and_rank_results(
                provider_results,
                max_results=result_limit,
            )
            if not results:
                warnings.append(
                    SearchWarning(
                        provider=provider_name,
                        reason="empty_results",
                        message=f"{provider_name} returned no usable results.",
                    )
                )
                continue

            response = SearchResponse(
                agent=agent,
                ticker=ticker,
                analysis_date=analysis_date,
                query=built_query,
                purpose=purpose,
                attempted_providers=list(attempted),
                successful_provider=provider_name,
                fallback_used=len(attempted) > 1,
                results=results,
                warnings=warnings,
                requested_at=requested_at,
            )
            self.cache.set(cache_key, response)
            return response

        if monthly_disabled_attempts == len(provider_chain):
            self.quota_repository.disable_global_until_month_end(
                "all_providers_unavailable"
            )
        return SearchResponse(
            agent=agent,
            ticker=ticker,
            analysis_date=analysis_date,
            query=built_query,
            purpose=purpose,
            attempted_providers=attempted,
            fallback_used=len(attempted) > 1,
            warnings=warnings
            or [
                SearchWarning(
                    reason="no_search_results",
                    message="Web Search returned no usable evidence.",
                )
            ],
            requested_at=requested_at,
        )

    def _warning_response(
        self,
        *,
        agent: str,
        ticker: str,
        analysis_date: str,
        query: str,
        purpose: SearchPurpose,
        requested_at: datetime,
        warning: SearchWarning,
    ) -> SearchResponse:
        return SearchResponse(
            agent=agent,
            ticker=ticker,
            analysis_date=analysis_date,
            query=query,
            purpose=purpose,
            warnings=[warning],
            requested_at=requested_at,
        )
