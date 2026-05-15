from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from diverge.market_brief.schema import MarketBriefMarket, MarketBriefSource


DEFAULT_ALLOWED_DOMAINS = (
    "sse.com.cn",
    "szse.cn",
    "pbc.gov.cn",
    "csrc.gov.cn",
    "stats.gov.cn",
    "mof.gov.cn",
    "ndrc.gov.cn",
    "mofcom.gov.cn",
    "reuters.com",
    "apnews.com",
)

MARKET_QUERY_TERMS: dict[MarketBriefMarket, str] = {
    "cn": "A shares China market policy liquidity earnings premarket",
    "us": "US stocks S&P 500 Nasdaq Federal Reserve Treasury yields premarket",
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_csv_env(name: str, default: tuple[str, ...]) -> list[str]:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return list(default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _to_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
            return dumped if isinstance(dumped, dict) else None
        except Exception:
            return None
    return None


def _extract_sources_from_openai_response(response: Any) -> list[MarketBriefSource]:
    sources: list[MarketBriefSource] = []
    seen_urls: set[str] = set()

    def visit(value: Any) -> None:
        payload = _to_dict(value)
        if payload is None:
            if isinstance(value, list):
                for item in value:
                    visit(item)
            return

        url = payload.get("url")
        title = payload.get("title") or payload.get("name")
        if isinstance(url, str) and url.strip() and url not in seen_urls:
            seen_urls.add(url)
            sources.append(
                MarketBriefSource(
                    title=str(title or url).strip(),
                    url=url.strip(),
                    source=str(payload.get("source") or "").strip() or None,
                    provider="openai_web_search",
                    published_at=(
                        str(payload.get("published_at")).strip()
                        if payload.get("published_at")
                        else None
                    ),
                    retrieved_at=_utc_iso(),
                    snippet=str(payload.get("snippet") or "").strip() or None,
                )
            )

        for child in payload.values():
            if isinstance(child, (dict, list)) or _to_dict(child) is not None:
                visit(child)

    visit(response)
    return sources


def collect_openai_web_search_sources(
    *,
    markets: list[MarketBriefMarket],
    trading_day: str | None,
    output_language: str,
    max_results: int = 6,
) -> list[MarketBriefSource]:
    if not os.environ.get("OPENAI_API_KEY"):
        return []

    try:
        from openai import OpenAI
    except Exception:
        return []

    allowed_domains = _split_csv_env(
        "MARKET_BRIEF_WEB_SEARCH_ALLOWED_DOMAINS",
        DEFAULT_ALLOWED_DOMAINS,
    )
    market_terms = "; ".join(MARKET_QUERY_TERMS[market] for market in markets)
    prompt = (
        "Find fresh, source-backed premarket market news for a Diverge market "
        f"brief. Markets: {', '.join(markets)}. Trading day: {trading_day or 'auto'}. "
        f"Focus terms: {market_terms}. Return concise evidence in {output_language}. "
        "Prioritize exchange, regulator, central bank, official statistics, and "
        "major wire sources."
    )

    tool: dict[str, Any] = {
        "type": "web_search",
        "search_context_size": os.environ.get(
            "MARKET_BRIEF_WEB_SEARCH_CONTEXT_SIZE",
            "high",
        ),
    }
    if allowed_domains:
        tool["filters"] = {"allowed_domains": allowed_domains}

    client = OpenAI()
    try:
        response = client.responses.create(
            model=os.environ.get("MARKET_BRIEF_OPENAI_MODEL", "gpt-5.4-mini"),
            tools=[tool],
            tool_choice="required",
            include=["web_search_call.action.sources"],
            input=prompt,
        )
    except Exception:
        return []

    return _extract_sources_from_openai_response(response)[:max_results]


def collect_existing_search_service_sources(
    *,
    markets: list[MarketBriefMarket],
    trading_day: str | None,
    output_language: str,
    max_results: int = 6,
) -> list[MarketBriefSource]:
    try:
        from diverge.agents.utils.search_tools import build_default_search_service
    except Exception:
        return []

    sources: list[MarketBriefSource] = []
    seen_urls: set[str] = set()
    per_market_limit = max(1, min(3, max_results))
    for market in markets:
        try:
            response = build_default_search_service().search_recent_evidence(
                agent="market_brief",
                ticker="MARKET_BRIEF",
                analysis_date=trading_day or datetime.now().date().isoformat(),
                query=MARKET_QUERY_TERMS[market],
                purpose="fresh_news",
                market=market,
                language=output_language,
                max_results=per_market_limit,
            )
        except Exception:
            continue

        for result in response.results:
            if result.url in seen_urls:
                continue
            seen_urls.add(result.url)
            sources.append(
                MarketBriefSource(
                    title=result.title,
                    url=result.url,
                    source=result.source,
                    provider=result.provider,
                    published_at=(
                        result.published_at.isoformat() if result.published_at else None
                    ),
                    retrieved_at=result.retrieved_at.isoformat(),
                    market=market,
                    snippet=result.snippet,
                )
            )
            if len(sources) >= max_results:
                return sources
    return sources


def collect_web_search_sources(
    *,
    markets: list[MarketBriefMarket],
    trading_day: str | None,
    output_language: str,
    max_results: int = 6,
) -> list[MarketBriefSource]:
    provider = (
        os.environ.get("MARKET_BRIEF_WEB_SEARCH_PROVIDER", "auto").strip().lower()
    )
    if provider in {"none", "disabled", "off"}:
        return []

    if provider in {"auto", "openai"}:
        sources = collect_openai_web_search_sources(
            markets=markets,
            trading_day=trading_day,
            output_language=output_language,
            max_results=max_results,
        )
        if sources or provider == "openai":
            return sources

    if provider in {"auto", "search_service", "configured"}:
        return collect_existing_search_service_sources(
            markets=markets,
            trading_day=trading_day,
            output_language=output_language,
            max_results=max_results,
        )
    return []
