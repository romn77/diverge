from __future__ import annotations

from datetime import date

import pandas as pd

from .rate_limit import call_akshare_api
from ...cn_market_utils import parse_and_normalize_cn_ticker
from ...vendor_errors import VendorDataEmptyError, VendorRetryableError
from diverge.valuation.schemas import (
    AssumptionValue,
    FinancialSnapshot,
    MarketContext,
    ValuationInput,
)


def _import_akshare():
    try:
        import akshare as ak
    except ModuleNotFoundError as exc:
        raise VendorRetryableError("akshare is not installed.") from exc
    return ak


def _coerce_float(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fetch_multi_period_reports(
    ticker: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ak = _import_akshare()
    normalized = parse_and_normalize_cn_ticker(ticker)["akshare_prefixed"]

    reports = []
    for report_name in ("利润表", "资产负债表", "现金流量表"):
        try:
            df = call_akshare_api(
                ak.stock_financial_report_sina,
                stock=normalized,
                symbol=report_name,
            )
        except Exception as exc:
            raise VendorRetryableError(f"akshare financial fetch failed: {exc}") from exc
        if df is None or df.empty:
            raise VendorDataEmptyError(f"No akshare {report_name} data found for {ticker}")
        reports.append(df.copy())

    return reports[0], reports[1], reports[2]


def _get_cn_risk_free_rate() -> AssumptionValue:
    ak = _import_akshare()
    rates = call_akshare_api(ak.bond_zh_us_rate)
    latest = rates.dropna(subset=["中国国债收益率10年"]).iloc[-1]
    return AssumptionValue(
        value=float(latest["中国国债收益率10年"]) / 100.0,
        source="akshare:bond_zh_us_rate",
        confidence="medium",
    )


def _extract_cn_growth_assumption(research_df: pd.DataFrame) -> AssumptionValue | None:
    if research_df is None or research_df.empty:
        return None

    candidate_columns = [
        column
        for column in research_df.columns
        if "盈利预测-收益" in str(column)
    ]
    for column in candidate_columns:
        series = research_df[column].dropna()
        if series.empty:
            continue
        value = _coerce_float(series.iloc[0])
        if value is not None:
            return AssumptionValue(
                value=value,
                source="akshare:stock_research_report_em",
                confidence="medium",
            )
    return None


def _build_cn_snapshots(
    income_df: pd.DataFrame,
    balance_df: pd.DataFrame,
    cashflow_df: pd.DataFrame,
) -> list[FinancialSnapshot]:
    income_df = income_df.copy()
    balance_df = balance_df.copy()
    cashflow_df = cashflow_df.copy()

    for df in (income_df, balance_df, cashflow_df):
        df["报告日"] = pd.to_datetime(df["报告日"], errors="coerce")

    by_date: dict[date, dict[str, pd.Series | None]] = {}
    for frame_name, df in (
        ("income", income_df),
        ("balance", balance_df),
        ("cashflow", cashflow_df),
    ):
        for _, row in df.iterrows():
            report_ts = row.get("报告日")
            if pd.isna(report_ts):
                continue
            report_date = report_ts.date()
            by_date.setdefault(report_date, {"income": None, "balance": None, "cashflow": None})
            by_date[report_date][frame_name] = row

    snapshots: list[FinancialSnapshot] = []
    for report_date in sorted(by_date.keys(), reverse=True):
        frames = by_date[report_date]
        income = frames["income"] if frames["income"] is not None else pd.Series(dtype=object)
        balance = frames["balance"] if frames["balance"] is not None else pd.Series(dtype=object)
        cashflow = frames["cashflow"] if frames["cashflow"] is not None else pd.Series(dtype=object)

        free_cash_flow = _coerce_float(cashflow.get("自由现金流量"))
        if free_cash_flow is None:
            operating_cash_flow = _coerce_float(cashflow.get("经营活动产生的现金流量净额"))
            capital_expenditure = _coerce_float(
                cashflow.get("购建固定资产、无形资产和其他长期资产支付的现金")
            )
            if operating_cash_flow is not None and capital_expenditure is not None:
                free_cash_flow = operating_cash_flow + capital_expenditure

        snapshots.append(
            FinancialSnapshot(
                period=report_date.isoformat(),
                report_date=report_date,
                revenue=_coerce_float(income.get("营业总收入")) or _coerce_float(income.get("营业收入")),
                net_income=_coerce_float(income.get("净利润")),
                free_cash_flow=free_cash_flow,
                cash_and_equivalents=_coerce_float(balance.get("货币资金")),
                total_debt=_coerce_float(balance.get("负债合计")),
                shareholders_equity=_coerce_float(balance.get("股东权益合计")),
                currency="CNY",
                frequency="annual",
            )
        )

    return snapshots


def _load_stock_returns(ticker: str) -> list[float]:
    ak = _import_akshare()
    symbol = parse_and_normalize_cn_ticker(ticker)["akshare"]
    df = call_akshare_api(
        ak.stock_zh_a_hist,
        symbol=symbol,
        period="daily",
        start_date="20240101",
        end_date="20260324",
        adjust="qfq",
    )
    if df is None or df.empty or "收盘" not in df.columns:
        return []
    close = pd.to_numeric(df["收盘"], errors="coerce").dropna()
    if close.empty:
        return []
    return close.pct_change().dropna().tolist()


def _load_index_returns(symbol: str) -> list[float]:
    ak = _import_akshare()
    normalized = parse_and_normalize_cn_ticker(symbol)["akshare"]
    df = call_akshare_api(ak.stock_zh_index_daily, symbol=normalized)
    if df is None or df.empty or "close" not in df.columns:
        return []
    close = pd.to_numeric(df["close"], errors="coerce").dropna()
    if close.empty:
        return []
    return close.pct_change().dropna().tolist()


def _compute_cn_beta(ticker: str, benchmark: str = "sh000300") -> float | None:
    stock_returns = _load_stock_returns(ticker)
    benchmark_returns = _load_index_returns(benchmark)
    if len(stock_returns) < 60 or len(benchmark_returns) < 60:
        return None

    size = min(len(stock_returns), len(benchmark_returns))
    stock = pd.Series(stock_returns[-size:])
    index = pd.Series(benchmark_returns[-size:])
    variance = index.var()
    if variance is None or pd.isna(variance) or variance == 0:
        return None
    covariance = stock.cov(index)
    if covariance is None or pd.isna(covariance):
        return None
    return float(covariance / variance)


def build_akshare_valuation_input(
    ticker: str,
    curr_date: str | None = None,
    freq: str = "annual",
) -> ValuationInput:
    del curr_date, freq

    income_df, balance_df, cashflow_df = _fetch_multi_period_reports(ticker)
    ak = _import_akshare()
    research_df = call_akshare_api(
        ak.stock_research_report_em,
        symbol=parse_and_normalize_cn_ticker(ticker)["raw"],
    )

    assumptions = {
        "risk_free_rate": _get_cn_risk_free_rate(),
    }
    short_term_growth = _extract_cn_growth_assumption(research_df)
    if short_term_growth is not None:
        assumptions["short_term_growth"] = short_term_growth

    return ValuationInput(
        ticker=ticker,
        market=MarketContext(
            market="cn",
            currency="CNY",
        ),
        financials=_build_cn_snapshots(income_df, balance_df, cashflow_df),
        assumptions=assumptions,
    )
