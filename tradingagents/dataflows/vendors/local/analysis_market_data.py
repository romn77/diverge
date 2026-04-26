from __future__ import annotations

from datetime import datetime

from tradingagents.data_layout import resolve_history_dir
from tradingagents.screener.market_data import fetch_ticker_history, resolve_history_market

from ... import vendor_usage
from ...cn_market_utils import (
    dataframe_to_standard_string,
    generate_indicator_report,
    parse_and_normalize_cn_ticker,
)


INDICATOR_WARMUP_DAYS = 260


def _canonical_history_symbol(symbol: str, market: str) -> str:
    normalized = str(symbol).strip()
    if market == "cn":
        return parse_and_normalize_cn_ticker(normalized)["tushare"]
    if market == "us":
        return normalized.upper()
    return normalized


def _core_stock_route(market: str) -> list[str]:
    return vendor_usage.get_data_source_route(
        module="analysis",
        market=market,
        category="core_stock_apis",
    )


def _history_source_kwargs(market: str) -> dict:
    route = _core_stock_route(market)
    if market == "cn":
        source_chain = route or ["tushare", "akshare"]
        return {
            "cn_data_source": source_chain[0],
            "cn_data_source_fallbacks": source_chain[1:],
        }
    if market == "us":
        source_chain = route or ["massive"]
        return {
            "us_data_source": source_chain[0],
            "us_data_source_fallbacks": source_chain[1:],
        }
    return {}


def _lookback_days(start_date: str, end_date: str) -> int:
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    if end_dt < start_dt:
        raise ValueError("end_date must be on or after start_date")
    return max((end_dt - start_dt).days, 1)


def get_stock_data_from_history(
    symbol: str,
    start_date: str,
    end_date: str,
) -> str:
    market = resolve_history_market(symbol)
    history_symbol = _canonical_history_symbol(symbol, market)
    resolved_market, frame = fetch_ticker_history(
        history_symbol,
        market=market,
        as_of_date=end_date,
        lookback_days=_lookback_days(start_date, end_date),
        cache_dir=resolve_history_dir(),
        **_history_source_kwargs(market),
    )
    display_symbol = history_symbol if resolved_market == "cn" else str(symbol).strip().upper()
    return dataframe_to_standard_string(
        frame,
        f"Stock data for {display_symbol} from {start_date} to {end_date}",
    )


def get_local_indicator(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
) -> str:
    market = resolve_history_market(symbol)
    history_symbol = _canonical_history_symbol(symbol, market)
    _, frame = fetch_ticker_history(
        history_symbol,
        market=market,
        as_of_date=curr_date,
        lookback_days=max(look_back_days, INDICATOR_WARMUP_DAYS),
        cache_dir=resolve_history_dir(),
        **_history_source_kwargs(market),
    )
    return generate_indicator_report(frame, indicator, curr_date, look_back_days)
