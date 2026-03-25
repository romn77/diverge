from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from tradingagents.dataflows.akshare_stock import _fetch_akshare_stock_df
from tradingagents.dataflows.cn_market_utils import normalize_symbol_for_vendor
from tradingagents.dataflows.tushare_stock import _fetch_tushare_stock_df
from tradingagents.dataflows.vendor_errors import VendorRetryableError
from tradingagents.dataflows.y_finance import _fetch_yfinance_ohlcv_df
from .history_cache import (
    checkpoint_path,
    delete_checkpoint,
    load_checkpoint,
    load_history_cache,
    merge_history_frames,
    resolve_incremental_fetch_start,
    save_checkpoint,
    save_history_cache,
    slice_history_window,
)


REQUIRED_PRICE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume", "Amount"]
CN_REQUEST_DELAY_SECONDS = 0.35
RETRY_BACKOFF_SECONDS = (0.5, 1.0, 2.0)
LOOKBACK_DAYS = 400


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

    histories: dict[str, pd.DataFrame] = {}
    failures: list[dict[str, str]] = []
    total = len(universe_df.index)
    processed_since_checkpoint = 0
    cn_network_fetch_count = 0
    current_symbol: str | None = None

    def persist_checkpoint() -> None:
        save_checkpoint(
            history_checkpoint_path,
            as_of_date=as_of_date,
            start_date=start_date,
            processed_symbols=sorted(processed_symbols),
            fetch_failed_symbols=[failure["symbol"] for failure in failures],
            universe_total=total,
            last_symbol=current_symbol,
        )

    try:
        for index, row in universe_df.reset_index(drop=True).iterrows():
            symbol = row["symbol"]
            market = row["market"]
            current_symbol = str(symbol)

            cached_frame = load_history_cache(history_cache_dir, market, symbol)
            fetch_start = resolve_incremental_fetch_start(cached_frame, start_date, as_of_date)
            if fetch_start is None:
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

            attempt = 0
            while True:
                try:
                    if market == "cn":
                        if cn_network_fetch_count > 0:
                            time.sleep(CN_REQUEST_DELAY_SECONDS)
                        cn_network_fetch_count += 1

                    frame = fetch_price_history(
                        symbol,
                        market,
                        fetch_start,
                        as_of_date,
                        cn_data_source=cn_data_source,
                    )
                    if frame.empty:
                        cached_window = slice_history_window(cached_frame, start_date, as_of_date)
                        if not cached_window.empty:
                            histories[symbol] = cached_window
                            processed_symbols.add(symbol)
                            processed_since_checkpoint += 1
                        else:
                            failures.append(
                                {
                                    "symbol": symbol,
                                    "market": market,
                                    "drop_reason": "fetch_failed",
                                }
                            )
                        break

                    merged_frame = merge_history_frames(cached_frame, frame)
                    save_history_cache(history_cache_dir, market, symbol, merged_frame)
                    histories[symbol] = slice_history_window(merged_frame, start_date, as_of_date)
                    processed_symbols.add(symbol)
                    processed_since_checkpoint += 1
                    break
                except VendorRetryableError:
                    if attempt >= len(RETRY_BACKOFF_SECONDS):
                        failures.append(
                            {
                                "symbol": symbol,
                                "market": market,
                                "drop_reason": "fetch_failed",
                            }
                        )
                        break

                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                    attempt += 1

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
