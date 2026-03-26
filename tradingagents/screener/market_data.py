from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from tradingagents.dataflows.akshare_stock import _fetch_akshare_stock_df
from tradingagents.dataflows.cn_market_utils import normalize_symbol_for_vendor
from tradingagents.dataflows.tushare_stock import _fetch_tushare_stock_df
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
    load_history_failure_cache,
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
RETRY_BACKOFF_SECONDS = (0.5, 1.0, 2.0)
LOOKBACK_DAYS = 400
FAILURE_CACHE_TTL = timedelta(hours=24)
CN_FALLBACK_ERRORS = (
    VendorRetryableError,
    VendorAuthError,
    VendorNotSupportedError,
)


def _normalize_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()

    if "Amount" not in normalized.columns:
        normalized["Amount"] = normalized["Close"] * normalized["Volume"]

    return normalized.loc[:, REQUIRED_PRICE_COLUMNS]


def fetch_price_history(
    symbol: str,
    market: str,
    start_date: str,
    end_date: str,
    cn_data_source: str = "tushare",
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
        frame = _fetch_yfinance_ohlcv_df(
            symbol,
            start_date,
            end_date,
            use_cache=True,
            auto_adjust=False,
        )
        return _normalize_price_frame(frame)

    raise ValueError(f"Unsupported market '{market}'")


def fetch_history_for_universe(
    universe_df: pd.DataFrame,
    as_of_date: str,
    cn_data_source: str = "tushare",
    cn_data_source_fallbacks: list[str] | None = None,
    progress_callback: Callable | None = None,
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
    )
    checkpoint_payload = load_checkpoint(history_checkpoint_path) or {}
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

    histories: dict[str, pd.DataFrame] = {}
    failures: list[dict[str, str]] = []
    total = len(universe_df.index)
    processed_since_checkpoint = 0
    cn_network_fetch_count = 0
    current_symbol: str | None = None
    cn_source_chain = build_cn_source_chain(
        cn_data_source,
        cn_data_source_fallbacks,
    )

    def fetch_frame_with_retries(
        symbol: str,
        market: str,
        fetch_start: str,
    ) -> pd.DataFrame:
        nonlocal cn_network_fetch_count

        if market != "cn":
            attempt = 0
            while True:
                try:
                    return fetch_price_history(
                        symbol,
                        market,
                        fetch_start,
                        as_of_date,
                        cn_data_source=cn_data_source,
                    )
                except VendorRetryableError:
                    if attempt >= len(RETRY_BACKOFF_SECONDS):
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
            raise VendorRetryableError(str(last_error)) from last_error

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

            cached_frame = load_history_cache(history_cache_dir, market, symbol)
            cached_failure = load_history_failure_cache(
                history_cache_dir,
                market,
                symbol,
                max_age=FAILURE_CACHE_TTL,
            )
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
                if progress_callback is not None:
                    progress_callback("history", index + 1, total, symbol)
                continue

            if cached_frame.empty and symbol in checkpoint_failure_reasons:
                failures.append(
                    {
                        "symbol": symbol,
                        "market": market,
                        "drop_reason": checkpoint_failure_reasons[symbol],
                    }
                )
                if progress_callback is not None:
                    progress_callback("history", index + 1, total, symbol)
                continue

            if cached_frame.empty and cached_failure is not None:
                failures.append(
                    {
                        "symbol": symbol,
                        "market": market,
                        "drop_reason": str(cached_failure.get("drop_reason") or "fetch_failed"),
                    }
                )
                if progress_callback is not None:
                    progress_callback("history", index + 1, total, symbol)
                continue

            try:
                frame = fetch_frame_with_retries(symbol, market, fetch_start)
                if frame.empty:
                    cached_window = slice_history_window(cached_frame, start_date, as_of_date)
                    if not cached_window.empty:
                        histories[symbol] = cached_window
                        processed_symbols.add(symbol)
                        processed_since_checkpoint += 1
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
                else:
                    merged_frame = merge_history_frames(cached_frame, frame)
                    delete_history_failure_cache(history_cache_dir, market, symbol)
                    save_history_cache(history_cache_dir, market, symbol, merged_frame)
                    histories[symbol] = slice_history_window(merged_frame, start_date, as_of_date)
                    processed_symbols.add(symbol)
                    processed_since_checkpoint += 1
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

            if processed_since_checkpoint >= checkpoint_batch_size:
                persist_checkpoint()
                processed_since_checkpoint = 0

            if progress_callback is not None:
                progress_callback("history", index + 1, total, symbol)
    except Exception:
        persist_checkpoint()
        raise

    delete_checkpoint(history_checkpoint_path)

    return histories, pd.DataFrame(failures, columns=["symbol", "market", "drop_reason"])
