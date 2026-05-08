from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from diverge.research.search.schema import SearchResult, clamp_max_results


TRACKING_PARAMS = {"fbclid", "gclid", "ref", "source"}


def canonicalize_url(url: str) -> str:
    candidate = str(url or "").strip()
    if not candidate:
        return ""

    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in TRACKING_PARAMS:
            continue
        query_items.append((key, value))

    query = urlencode(sorted(query_items))
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, query, ""))


def _timestamp(value: datetime | None) -> float:
    if value is None:
        return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _completeness_score(result: SearchResult) -> int:
    title_length = len((result.title or "").strip())
    snippet_length = len((result.snippet or "").strip())
    return title_length + snippet_length


def _dedupe_choice_key(result: SearchResult) -> tuple[float, float, int, int]:
    return (
        _timestamp(result.published_at),
        float(result.relevance_score or 0.0),
        1 if result.source else 0,
        _completeness_score(result),
    )


def _rank_key(result: SearchResult) -> tuple[int, int, float, float, int, int]:
    return (
        1 if result.freshness_status == "fresh" else 0,
        1 if result.published_at is not None else 0,
        _timestamp(result.published_at),
        float(result.relevance_score or 0.0),
        1 if result.source else 0,
        _completeness_score(result),
    )


def _has_content(result: SearchResult) -> bool:
    return bool((result.title or "").strip() or (result.snippet or "").strip())


def normalize_and_rank_results(
    results: list[SearchResult],
    *,
    max_results: int,
) -> list[SearchResult]:
    deduped: dict[str, SearchResult] = {}
    for result in results:
        canonical_url = canonicalize_url(result.canonical_url or result.url)
        if not canonical_url or not _has_content(result):
            continue

        normalized = result.model_copy(update={"canonical_url": canonical_url})
        existing = deduped.get(canonical_url)
        if existing is None or _dedupe_choice_key(normalized) > _dedupe_choice_key(existing):
            deduped[canonical_url] = normalized

    return sorted(deduped.values(), key=_rank_key, reverse=True)[
        : clamp_max_results(max_results)
    ]
