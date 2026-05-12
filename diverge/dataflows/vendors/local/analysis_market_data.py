from __future__ import annotations

import logging

from diverge.common.dates import offset_iso_date, parse_iso_date
from diverge.common.market_calendar import resolve_market_trading_date
from diverge.common.symbols import parse_and_normalize_cn_ticker, resolve_symbol_market
from diverge.data_layout import resolve_history_dir
from diverge.dataflows.cn_market_utils import (
    dataframe_to_standard_string,
    generate_indicator_report,
)
from diverge.dataflows.routes import history_source_kwargs_for_market
from diverge.market_data.history_cache import load_history_cache, slice_history_window
from diverge.market_data.price_history import fetch_ticker_history


INDICATOR_WARMUP_DAYS = 260
_CACHE_FALLBACK_NOTE = (
    "Data quality note: incremental price-history fetch failed, so this indicator "
    "was computed from cached local history only. Longer-window indicators may have "
    "limited warmup data."
)

logger = logging.getLogger(__name__)


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


def _effective_indicator_as_of_date(market: str, curr_date: str) -> str | None:
    curr_dt = parse_iso_date(curr_date)
    if curr_dt is None:
        return None
    trading_date = resolve_market_trading_date(market, curr_dt)
    return trading_date or curr_date


def _cached_indicator_frame(
    *,
    symbol: str,
    market: str,
    curr_date: str,
    look_back_days: int,
    original_error: Exception,
):
    effective_as_of = _effective_indicator_as_of_date(market, curr_date)
    if effective_as_of is None:
        raise original_error

    start_date = offset_iso_date(
        effective_as_of,
        -max(look_back_days, INDICATOR_WARMUP_DAYS),
    )
    cached_frame = load_history_cache(resolve_history_dir(), market, symbol)
    fallback_frame = slice_history_window(cached_frame, start_date, effective_as_of)
    if fallback_frame.empty:
        raise original_error

    logger.warning(
        "analysis_indicator_cache_fallback symbol=%s market=%s curr_date=%s "
        "cache_rows=%s error_type=%s",
        symbol,
        market,
        curr_date,
        len(fallback_frame),
        original_error.__class__.__name__,
    )
    return fallback_frame


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
    used_cache_fallback = False
    try:
        _, frame = fetch_ticker_history(
            history_symbol,
            market=market,
            as_of_date=curr_date,
            lookback_days=max(look_back_days, INDICATOR_WARMUP_DAYS),
            cache_dir=resolve_history_dir(),
            normalize_as_of_to_trading_day=True,
            **_history_source_kwargs(market),
        )
    except Exception as exc:
        frame = _cached_indicator_frame(
            symbol=history_symbol,
            market=market,
            curr_date=curr_date,
            look_back_days=look_back_days,
            original_error=exc,
        )
        used_cache_fallback = True

    report = generate_indicator_report(frame, indicator, curr_date, look_back_days)
    if used_cache_fallback:
        return f"{report}\n\n{_CACHE_FALLBACK_NOTE}"
    return report
