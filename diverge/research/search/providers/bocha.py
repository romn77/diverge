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


class BochaSearchProvider:
    name = "bocha"
    endpoint = "https://api.bochaai.com/v1/web-search"

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key if api_key is not None else os.getenv("BOCHA_API_KEY")
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
            headers={"Authorization": f"Bearer {api_key}"},
            json={"query": query, "count": count},
        )
        raise_for_http_status(self.name, response.status_code, getattr(response, "text", ""))
        payload = response_json(self.name, response)
        raw_results = (
            payload.get("data", {})
            .get("webPages", {})
            .get("value", [])
        )
        results = [
            self._map_result(item, index=index, query=query, language=language, market=market)
            for index, item in enumerate(raw_results)
            if isinstance(item, dict)
        ]
        if not results:
            raise SearchProviderEmptyResult("empty_results", "bocha returned no results")
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
            id=f"bocha-{index}",
            provider=self.name,
            query=query,
            title=str(item.get("name") or item.get("title") or ""),
            url=str(item.get("url") or ""),
            source=str(item.get("siteName") or item.get("source")) if item.get("siteName") or item.get("source") else None,
            snippet=str(item.get("snippet") or item.get("summary") or ""),
            published_at=parse_provider_datetime(
                item.get("datePublished") or item.get("published_at")
            ),
            retrieved_at=datetime.now(timezone.utc),
            language=language,
            market=market,
            raw_provider_id=str(item.get("id")) if item.get("id") else None,
        )
