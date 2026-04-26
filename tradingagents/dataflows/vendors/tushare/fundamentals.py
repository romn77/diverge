from __future__ import annotations

import pandas as pd

from ...cn_market_utils import dataframe_to_standard_string
from .common import get_tushare_pro_client
from ...vendor_errors import VendorDataEmptyError, VendorRetryableError


def _fetch_dataset(fetcher_name: str, ticker: str, fields: str | None = None):
    pro = get_tushare_pro_client()
    fetcher = getattr(pro, fetcher_name)

    try:
        if fields:
            df = fetcher(ts_code=ticker, fields=fields)
        else:
            df = fetcher(ts_code=ticker)
    except Exception as exc:
        raise VendorRetryableError(f"tushare {fetcher_name} fetch failed: {exc}") from exc

    if df is None or df.empty:
        raise VendorDataEmptyError(f"No tushare {fetcher_name} data found for {ticker}")

    return df


def _latest_by_end_date(df: pd.DataFrame) -> pd.Series:
    date_col = "end_date" if "end_date" in df.columns else df.columns[0]
    ordered = df.copy()
    ordered[date_col] = pd.to_datetime(ordered[date_col], errors="coerce")
    ordered = ordered.sort_values(date_col, ascending=False)
    return ordered.iloc[0]


def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    basic_df = _fetch_dataset(
        "stock_basic",
        ticker,
        fields="ts_code,symbol,name,area,industry,market,list_date",
    )
    indicators_df = _fetch_dataset("fina_indicator", ticker)

    basic_row = basic_df.iloc[0]
    indicator_row = _latest_by_end_date(indicators_df)

    lines = [
        f"Name: {basic_row.get('name')}",
        f"Ticker: {basic_row.get('ts_code')}",
        f"Industry: {basic_row.get('industry')}",
        f"Area: {basic_row.get('area')}",
        f"Market: {basic_row.get('market')}",
        f"List Date: {basic_row.get('list_date')}",
    ]

    for label in ("roe", "roa", "grossprofit_margin", "netprofit_margin", "current_ratio", "debt_to_assets", "eps", "bps", "ocfps"):
        if label in indicator_row and pd.notna(indicator_row[label]):
            lines.append(f"{label}: {indicator_row[label]}")

    if "end_date" in indicator_row:
        lines.append(f"Report Date: {indicator_row['end_date']}")

    return "# CN Company Fundamentals\n\n" + "\n".join(lines)


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    df = _fetch_dataset("balancesheet", ticker)
    return dataframe_to_standard_string(df, f"CN Balance Sheet data for {ticker} ({freq})")


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    df = _fetch_dataset("cashflow", ticker)
    return dataframe_to_standard_string(df, f"CN Cash Flow data for {ticker} ({freq})")


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    df = _fetch_dataset("income", ticker)
    return dataframe_to_standard_string(df, f"CN Income Statement data for {ticker} ({freq})")
