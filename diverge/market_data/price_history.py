from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Callable

import pandas as pd

from diverge.common.dates import offset_iso_date, parse_iso_date
from diverge.common.market_calendar import resolve_market_trading_date
from diverge.common.symbols import normalize_symbol_for_vendor, resolve_symbol_market
from diverge.data_layout import resolve_history_dir
from diverge.dataflows import vendor_usage
from diverge.dataflows.vendor_errors import (
    VendorDataEmptyError,
    VendorRetryableError,
)
from diverge.dataflows.vendors.akshare.stock import (
    _fetch_akshare_stock_df,
    _fetch_akshare_us_stock_df,
)
from diverge.dataflows.vendors.alpha_vantage.stock import _fetch_alpha_vantage_stock_df
from diverge.dataflows.vendors.massive.stock import _fetch_massive_stock_df
from diverge.dataflows.vendors.tushare.stock import (
    _fetch_tushare_stock_df,
    _fetch_tushare_us_stock_df,
)
from diverge.dataflows.vendors.yfinance.stock import _fetch_yfinance_ohlcv_df
from diverge.market_data.history_cache import (
    REQUIRED_PRICE_COLUMNS,
    classify_history_cache_coverage,
    history_cache_path,
    load_history_cache,
    merge_history_frames,
    normalize_history_frame,
    resolve_incremental_fetch_start,
    save_history_cache,
    slice_history_window,
)
from diverge.market_data.price_history_router import (
    DEFAULT_CN_REQUEST_DELAY_SECONDS,
    DEFAULT_MASSIVE_US_REQUEST_DELAY_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_US_REQUEST_DELAY_SECONDS,
    FetchedHistoryFrame,
    PriceHistoryRouter,
    build_source_chain as _build_source_chain,
)

CN_REQUEST_DELAY_SECONDS = DEFAULT_CN_REQUEST_DELAY_SECONDS
US_REQUEST_DELAY_SECONDS = DEFAULT_US_REQUEST_DELAY_SECONDS
MASSIVE_US_REQUEST_DELAY_SECONDS = DEFAULT_MASSIVE_US_REQUEST_DELAY_SECONDS
RETRY_BACKOFF_SECONDS = DEFAULT_RETRY_BACKOFF_SECONDS
LOOKBACK_DAYS = 400

__all__ = [
    "FetchedHistoryFrame",
    "HistoryFetchExecutor",
    "fetch_price_history",
    "fetch_ticker_history",
    "load_local_price_window",
    "resolve_history_market",
]


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


class HistoryFetchExecutor(PriceHistoryRouter):
    """Backward-compatible adapter for the deeper PriceHistoryRouter module."""

    def __init__(
        self,
        *,
        as_of_date: str,
        cn_source_chain: list[str],
        us_data_source: str,
        us_data_source_fallbacks: list[str] | None = None,
        price_fetcher: Callable[..., pd.DataFrame] | None = None,
    ) -> None:
        super().__init__(
            as_of_date=as_of_date,
            cn_source_chain=cn_source_chain,
            us_data_source=us_data_source,
            us_data_source_fallbacks=us_data_source_fallbacks,
            price_fetcher=price_fetcher or fetch_price_history,
            retry_backoff_seconds=RETRY_BACKOFF_SECONDS,
            cn_request_delay_seconds=CN_REQUEST_DELAY_SECONDS,
            us_request_delay_seconds=US_REQUEST_DELAY_SECONDS,
            massive_us_request_delay_seconds=MASSIVE_US_REQUEST_DELAY_SECONDS,
            sleep=_sleep,
        )


def _normalize_us_symbol_for_yfinance(symbol: str) -> str:
    return str(symbol).strip().upper().replace(".", "-")


def _call_price_data_source(
    vendor: str, fetcher: Callable[[], pd.DataFrame]
) -> pd.DataFrame:
    return vendor_usage.track_data_source_call(vendor, fetcher)


def _normalize_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_PRICE_COLUMNS)

    return normalize_history_frame(df)


def _fetch_range(fetch_start: str, as_of_date: str) -> str:
    return f"{fetch_start}..{as_of_date}"


def _source_detail(source: str | None) -> str:
    return f" source={source}" if source is not None else ""


def fetch_price_history(
    symbol: str,
    market: str,
    start_date: str,
    end_date: str,
    cn_data_source: str = "tushare",
    us_data_source: str = "yfinance",
) -> pd.DataFrame:
    if market == "cn":
        vendor_symbol = normalize_symbol_for_vendor(
            symbol, market="cn", vendor=cn_data_source
        )
        if cn_data_source == "tushare":
            frame = _call_price_data_source(
                "tushare",
                lambda: _fetch_tushare_stock_df(vendor_symbol, start_date, end_date),
            )
        elif cn_data_source == "akshare":
            frame = _call_price_data_source(
                "akshare",
                lambda: _fetch_akshare_stock_df(vendor_symbol, start_date, end_date),
            )
        else:
            raise ValueError(f"Unsupported CN data source '{cn_data_source}'")

        if (
            cn_data_source == "tushare"
            and not frame.empty
            and "Amount" in frame.columns
        ):
            frame = frame.copy()
            frame["Amount"] = pd.to_numeric(frame["Amount"], errors="coerce") * 1000
        return _normalize_price_frame(frame)

    if market == "us":
        if us_data_source == "yfinance":
            vendor_symbol = _normalize_us_symbol_for_yfinance(symbol)
            frame = _call_price_data_source(
                "yfinance",
                lambda: _fetch_yfinance_ohlcv_df(
                    vendor_symbol,
                    start_date,
                    end_date,
                    use_cache=True,
                    auto_adjust=False,
                ),
            )
        elif us_data_source == "alpha_vantage":
            frame = _call_price_data_source(
                "alpha_vantage",
                lambda: _fetch_alpha_vantage_stock_df(symbol, start_date, end_date),
            )
        elif us_data_source == "tushare":
            frame = _call_price_data_source(
                "tushare",
                lambda: _fetch_tushare_us_stock_df(symbol, start_date, end_date),
            )
        elif us_data_source == "akshare":
            frame = _call_price_data_source(
                "akshare",
                lambda: _fetch_akshare_us_stock_df(symbol, start_date, end_date),
            )
        elif us_data_source == "massive":
            frame = _call_price_data_source(
                "massive",
                lambda: _fetch_massive_stock_df(symbol, start_date, end_date),
            )
        else:
            raise ValueError(f"Unsupported US data source '{us_data_source}'")
        return _normalize_price_frame(frame)

    raise ValueError(f"Unsupported market '{market}'")


def resolve_history_market(symbol: str, market: str | None = None) -> str:
    return resolve_symbol_market(symbol, market)


def fetch_ticker_history(
    symbol: str,
    *,
    market: str | None = None,
    as_of_date: str,
    lookback_days: int = LOOKBACK_DAYS,
    cn_data_source: str = "tushare",
    cn_data_source_fallbacks: list[str] | None = None,
    us_data_source: str = "yfinance",
    us_data_source_fallbacks: list[str] | None = None,
    cache_dir: str | Path | None = None,
    normalize_as_of_to_trading_day: bool = False,
) -> tuple[str, pd.DataFrame]:
    normalized_symbol = str(symbol).strip()
    if not normalized_symbol:
        raise ValueError("symbol is required")
    if lookback_days <= 0:
        raise ValueError("lookback_days must be positive")

    requested_as_of_dt = parse_iso_date(as_of_date)
    if requested_as_of_dt is None:
        raise ValueError("as_of_date must use YYYY-MM-DD format")
    start_date = offset_iso_date(as_of_date, -lookback_days)
    history_cache_dir = (
        Path(cache_dir) if cache_dir is not None else resolve_history_dir()
    )
    resolved_market = resolve_history_market(normalized_symbol, market)
    effective_as_of_date = as_of_date
    if normalize_as_of_to_trading_day:
        trading_date = resolve_market_trading_date(
            resolved_market,
            requested_as_of_dt,
        )
        if trading_date is not None:
            effective_as_of_date = trading_date

    cached_frame = load_history_cache(
        history_cache_dir, resolved_market, normalized_symbol
    )
    fetch_start = resolve_incremental_fetch_start(
        cached_frame, start_date, effective_as_of_date
    )
    if fetch_start is None:
        cached_window = slice_history_window(
            cached_frame,
            start_date,
            effective_as_of_date,
        )
        return resolved_market, cached_window

    executor = HistoryFetchExecutor(
        as_of_date=effective_as_of_date,
        cn_source_chain=_build_source_chain(cn_data_source, cn_data_source_fallbacks),
        us_data_source=us_data_source,
        us_data_source_fallbacks=us_data_source_fallbacks,
    )
    try:
        fetched = executor.fetch(normalized_symbol, resolved_market, fetch_start)
    except VendorDataEmptyError:
        return resolved_market, normalize_history_frame(pd.DataFrame())
    except VendorRetryableError as exc:
        raise VendorRetryableError(
            f"Failed to fetch history for {normalized_symbol} in market '{resolved_market}'"
        ) from exc

    fetch_range = _fetch_range(fetch_start, effective_as_of_date)
    source_detail = _source_detail(fetched.source)
    if fetched.frame.empty:
        cached_window = slice_history_window(
            cached_frame,
            start_date,
            effective_as_of_date,
        )
        if not cached_window.empty:
            return resolved_market, cached_window
        return resolved_market, normalize_history_frame(pd.DataFrame())

    merged_frame = merge_history_frames(cached_frame, fetched.frame)
    save_history_cache(
        history_cache_dir, resolved_market, normalized_symbol, merged_frame
    )
    history_window = slice_history_window(
        merged_frame,
        start_date,
        effective_as_of_date,
    )
    if history_window.empty:
        raise VendorRetryableError(
            "Fetched history did not cover "
            f"{fetch_range}{source_detail} for {normalized_symbol}"
        )
    return resolved_market, history_window


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
