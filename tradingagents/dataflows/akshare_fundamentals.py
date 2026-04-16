from __future__ import annotations

import pandas as pd

from .akshare_rate_limit import call_akshare_api
from .cn_market_utils import dataframe_to_standard_string, parse_and_normalize_cn_ticker
from .vendor_errors import VendorDataEmptyError, VendorRetryableError


def _import_akshare():
    try:
        import akshare as ak
    except ModuleNotFoundError as exc:
        raise VendorRetryableError("akshare is not installed.") from exc
    return ak


def _fetch_report(symbol: str, report_name: str):
    ak = _import_akshare()
    qualified_symbol = parse_and_normalize_cn_ticker(symbol)["akshare_prefixed"]
    try:
        df = call_akshare_api(
            ak.stock_financial_report_sina,
            stock=qualified_symbol,
            symbol=report_name,
        )
    except Exception as exc:
        raise VendorRetryableError(f"akshare financial fetch failed: {exc}") from exc

    if df is None or df.empty:
        raise VendorDataEmptyError(f"No akshare {report_name} data found for {symbol}")

    return df


def _latest_row(df: pd.DataFrame) -> pd.Series:
    report_col = "报告日" if "报告日" in df.columns else df.columns[0]
    ordered = df.copy()
    ordered[report_col] = pd.to_datetime(ordered[report_col], errors="coerce")
    ordered = ordered.sort_values(report_col, ascending=False)
    return ordered.iloc[0]


def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    income_df = _fetch_report(ticker, "利润表")
    balance_df = _fetch_report(ticker, "资产负债表")
    cashflow_df = _fetch_report(ticker, "现金流量表")

    income_row = _latest_row(income_df)
    balance_row = _latest_row(balance_df)
    cashflow_row = _latest_row(cashflow_df)

    lines = [
        f"Ticker: {parse_and_normalize_cn_ticker(ticker)['tushare']}",
        f"Report Date: {income_row.get('报告日')}",
    ]

    for label in ("营业总收入", "营业收入", "净利润", "基本每股收益"):
        if label in income_row and pd.notna(income_row[label]):
            lines.append(f"{label}: {income_row[label]}")

    for label in ("资产总计", "负债合计", "股东权益合计", "货币资金"):
        if label in balance_row and pd.notna(balance_row[label]):
            lines.append(f"{label}: {balance_row[label]}")

    for label in ("经营活动产生的现金流量净额", "现金及现金等价物净增加额"):
        if label in cashflow_row and pd.notna(cashflow_row[label]):
            lines.append(f"{label}: {cashflow_row[label]}")

    return "# CN Company Fundamentals\n\n" + "\n".join(lines)


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    df = _fetch_report(ticker, "资产负债表")
    return dataframe_to_standard_string(df, f"CN Balance Sheet data for {ticker} ({freq})")


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    df = _fetch_report(ticker, "现金流量表")
    return dataframe_to_standard_string(df, f"CN Cash Flow data for {ticker} ({freq})")


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    df = _fetch_report(ticker, "利润表")
    return dataframe_to_standard_string(df, f"CN Income Statement data for {ticker} ({freq})")
