from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from diverge.agents.utils.tooling import tool
from diverge.research.search.providers.bocha import BochaSearchProvider
from diverge.research.search.providers.brave import BraveSearchProvider
from diverge.research.search.providers.tavily import TavilySearchProvider
from diverge.research.search.schema import SearchPurpose, SearchResponse, SearchWarning, clamp_max_results
from diverge.research.search.service import SearchService
from diverge.research.search.session import current_search_context, search_sessions


VALID_SEARCH_PURPOSES = {"fresh_news", "sentiment", "risk", "catalyst", "default"}
_SEARCH_SERVICE_FOR_TESTING = None


class WebSearchQuotaRepository:
    def get_summary(self) -> dict:
        from web.backend import auth, search_quota

        with auth.db_session() as db:
            return search_quota.get_search_quota_summary(db)

    def record_call(self, provider: str, *, success: bool, error: str | None = None) -> None:
        from web.backend import auth, search_quota

        with auth.db_session() as db:
            search_quota.record_search_provider_call(
                db,
                provider,
                success=success,
                error=error,
            )

    def disable_provider_until_month_end(self, provider: str, reason: str) -> None:
        from web.backend import auth, search_quota

        with auth.db_session() as db:
            search_quota.disable_provider_until_month_end(db, provider, reason)

    def disable_global_until_month_end(self, reason: str) -> None:
        from web.backend import auth, search_quota

        with auth.db_session() as db:
            search_quota.disable_global_until_month_end(db, reason)


def build_default_search_service() -> SearchService:
    return SearchService(
        providers={
            "brave": BraveSearchProvider(),
            "tavily": TavilySearchProvider(),
            "bocha": BochaSearchProvider(),
        },
        quota_repository=WebSearchQuotaRepository(),
    )


def set_search_service_for_testing(service) -> None:
    global _SEARCH_SERVICE_FOR_TESTING
    _SEARCH_SERVICE_FOR_TESTING = service


def clear_search_service_for_testing() -> None:
    global _SEARCH_SERVICE_FOR_TESTING
    _SEARCH_SERVICE_FOR_TESTING = None


def _get_search_service():
    return _SEARCH_SERVICE_FOR_TESTING or build_default_search_service()


def _normalize_purpose(value: str) -> SearchPurpose:
    candidate = str(value or "default").strip().lower()
    if candidate not in VALID_SEARCH_PURPOSES:
        return "default"
    return candidate  # type: ignore[return-value]


def _format_published(response_result) -> str:
    if response_result.published_at is None:
        return "unknown"
    return response_result.published_at.date().isoformat()


def format_search_response_markdown(response: SearchResponse) -> str:
    lines = [f"Web Search Evidence for query: {response.query}", ""]
    if response.results:
        for index, result in enumerate(response.results, start=1):
            source = result.source or result.provider
            lines.extend(
                [
                    f"{index}. {source} - {result.title}",
                    f"   Source: {source}",
                    f"   Published: {_format_published(result)}",
                    f"   URL: {result.url}",
                ]
            )
            if result.snippet:
                lines.append(f"   Snippet: {result.snippet}")
    else:
        lines.append("No web search results returned.")

    if response.warnings:
        lines.extend(["", "Warnings:"])
        for warning in response.warnings:
            prefix = f"{warning.provider}: " if warning.provider else ""
            lines.append(f"- {prefix}{warning.reason}: {warning.message}")
    return "\n".join(lines).strip()


def _missing_context_markdown(query: str) -> str:
    return format_search_response_markdown(
        SearchResponse(
            agent="unknown",
            ticker="unknown",
            analysis_date="unknown",
            query=query,
            requested_at=datetime.now(timezone.utc),
            warnings=[
                SearchWarning(
                    reason="search_context_missing",
                    message="Web Search context is unavailable.",
                )
            ],
        )
    )


@tool
def web_search_evidence(
    query: Annotated[str, "Search query"] = "",
    purpose: Annotated[str, "fresh_news, sentiment, risk, catalyst, or default"] = "default",
    max_results: Annotated[int, "Maximum results to return, clamped to 1..5"] = 5,
) -> str:
    """Return controlled Web Search evidence as Markdown for analyst use."""
    context = current_search_context.get()
    resolved_query = str(query or "").strip()
    resolved_purpose = _normalize_purpose(purpose)
    result_limit = clamp_max_results(max_results)

    if context is None:
        return _missing_context_markdown(resolved_query)

    session = search_sessions.get(context.analysis_run_id)
    if session is None:
        session = search_sessions.create(
            analysis_run_id=context.analysis_run_id,
            ticker=context.ticker,
            analysis_date=context.analysis_date,
        )

    allowed, warning = session.can_search(context.agent)
    if not allowed and warning is not None:
        response = session.warning_response(
            agent=context.agent,
            query=resolved_query,
            purpose=resolved_purpose,
            warning=warning,
        )
        session.record(response, count_budget=False)
        return format_search_response_markdown(response)

    try:
        response = _get_search_service().search_recent_evidence(
            agent=context.agent,
            ticker=context.ticker,
            analysis_date=context.analysis_date,
            query=resolved_query,
            purpose=resolved_purpose,
            market=context.market,
            language=context.language,
            max_results=result_limit,
        )
    except Exception as exc:
        response = session.warning_response(
            agent=context.agent,
            query=resolved_query,
            purpose=resolved_purpose,
            warning=SearchWarning(
                reason="search_service_error",
                message=str(exc) or exc.__class__.__name__,
            ),
        )

    session.record(response)
    return format_search_response_markdown(response)
