from __future__ import annotations

from typing import Iterable

from diverge.dataflows import vendor_usage

CORE_STOCK_CATEGORY = "core_stock_apis"
DEFAULT_ROUTE_CHAINS: dict[tuple[str, str], list[str]] = {
    ("analysis", "cn"): ["tushare", "akshare"],
    ("analysis", "us"): ["massive"],
    ("screener", "cn"): ["tushare"],
    ("screener", "us"): ["massive"],
}


def source_chain_for_market(
    *,
    module: str,
    market: str,
    category: str = CORE_STOCK_CATEGORY,
    fallback: Iterable[str] | None = None,
) -> list[str]:
    normalized_module = str(module).strip().lower()
    normalized_market = str(market).strip().lower()
    route = vendor_usage.get_data_source_route(
        module=normalized_module,
        market=normalized_market,
        category=category,
    )
    if route:
        return list(route)
    return list(
        fallback or DEFAULT_ROUTE_CHAINS.get((normalized_module, normalized_market), [])
    )


def history_source_kwargs_for_market(*, module: str, market: str) -> dict[str, object]:
    normalized_market = str(market).strip().lower()
    chain = source_chain_for_market(module=module, market=normalized_market)
    if normalized_market == "cn":
        source_chain = chain or ["tushare"]
        return {
            "cn_data_source": source_chain[0],
            "cn_data_source_fallbacks": source_chain[1:],
        }
    if normalized_market == "us":
        source_chain = chain or ["massive"]
        return {
            "us_data_source": source_chain[0],
            "us_data_source_fallbacks": source_chain[1:],
        }
    return {}


def dual_market_history_source_kwargs(*, module: str) -> dict[str, object]:
    sources: dict[str, object] = {}
    sources.update(history_source_kwargs_for_market(module=module, market="cn"))
    sources.update(history_source_kwargs_for_market(module=module, market="us"))
    return sources
