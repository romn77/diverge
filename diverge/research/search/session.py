from __future__ import annotations

import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from diverge.research.search.normalization import canonicalize_url
from diverge.research.search.schema import SearchResponse, SearchResult, SearchWarning


class SearchBudget(BaseModel):
    per_analysis_max_queries: int = 4
    per_agent_max_queries: int = 2
    per_query_max_results: int = 5


class SearchToolContext(BaseModel):
    analysis_run_id: str
    agent: str
    ticker: str
    analysis_date: str
    market: str = "us"
    language: str | None = None


current_search_context: ContextVar[SearchToolContext | None] = ContextVar(
    "current_search_context",
    default=None,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SearchSession:
    def __init__(
        self,
        *,
        analysis_run_id: str,
        ticker: str,
        analysis_date: str,
        budget: SearchBudget | None = None,
    ) -> None:
        self.analysis_run_id = analysis_run_id
        self.ticker = ticker
        self.analysis_date = analysis_date
        self.budget = budget or SearchBudget()
        self.calls: list[SearchResponse] = []
        self.used_queries = 0
        self.used_by_agent: dict[str, int] = {}
        self._lock = threading.RLock()

    def can_search(self, agent: str) -> tuple[bool, SearchWarning | None]:
        with self._lock:
            if self.used_queries >= self.budget.per_analysis_max_queries:
                return (
                    False,
                    SearchWarning(
                        reason="analysis_budget_exhausted",
                        message="Web Search budget exhausted for this analysis.",
                    ),
                )
            if self.used_by_agent.get(agent, 0) >= self.budget.per_agent_max_queries:
                return (
                    False,
                    SearchWarning(
                        reason="agent_budget_exhausted",
                        message="Web Search budget exhausted for this analyst.",
                    ),
                )
            return True, None

    def warning_response(
        self,
        *,
        agent: str,
        query: str,
        warning: SearchWarning,
        purpose: str = "default",
    ) -> SearchResponse:
        return SearchResponse(
            agent=agent,
            ticker=self.ticker,
            analysis_date=self.analysis_date,
            query=query,
            purpose=purpose,  # type: ignore[arg-type]
            warnings=[warning],
            requested_at=_utcnow(),
        )

    def record(self, response: SearchResponse, *, count_budget: bool = True) -> None:
        with self._lock:
            self.calls.append(response)
            if count_budget:
                self.used_queries += 1
                self.used_by_agent[response.agent] = (
                    self.used_by_agent.get(response.agent, 0) + 1
                )

    def unique_results(self) -> list[SearchResult]:
        seen: set[str] = set()
        unique: list[SearchResult] = []
        with self._lock:
            for call in self.calls:
                for result in call.results:
                    canonical_url = canonicalize_url(result.canonical_url or result.url)
                    if not canonical_url or canonical_url in seen:
                        continue
                    seen.add(canonical_url)
                    unique.append(
                        result.model_copy(update={"canonical_url": canonical_url})
                    )
        return unique


class SearchSessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, SearchSession] = {}
        self._lock = threading.RLock()

    def create(
        self,
        *,
        analysis_run_id: str,
        ticker: str,
        analysis_date: str,
        budget: SearchBudget | None = None,
        **_: Any,
    ) -> SearchSession:
        with self._lock:
            session = SearchSession(
                analysis_run_id=analysis_run_id,
                ticker=ticker,
                analysis_date=analysis_date,
                budget=budget,
            )
            self._sessions[analysis_run_id] = session
            return session

    def get(self, analysis_run_id: str) -> SearchSession | None:
        with self._lock:
            return self._sessions.get(analysis_run_id)

    def pop(self, analysis_run_id: str) -> SearchSession | None:
        with self._lock:
            return self._sessions.pop(analysis_run_id, None)


search_sessions = SearchSessionRegistry()
