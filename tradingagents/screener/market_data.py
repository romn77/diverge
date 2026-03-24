from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Callable

import pandas as pd

from tradingagents.dataflows.tushare_stock import _fetch_tushare_stock_df
from tradingagents.dataflows.vendor_errors import VendorRetryableError
from tradingagents.dataflows.y_finance import _fetch_yfinance_ohlcv_df


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
) -> pd.DataFrame:
    if market == "cn":
        frame = _fetch_tushare_stock_df(symbol, start_date, end_date)
        if not frame.empty and "Amount" in frame.columns:
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
    progress_callback: Callable | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
    start_date = (as_of_dt - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    histories: dict[str, pd.DataFrame] = {}
    failures: list[dict[str, str]] = []
    total = len(universe_df.index)

    for index, row in universe_df.reset_index(drop=True).iterrows():
        symbol = row["symbol"]
        market = row["market"]

        if market == "cn" and index > 0:
            time.sleep(CN_REQUEST_DELAY_SECONDS)

        attempt = 0
        while True:
            try:
                frame = fetch_price_history(symbol, market, start_date, as_of_date)
                if frame.empty:
                    failures.append(
                        {
                            "symbol": symbol,
                            "market": market,
                            "drop_reason": "fetch_failed",
                        }
                    )
                else:
                    histories[symbol] = frame
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

        if progress_callback is not None:
            progress_callback("history", index + 1, total, symbol)

    return histories, pd.DataFrame(failures, columns=["symbol", "market", "drop_reason"])
