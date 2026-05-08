from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

from diverge.research.search.providers.base import (
    SearchProviderEmptyResult,
    parse_provider_datetime,
    raise_for_http_status,
    require_api_key,
    response_json,
)
from diverge.research.search.schema import SearchResult, clamp_max_results


class TavilySearchProvider:
    name = "tavily"
    endpoint = "https://api.tavily.com/search"

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key if api_key is not None else os.getenv("TAVILY_API_KEY")
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(10.0, connect=3.0, read=8.0)
        )

    def search(
        self,
        query: str,
        *,
        max_results: int,
        language: str | None,
        market: str | None,
    ) -> list[SearchResult]:
        api_key = require_api_key(self.api_key, self.name)
        count = clamp_max_results(max_results)
        response = self.client.post(
            self.endpoint,
            json={
                "api_key": api_key,
                "query": query,
                "max_results": count,
                "include_answer": False,
                "include_raw_content": False,
            },
        )
        raise_for_http_status(self.name, response.status_code, getattr(response, "text", ""))
        payload = response_json(self.name, response)
        raw_results = payload.get("results", [])
        results = [
            self._map_result(item, index=index, query=query, language=language, market=market)
            for index, item in enumerate(raw_results)
            if isinstance(item, dict)
        ]
        if not results:
            raise SearchProviderEmptyResult("empty_results", "tavily returned no results")
        return results[:count]

    def _map_result(
        self,
        item: dict[str, Any],
        *,
        index: int,
        query: str,
        language: str | None,
        market: str | None,
    ) -> SearchResult:
        return SearchResult(
            id=f"tavily-{index}",
            provider=self.name,
            query=query,
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
            source=str(item.get("source")) if item.get("source") else None,
            snippet=str(item.get("content") or item.get("snippet") or ""),
            published_at=parse_provider_datetime(
                item.get("published_date") or item.get("published_at")
            ),
            retrieved_at=datetime.now(timezone.utc),
            language=language,
            market=market,
            relevance_score=float(item["score"]) if item.get("score") is not None else None,
            raw_provider_id=str(item.get("id")) if item.get("id") else None,
        )
