from __future__ import annotations

import pandas as pd

from .cn_market_utils import dataframe_to_standard_string, rename_columns
from .tushare_common import get_tushare_pro_client, to_tushare_date
from .vendor_errors import VendorDataEmptyError, VendorRetryableError


TS_RENAME_MAP = {
    "trade_date": "Date",
    "open": "Open",
    "close": "Close",
    "high": "High",
    "low": "Low",
    "pre_close": "PreClose",
    "change": "Change",
    "pct_chg": "ChangePercent",
    "vol": "Volume",
    "amount": "Amount",
}

TS_US_RENAME_MAP = {
    "trade_date": "Date",
    "open": "Open",
    "close": "Close",
    "high": "High",
    "low": "Low",
    "vol": "Volume",
    "amount": "Amount",
}


def _fetch_tushare_stock_df(symbol: str, start_date: str, end_date: str):
    pro = get_tushare_pro_client()
    try:
        df = pro.daily(
            ts_code=symbol,
            start_date=to_tushare_date(start_date),
            end_date=to_tushare_date(end_date),
        )
    except Exception as exc:
        raise VendorRetryableError(f"tushare stock fetch failed: {exc}") from exc

    if df is None or df.empty:
        raise VendorDataEmptyError(f"No tushare stock data found for {symbol}")

    if "trade_date" in df.columns:
        df = df.copy()
        df["trade_date"] = pd.to_datetime(
            df["trade_date"].astype(str),
            format="%Y%m%d",
            errors="coerce",
        )

    renamed = rename_columns(df, TS_RENAME_MAP)
    renamed["Date"] = renamed["Date"].dt.strftime("%Y-%m-%d")
    return renamed


def _fetch_tushare_us_stock_df(symbol: str, start_date: str, end_date: str):
    pro = get_tushare_pro_client()
    try:
        df = pro.us_daily(
            ts_code=symbol,
            start_date=to_tushare_date(start_date),
            end_date=to_tushare_date(end_date),
        )
    except Exception as exc:
        raise VendorRetryableError(f"tushare us stock fetch failed: {exc}") from exc

    if df is None or df.empty:
        raise VendorDataEmptyError(f"No tushare us stock data found for {symbol}")

    if "trade_date" in df.columns:
        df = df.copy()
        df["trade_date"] = pd.to_datetime(
            df["trade_date"].astype(str),
            format="%Y%m%d",
            errors="coerce",
        )

    renamed = rename_columns(df, TS_US_RENAME_MAP)
    renamed["Date"] = renamed["Date"].dt.strftime("%Y-%m-%d")
    return renamed


def get_stock(symbol: str, start_date: str, end_date: str) -> str:
    df = _fetch_tushare_stock_df(symbol, start_date, end_date)
    title = f"CN stock data for {symbol} from {start_date} to {end_date}"
    return dataframe_to_standard_string(df, title)
