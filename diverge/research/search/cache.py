from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from diverge.default_config import DEFAULT_CONFIG
from diverge.research.search.schema import (
    SearchPurpose,
    SearchResponse,
    clamp_max_results,
)


SEARCH_CACHE_TTL_SECONDS = 43_200


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> datetime:
    candidate = str(value)
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class SearchCacheKey(BaseModel):
    provider: str
    query: str
    ticker: str
    analysis_date: str
    market: str | None = None
    language: str | None = None
    purpose: SearchPurpose = "default"
    max_results: int = 5

    def digest(self) -> str:
        payload = self.model_dump(mode="json")
        payload["provider"] = str(payload["provider"]).strip().lower()
        payload["query"] = " ".join(str(payload["query"]).split())
        payload["ticker"] = str(payload["ticker"]).strip().upper()
        payload["max_results"] = clamp_max_results(int(payload["max_results"]))
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class SearchCache:
    def __init__(
        self,
        cache_dir: Path | str | None = None,
        *,
        now_func: Callable[[], datetime] | None = None,
    ) -> None:
        self.cache_dir = Path(
            cache_dir or Path(DEFAULT_CONFIG["data_cache_dir"]) / "search"
        )
        self.now_func = now_func or _utcnow

    def _path(self, key: SearchCacheKey) -> Path:
        return self.cache_dir / f"{key.digest()}.json"

    def _now(self) -> datetime:
        value = self.now_func()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def get(self, key: SearchCacheKey) -> SearchResponse | None:
        path = self._path(key)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            cached_at = _parse_datetime(payload["cached_at"])
            if (self._now() - cached_at).total_seconds() > SEARCH_CACHE_TTL_SECONDS:
                return None
            response = SearchResponse.model_validate(payload["response"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

        served_at = self._now()
        return response.model_copy(
            update={
                "cache_hit": True,
                "results": [
                    result.model_copy(update={"served_at": served_at})
                    for result in response.results
                ],
            }
        )

    def set(self, key: SearchCacheKey, response: SearchResponse) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "cached_at": self._now().isoformat(),
            "response": response.model_dump(mode="json"),
        }
        self._path(key).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
