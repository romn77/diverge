from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from tradingagents.dataflows.akshare_stock import _fetch_akshare_stock_df, _fetch_akshare_us_stock_df
from tradingagents.dataflows.alpha_vantage_common import AlphaVantageRateLimitError
from tradingagents.dataflows.alpha_vantage_stock import _fetch_alpha_vantage_stock_df
from tradingagents.dataflows.cn_market_utils import normalize_symbol_for_vendor
from tradingagents.dataflows.massive_stock import _fetch_massive_stock_df
from tradingagents.dataflows.tushare_stock import _fetch_tushare_stock_df, _fetch_tushare_us_stock_df
from tradingagents.dataflows.vendor_errors import (
    VendorAuthError,
    VendorDataEmptyError,
    VendorNotSupportedError,
    VendorRetryableError,
)
from tradingagents.dataflows.y_finance import _fetch_yfinance_ohlcv_df
from .history_cache import (
    checkpoint_path,
    delete_history_failure_cache,
    delete_checkpoint,
    load_checkpoint,
    load_history_cache,
    merge_history_frames,
    resolve_incremental_fetch_start,
    save_checkpoint,
    save_history_failure_cache,
    save_history_cache,
    slice_history_window,
)
from .schema import build_cn_source_chain


REQUIRED_PRICE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume", "Amount"]
CN_REQUEST_DELAY_SECONDS = 0.35
US_REQUEST_DELAY_SECONDS = 2.0
RETRY_BACKOFF_SECONDS = (0.5, 1.0, 2.0)
LOOKBACK_DAYS = 400
CHECKPOINT_TTL = timedelta(hours=24)
CN_FALLBACK_ERRORS = (
    VendorRetryableError,
    VendorAuthError,
    VendorNotSupportedError,
)

try:
    from yfinance.exceptions import YFRateLimitError
except ModuleNotFoundError:  # pragma: no cover
    class YFRateLimitError(Exception):
        pass


US_RETRYABLE_ERRORS = (
    VendorRetryableError,
    AlphaVantageRateLimitError,
    YFRateLimitError,
)


def _unwrap_vendor_error(exc: Exception) -> Exception:
    cause = getattr(exc, "__cause__", None)
    return cause if isinstance(cause, Exception) else exc


def _normalize_us_symbol_for_yfinance(symbol: str) -> str:
    return str(symbol).strip().upper().replace(".", "-")


def _history_span(frame: pd.DataFrame) -> str | None:
    if frame.empty:
        return None
    start = str(frame["Date"].min())
    end = str(frame["Date"].max())
    return f"{start}..{end}"


def _emit_progress(
    progress_callback: Callable[..., None] | None,
    stage: str,
    current: int,
    total: int,
    symbol: str | None = None,
    *,
    status: str | None = None,
    detail: str | None = None,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        stage,
        current,
        total,
        symbol,
        status=status,
        detail=detail,
    )


def _normalize_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_PRICE_COLUMNS)

    normalized = df.copy()
    has_amount = "Amount" in normalized.columns

    for column in REQUIRED_PRICE_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = pd.NA

    if not has_amount:
        normalized["Amount"] = normalized["Close"] * normalized["Volume"]

    return normalized.loc[:, REQUIRED_PRICE_COLUMNS]


def fetch_price_history(
    symbol: str,
    market: str,
    start_date: str,
    end_date: str,
    cn_data_source: str = "tushare",
    us_data_source: str = "yfinance",
) -> pd.DataFrame:
    if market == "cn":
        vendor_symbol = normalize_symbol_for_vendor(symbol, market="cn", vendor=cn_data_source)
        if cn_data_source == "tushare":
            frame = _fetch_tushare_stock_df(vendor_symbol, start_date, end_date)
        elif cn_data_source == "akshare":
            frame = _fetch_akshare_stock_df(vendor_symbol, start_date, end_date)
        else:
            raise ValueError(f"Unsupported CN data source '{cn_data_source}'")

        if cn_data_source == "tushare" and not frame.empty and "Amount" in frame.columns:
            frame = frame.copy()
            frame["Amount"] = pd.to_numeric(frame["Amount"], errors="coerce") * 1000
        return _normalize_price_frame(frame)

    if market == "us":
        if us_data_source == "yfinance":
            vendor_symbol = _normalize_us_symbol_for_yfinance(symbol)
            frame = _fetch_yfinance_ohlcv_df(
                vendor_symbol,
                start_date,
                end_date,
                use_cache=True,
                auto_adjust=False,
            )
        elif us_data_source == "alpha_vantage":
            frame = _fetch_alpha_vantage_stock_df(symbol, start_date, end_date)
        elif us_data_source == "tushare":
            frame = _fetch_tushare_us_stock_df(symbol, start_date, end_date)
        elif us_data_source == "akshare":
            frame = _fetch_akshare_us_stock_df(symbol, start_date, end_date)
        elif us_data_source == "massive":
            frame = _fetch_massive_stock_df(symbol, start_date, end_date)
        else:
            raise ValueError(f"Unsupported US data source '{us_data_source}'")
        return _normalize_price_frame(frame)

    raise ValueError(f"Unsupported market '{market}'")


def fetch_history_for_universe(
    universe_df: pd.DataFrame,
    as_of_date: str,
    cn_data_source: str = "tushare",
    cn_data_source_fallbacks: list[str] | None = None,
    us_data_source: str = "yfinance",
    progress_callback: Callable[..., None] | None = None,
    cache_dir: str | Path | None = None,
    checkpoint_dir: str | Path | None = None,
    checkpoint_batch_size: int = 100,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
    start_date = (as_of_dt - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    history_cache_dir = Path(cache_dir) if cache_dir is not None else Path("./results/screener/.cache")
    history_checkpoint_dir = (
        Path(checkpoint_dir)
        if checkpoint_dir is not None
        else history_cache_dir / "checkpoints"
    )
    history_checkpoint_path = checkpoint_path(
        history_checkpoint_dir,
        universe_df,
        as_of_date,
        cn_data_source,
        cn_data_source_fallbacks=cn_data_source_fallbacks,
        us_data_source=us_data_source,
    )
    checkpoint_payload = load_checkpoint(history_checkpoint_path, max_age=CHECKPOINT_TTL) or {}
    processed_symbols: set[str] = set(checkpoint_payload.get("processed_symbols") or [])
    checkpoint_failed_symbols = checkpoint_payload.get("failed_symbols") or [
        {
            "symbol": symbol,
            "drop_reason": "fetch_failed",
        }
        for symbol in checkpoint_payload.get("fetch_failed_symbols") or []
    ]
    checkpoint_failure_reasons = {
        str(item.get("symbol")): str(item.get("drop_reason") or "fetch_failed")
        for item in checkpoint_failed_symbols
        if item.get("symbol")
    }
    checkpoint_updated_at = checkpoint_payload.get("updated_at")

    histories: dict[str, pd.DataFrame] = {}
    failures: list[dict[str, str]] = []
    total = len(universe_df.index)
    processed_since_checkpoint = 0
    cn_network_fetch_count = 0
    us_network_fetch_count = 0
    current_symbol: str | None = None
    cn_source_chain = build_cn_source_chain(
        cn_data_source,
        cn_data_source_fallbacks,
    )

    last_fetch_source: str | None = None

    def fetch_frame_with_retries(
        symbol: str,
        market: str,
        fetch_start: str,
    ) -> pd.DataFrame:
        nonlocal cn_network_fetch_count, us_network_fetch_count, last_fetch_source

        if market != "cn":
            attempt = 0
            while True:
                try:
                    if us_network_fetch_count > 0:
                        time.sleep(US_REQUEST_DELAY_SECONDS)
                    us_network_fetch_count += 1
                    last_fetch_source = us_data_source
                    return fetch_price_history(
                        symbol,
                        market,
                        fetch_start,
                        as_of_date,
                        us_data_source=us_data_source,
                    )
                except US_RETRYABLE_ERRORS as exc:
                    if attempt >= len(RETRY_BACKOFF_SECONDS):
                        if isinstance(exc, VendorRetryableError):
                            raise _unwrap_vendor_error(exc)
                        raise
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                    attempt += 1

        last_error: Exception | None = None
        for source in cn_source_chain:
            attempt = 0
            while True:
                try:
                    if cn_network_fetch_count > 0:
                        time.sleep(CN_REQUEST_DELAY_SECONDS)
                    cn_network_fetch_count += 1
                    last_fetch_source = source
                    return fetch_price_history(
                        symbol,
                        market,
                        fetch_start,
                        as_of_date,
                        cn_data_source=source,
                    )
                except VendorDataEmptyError:
                    raise
                except CN_FALLBACK_ERRORS as exc:
                    last_error = exc
                    if attempt >= len(RETRY_BACKOFF_SECONDS):
                        break
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                    attempt += 1

        if last_error is not None:
            raise _unwrap_vendor_error(last_error)

        raise VendorRetryableError("CN history fetch failed without a fallback result")

    def persist_checkpoint() -> None:
        save_checkpoint(
            history_checkpoint_path,
            as_of_date=as_of_date,
            start_date=start_date,
            processed_symbols=sorted(processed_symbols),
            fetch_failed_symbols=[
                failure["symbol"]
                for failure in failures
                if failure["drop_reason"] == "fetch_failed"
            ],
            failed_symbols=failures,
            universe_total=total,
            last_symbol=current_symbol,
        )

    try:
        for index, row in universe_df.reset_index(drop=True).iterrows():
            symbol = row["symbol"]
            market = row["market"]
            current_symbol = str(symbol)
            last_fetch_source = None

            cached_frame = load_history_cache(history_cache_dir, market, symbol)
            cached_span = _history_span(cached_frame)
            fetch_start = resolve_incremental_fetch_start(cached_frame, start_date, as_of_date)
            if fetch_start is None:
                delete_history_failure_cache(history_cache_dir, market, symbol)
                cached_window = slice_history_window(cached_frame, start_date, as_of_date)
                if not cached_window.empty:
                    histories[symbol] = cached_window
                    processed_symbols.add(symbol)
                    processed_since_checkpoint += 1
                if processed_since_checkpoint >= checkpoint_batch_size:
                    persist_checkpoint()
                    processed_since_checkpoint = 0
                _emit_progress(
                    progress_callback,
                    "history",
                    index + 1,
                    total,
                    symbol,
                    status="cache_hit",
                    detail=f"cache={cached_span}" if cached_span else None,
                )
                continue

            if cached_frame.empty and symbol in checkpoint_failure_reasons:
                drop_reason = checkpoint_failure_reasons[symbol]
                checkpoint_detail = f"drop_reason={drop_reason} source=checkpoint"
                if checkpoint_updated_at:
                    checkpoint_detail += f" updated_at={checkpoint_updated_at}"
                failures.append(
                    {
                        "symbol": symbol,
                        "market": market,
                        "drop_reason": drop_reason,
                    }
                )
                _emit_progress(
                    progress_callback,
                    "history",
                    index + 1,
                    total,
                    symbol,
                    status="skip_checkpoint_failure",
                    detail=checkpoint_detail,
                )
                continue

            history_status: str | None = None
            history_detail: str | None = None

            try:
                frame = fetch_frame_with_retries(symbol, market, fetch_start)
                fetch_range = f"{fetch_start}..{as_of_date}"
                source_detail = (
                    f" source={last_fetch_source}" if last_fetch_source is not None else ""
                )
                if frame.empty:
                    cached_window = slice_history_window(cached_frame, start_date, as_of_date)
                    if not cached_window.empty:
                        histories[symbol] = cached_window
                        processed_symbols.add(symbol)
                        processed_since_checkpoint += 1
                        history_status = "fetch_empty_reuse_cache"
                        history_detail = (
                            f"cache={cached_span} fetch={fetch_range}{source_detail}"
                            if cached_span
                            else f"fetch={fetch_range}{source_detail}"
                        )
                    else:
                        save_history_failure_cache(
                            history_cache_dir,
                            market,
                            symbol,
                            drop_reason="history_empty",
                        )
                        failures.append(
                            {
                                "symbol": symbol,
                                "market": market,
                                "drop_reason": "history_empty",
                            }
                        )
                        history_status = "history_empty"
                        history_detail = f"fetch={fetch_range}{source_detail}"
                else:
                    merged_frame = merge_history_frames(cached_frame, frame)
                    delete_history_failure_cache(history_cache_dir, market, symbol)
                    save_history_cache(history_cache_dir, market, symbol, merged_frame)
                    histories[symbol] = slice_history_window(merged_frame, start_date, as_of_date)
                    processed_symbols.add(symbol)
                    processed_since_checkpoint += 1
                    if cached_frame.empty or fetch_start == start_date:
                        history_status = "fetch_full"
                        history_detail = f"fetch={fetch_range}{source_detail}"
                    else:
                        history_status = "fetch_tail"
                        history_detail = (
                            f"cache={cached_span} fetch={fetch_range}{source_detail}"
                        )
            except VendorDataEmptyError:
                save_history_failure_cache(
                    history_cache_dir,
                    market,
                    symbol,
                    drop_reason="history_empty",
                )
                failures.append(
                    {
                        "symbol": symbol,
                        "market": market,
                        "drop_reason": "history_empty",
                    }
                )
                history_status = "history_empty"
                history_detail = f"fetch={fetch_start}..{as_of_date}"
                if last_fetch_source is not None:
                    history_detail += f" source={last_fetch_source}"
            except VendorRetryableError:
                save_history_failure_cache(
                    history_cache_dir,
                    market,
                    symbol,
                    drop_reason="fetch_failed",
                )
                failures.append(
                    {
                        "symbol": symbol,
                        "market": market,
                        "drop_reason": "fetch_failed",
                    }
                )
                history_status = "fetch_failed"
                history_detail = f"fetch={fetch_start}..{as_of_date}"
                if last_fetch_source is not None:
                    history_detail += f" source={last_fetch_source}"

            if processed_since_checkpoint >= checkpoint_batch_size:
                persist_checkpoint()
                processed_since_checkpoint = 0

            _emit_progress(
                progress_callback,
                "history",
                index + 1,
                total,
                symbol,
                status=history_status,
                detail=history_detail,
            )
    except BaseException:
        persist_checkpoint()
        raise

    delete_checkpoint(history_checkpoint_path)

    return histories, pd.DataFrame(failures, columns=["symbol", "market", "drop_reason"])
