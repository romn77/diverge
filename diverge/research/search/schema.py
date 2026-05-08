from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SearchPurpose = Literal["fresh_news", "sentiment", "risk", "catalyst", "default"]
SearchFreshnessStatus = Literal["fresh", "stale", "unknown"]


class SearchWarning(BaseModel):
    provider: str | None = None
    reason: str
    message: str


class SearchResult(BaseModel):
    id: str
    provider: str
    query: str
    title: str
    url: str
    canonical_url: str | None = None
    source: str | None = None
    snippet: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime
    served_at: datetime | None = None
    language: str | None = None
    market: str | None = None
    freshness_status: SearchFreshnessStatus = "unknown"
    relevance_score: float | None = None
    source_quality: Literal["known", "unknown", "low"] = "unknown"
    raw_provider_id: str | None = None


class SearchResponse(BaseModel):
    agent: str
    ticker: str
    analysis_date: str
    query: str
    purpose: SearchPurpose = "default"
    attempted_providers: list[str] = Field(default_factory=list)
    successful_provider: str | None = None
    fallback_used: bool = False
    cache_hit: bool = False
    results: list[SearchResult] = Field(default_factory=list)
    warnings: list[SearchWarning] = Field(default_factory=list)
    requested_at: datetime


def clamp_max_results(value: int | None) -> int:
    if value is None:
        return 5
    return max(1, min(5, int(value)))
