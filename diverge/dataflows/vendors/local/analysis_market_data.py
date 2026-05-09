from __future__ import annotations

from diverge.common.dates import parse_iso_date
from diverge.common.symbols import parse_and_normalize_cn_ticker, resolve_symbol_market
from diverge.data_layout import resolve_history_dir
from diverge.dataflows.cn_market_utils import (
    dataframe_to_standard_string,
    generate_indicator_report,
)
from diverge.dataflows.routes import history_source_kwargs_for_market
from diverge.market_data.price_history import fetch_ticker_history


INDICATOR_WARMUP_DAYS = 260


def _canonical_history_symbol(symbol: str, market: str) -> str:
    normalized = str(symbol).strip()
    if market == "cn":
        return parse_and_normalize_cn_ticker(normalized)["tushare"]
    if market == "us":
        return normalized.upper()
    return normalized


def _history_source_kwargs(market: str) -> dict:
    return history_source_kwargs_for_market(module="analysis", market=market)


def _lookback_days(start_date: str, end_date: str) -> int:
    start_dt = parse_iso_date(start_date)
    end_dt = parse_iso_date(end_date)
    if start_dt is None or end_dt is None:
        raise ValueError("start_date and end_date must use YYYY-MM-DD format")
    if end_dt < start_dt:
        raise ValueError("end_date must be on or after start_date")
    return max((end_dt - start_dt).days, 1)


def get_stock_data_from_history(
    symbol: str,
    start_date: str,
    end_date: str,
) -> str:
    market = resolve_symbol_market(symbol)
    history_symbol = _canonical_history_symbol(symbol, market)
    resolved_market, frame = fetch_ticker_history(
        history_symbol,
        market=market,
        as_of_date=end_date,
        lookback_days=_lookback_days(start_date, end_date),
        cache_dir=resolve_history_dir(),
        normalize_as_of_to_trading_day=True,
        **_history_source_kwargs(market),
    )
    display_symbol = (
        history_symbol if resolved_market == "cn" else str(symbol).strip().upper()
    )
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
    market = resolve_symbol_market(symbol)
    history_symbol = _canonical_history_symbol(symbol, market)
    _, frame = fetch_ticker_history(
        history_symbol,
        market=market,
        as_of_date=curr_date,
        lookback_days=max(look_back_days, INDICATOR_WARMUP_DAYS),
        cache_dir=resolve_history_dir(),
        normalize_as_of_to_trading_day=True,
        **_history_source_kwargs(market),
    )
    return generate_indicator_report(frame, indicator, curr_date, look_back_days)
