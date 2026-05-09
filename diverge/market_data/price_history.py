from __future__ import annotations

from pathlib import Path
from typing import Any

from diverge.common.dates import offset_iso_date
from diverge.common.market_calendar import resolve_market_trading_date
from diverge.market_data.history_cache import (
    classify_history_cache_coverage,
    history_cache_path,
    load_history_cache,
    slice_history_window,
)


def load_local_price_window(
    *,
    history_dir: str | Path,
    market: str,
    symbol: str,
    as_of_date: str,
    lookback_days: int,
    normalize_to_trading_day: bool = True,
) -> dict[str, Any]:
    effective_as_of_date = (
        resolve_market_trading_date(market, as_of_date)
        if normalize_to_trading_day
        else None
    ) or as_of_date
    start_date = offset_iso_date(effective_as_of_date, -lookback_days)
    frame = load_history_cache(history_dir, market, symbol)
    coverage = classify_history_cache_coverage(
        frame,
        start_date=start_date,
        as_of_date=effective_as_of_date,
    )
    window = slice_history_window(frame, start_date, effective_as_of_date)
    return {
        "cache_path": history_cache_path(history_dir, market, symbol),
        "coverage": coverage,
        "window": window,
        "start_date": start_date,
        "as_of_date": effective_as_of_date,
        "requested_as_of_date": as_of_date,
    }
