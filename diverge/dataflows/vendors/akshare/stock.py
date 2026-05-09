from __future__ import annotations

import pandas as pd

from .rate_limit import call_akshare_api
from ...cn_market_utils import dataframe_to_standard_string, rename_columns
from ...vendor_errors import VendorDataEmptyError, VendorRetryableError


OHLCV_RENAME_MAP = {
    "日期": "Date",
    "开盘": "Open",
    "收盘": "Close",
    "最高": "High",
    "最低": "Low",
    "成交量": "Volume",
    "成交额": "Amount",
    "振幅": "Amplitude",
    "涨跌幅": "ChangePercent",
    "涨跌额": "Change",
    "换手率": "TurnoverRate",
}

US_OHLCV_RENAME_MAP = {
    "date": "Date",
    "open": "Open",
    "close": "Close",
    "high": "High",
    "low": "Low",
    "volume": "Volume",
}


def _import_akshare():
    try:
        import akshare as ak
    except ModuleNotFoundError as exc:
        raise VendorRetryableError("akshare is not installed.") from exc
    return ak


def _fetch_akshare_stock_df(symbol: str, start_date: str, end_date: str):
    ak = _import_akshare()
    try:
        df = call_akshare_api(
            ak.stock_zh_a_hist,
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
    except Exception as exc:
        raise VendorRetryableError(f"akshare stock fetch failed: {exc}") from exc

    if df is None or df.empty:
        raise VendorDataEmptyError(f"No akshare stock data found for {symbol}")

    return rename_columns(df, OHLCV_RENAME_MAP)


def _fetch_akshare_us_stock_df(symbol: str, start_date: str, end_date: str):
    ak = _import_akshare()
    try:
        df = call_akshare_api(ak.stock_us_daily, symbol=symbol, adjust="")
    except Exception as exc:
        raise VendorRetryableError(f"akshare us stock fetch failed: {exc}") from exc

    if df is None or df.empty:
        raise VendorDataEmptyError(f"No akshare us stock data found for {symbol}")

    renamed = rename_columns(df, US_OHLCV_RENAME_MAP)
    if renamed.empty:
        raise VendorDataEmptyError(f"No akshare us stock data found for {symbol}")

    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)
    filtered = renamed[
        (renamed["Date"] >= start_ts) & (renamed["Date"] <= end_ts)
    ].reset_index(drop=True)
    if filtered.empty:
        raise VendorDataEmptyError(f"No akshare us stock data found for {symbol}")
    return filtered


def get_stock(symbol: str, start_date: str, end_date: str) -> str:
    df = _fetch_akshare_stock_df(symbol, start_date, end_date)
    title = f"CN stock data for {symbol} from {start_date} to {end_date}"
    return dataframe_to_standard_string(df, title)
