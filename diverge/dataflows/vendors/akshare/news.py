from __future__ import annotations

import pandas as pd

from .rate_limit import call_akshare_api
from ...cn_market_utils import (
    dataframe_to_standard_string,
    parse_and_normalize_cn_ticker,
)
from ...vendor_errors import (
    VendorDataEmptyError,
    VendorNotSupportedError,
    VendorRetryableError,
)


def _import_akshare():
    try:
        import akshare as ak
    except ModuleNotFoundError as exc:
        raise VendorRetryableError("akshare is not installed.") from exc
    return ak


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    ak = _import_akshare()
    symbol = parse_and_normalize_cn_ticker(ticker)["raw"]
    try:
        df = call_akshare_api(ak.stock_research_report_em, symbol=symbol)
    except Exception as exc:
        raise VendorRetryableError(f"akshare news fetch failed: {exc}") from exc

    if df is None or df.empty:
        raise VendorDataEmptyError(
            f"No akshare research report data found for {ticker}"
        )

    if "日期" in df.columns:
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        dates = pd.to_datetime(df["日期"], errors="coerce")
        df = df[(dates >= start_dt) & (dates <= end_dt)]

    if df.empty:
        raise VendorDataEmptyError(
            f"No akshare research report data found for {ticker}"
        )

    return dataframe_to_standard_string(df, f"CN research reports for {ticker}")


def get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 5) -> str:
    raise VendorNotSupportedError(
        "akshare does not provide a global macro news endpoint here."
    )


def get_insider_transactions(ticker: str) -> str:
    raise VendorNotSupportedError("akshare insider transactions are not implemented.")
