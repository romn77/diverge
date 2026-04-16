from __future__ import annotations

from typing import Any

import pandas as pd

from .cn_market_utils import dataframe_to_standard_string, rename_columns
from .massive_common import (
    format_rfc3339_end,
    format_rfc3339_start,
    massive_get,
)
from .vendor_errors import VendorDataEmptyError, VendorRetryableError


MASSIVE_RENAME_MAP = {
    "t": "Date",
    "o": "Open",
    "h": "High",
    "l": "Low",
    "c": "Close",
    "v": "Volume",
    "vw": "VWAP",
    "n": "Transactions",
}


def _extract_bar_records(payload: dict[str, Any], symbol: str) -> list[dict[str, Any]]:
    bars = payload.get("bars")
    if isinstance(bars, dict):
        symbol_records = bars.get(symbol)
        if isinstance(symbol_records, list):
            return symbol_records
    if isinstance(bars, list):
        return bars

    results = payload.get("results")
    if isinstance(results, list):
        return results
    if isinstance(results, dict):
        symbol_records = results.get(symbol)
        if isinstance(symbol_records, list):
            return symbol_records

    symbol_records = payload.get(symbol)
    if isinstance(symbol_records, list):
        return symbol_records

    return []


def _fetch_massive_stock_df(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    params = {
        "tickers": symbol,
        "interval": "1Day",
        "start_time": format_rfc3339_start(start_date),
        "end_time": format_rfc3339_end(end_date),
        "max_rows": 10000,
        "price_adjust": "raw",
        "order": "asc",
    }

    records: list[dict[str, Any]] = []
    page_token: str | None = None

    while True:
        request_params = dict(params)
        if page_token:
            request_params["page_token"] = page_token

        payload = massive_get("/market/stocks/bars", request_params)
        page_records = _extract_bar_records(payload, symbol)
        records.extend(page_records)
        page_token = payload.get("next_page_token")
        if not page_token:
            break

    if not records:
        raise VendorDataEmptyError(f"No massive stock data found for {symbol}")

    try:
        df = pd.DataFrame(records)
    except Exception as exc:
        raise VendorRetryableError(f"massive stock fetch failed: {exc}") from exc

    if df.empty:
        raise VendorDataEmptyError(f"No massive stock data found for {symbol}")

    return rename_columns(df, MASSIVE_RENAME_MAP)


def get_stock(symbol: str, start_date: str, end_date: str) -> str:
    df = _fetch_massive_stock_df(symbol, start_date, end_date)
    return dataframe_to_standard_string(df, f"Stock data for {symbol.upper()} from {start_date} to {end_date}")
