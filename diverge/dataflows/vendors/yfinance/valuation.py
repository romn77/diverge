from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf

from diverge.valuation.schemas import (
    AssumptionValue,
    FinancialSnapshot,
    MarketContext,
    ValuationInput,
)


def _coerce_float(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_us_risk_free_rate() -> AssumptionValue:
    treasury = yf.Ticker("^TNX").history(period="5d")
    latest = float(treasury["Close"].dropna().iloc[-1]) / 100.0
    return AssumptionValue(value=latest, source="yfinance:^TNX", confidence="medium")


def _classify_instrument(
    info: dict[str, object],
) -> tuple[str, str, str | None]:
    quote_type = str(info.get("quoteType") or "").strip().upper().replace(" ", "")
    fund_family = info.get("fundFamily") or info.get("category")
    industry = str(info.get("industry") or "").strip().lower()

    if "ETF" in quote_type:
        return (
            "etf",
            "not_applicable",
            "ETF instruments do not have operating cash flows suitable for DCF.",
        )
    if "INDEX" in quote_type:
        return (
            "index",
            "not_applicable",
            "Index instruments do not support company-style DCF valuation.",
        )
    if "FUND" in quote_type or fund_family:
        return (
            "fund",
            "not_applicable",
            "Fund-like instruments are not suitable for operating-company DCF valuation.",
        )
    if "reit" in industry:
        return (
            "reit",
            "not_applicable",
            "REIT instruments should use sector-specific valuation methods instead of operating-company DCF.",
        )
    if "insurance" in industry:
        return (
            "insurance",
            "not_applicable",
            "Insurance companies should use sector-specific valuation methods instead of operating-company DCF.",
        )
    if "bank" in industry or "banks" in industry:
        return (
            "bank",
            "not_applicable",
            "Banks should use sector-specific valuation methods instead of operating-company DCF.",
        )
    return ("operating_company", "applicable", None)


def _extract_growth_assumption(ticker_obj) -> AssumptionValue | None:
    candidate_frames = (
        (
            "yfinance.earnings_estimate",
            getattr(ticker_obj, "earnings_estimate", None),
            "growth",
        ),
        (
            "yfinance.revenue_estimate",
            getattr(ticker_obj, "revenue_estimate", None),
            "growth",
        ),
        (
            "yfinance.growth_estimates",
            getattr(ticker_obj, "growth_estimates", None),
            "stock",
        ),
    )
    for source, frame, column in candidate_frames:
        if frame is None or getattr(frame, "empty", False):
            continue
        if column not in frame.columns:
            continue
        series = frame[column].dropna()
        if series.empty:
            continue
        value = _coerce_float(series.iloc[0])
        if value is not None:
            return AssumptionValue(value=value, source=source, confidence="medium")
    return None


def _extract_peg_assumptions(
    ticker_obj,
    info: dict[str, object],
) -> dict[str, AssumptionValue]:
    assumptions: dict[str, AssumptionValue] = {}

    forward_pe = _coerce_float(info.get("forwardPE"))
    if forward_pe is None:
        current_price = _coerce_float(info.get("currentPrice"))
        forward_eps = _coerce_float(info.get("forwardEps"))
        if current_price is not None and forward_eps is not None and forward_eps > 0:
            forward_pe = current_price / forward_eps
    if forward_pe is not None and forward_pe > 0:
        assumptions["forward_pe"] = AssumptionValue(
            value=forward_pe,
            source="yfinance.info",
            confidence="medium",
        )

    earnings_estimate = getattr(ticker_obj, "earnings_estimate", None)
    if earnings_estimate is not None and not getattr(earnings_estimate, "empty", False):
        if {"avg", "numberOfAnalysts"}.issubset(earnings_estimate.columns):
            try:
                eps_fy0 = _coerce_float(earnings_estimate.loc["0y", "avg"])
                eps_nfy1 = _coerce_float(earnings_estimate.loc["+1y", "avg"])
                analysts_fy0 = _coerce_float(
                    earnings_estimate.loc["0y", "numberOfAnalysts"]
                )
                analysts_nfy1 = _coerce_float(
                    earnings_estimate.loc["+1y", "numberOfAnalysts"]
                )
            except KeyError:
                eps_fy0 = eps_nfy1 = analysts_fy0 = analysts_nfy1 = None
            if (
                eps_fy0 is not None
                and eps_nfy1 is not None
                and eps_fy0 > 0
                and eps_nfy1 > 0
                and (analysts_fy0 or 0) >= 3
                and (analysts_nfy1 or 0) >= 3
            ):
                growth_1y = (eps_nfy1 / eps_fy0) - 1
                if growth_1y > 0:
                    assumptions["eps_growth_1y"] = AssumptionValue(
                        value=growth_1y,
                        source="yfinance.earnings_estimate",
                        confidence="medium",
                    )

    growth_estimates = getattr(ticker_obj, "growth_estimates", None)
    if growth_estimates is not None and not getattr(growth_estimates, "empty", False):
        if "stock" in growth_estimates.columns:
            try:
                long_term_growth = _coerce_float(growth_estimates.loc["+5y", "stock"])
            except KeyError:
                long_term_growth = None
            if long_term_growth is not None and long_term_growth > 0:
                assumptions["eps_growth_long_term"] = AssumptionValue(
                    value=long_term_growth,
                    source="yfinance.growth_estimates",
                    confidence="low",
                )

    return assumptions


def _statement_by_date(df: pd.DataFrame) -> dict[date | None, dict[str, float | None]]:
    if df is None or df.empty:
        return {}

    by_date: dict[date | None, dict[str, float | None]] = {}
    for column in df.columns:
        report_ts = pd.to_datetime(column, errors="coerce")
        report_date = None if pd.isna(report_ts) else report_ts.date()
        values: dict[str, float | None] = {}
        for label, value in df[column].items():
            values[str(label)] = _coerce_float(value)
        by_date[report_date] = values
    return by_date


def _build_yfinance_snapshots(ticker_obj, freq: str) -> list[FinancialSnapshot]:
    del freq  # Phase 1 always uses annual history here.

    income_by_date = _statement_by_date(
        getattr(ticker_obj, "income_stmt", pd.DataFrame())
    )
    cashflow_by_date = _statement_by_date(
        getattr(ticker_obj, "cashflow", pd.DataFrame())
    )
    balance_by_date = _statement_by_date(
        getattr(ticker_obj, "balance_sheet", pd.DataFrame())
    )

    report_dates = {
        *income_by_date.keys(),
        *cashflow_by_date.keys(),
        *balance_by_date.keys(),
    }

    snapshots: list[FinancialSnapshot] = []
    for report_date in sorted(report_dates, reverse=True):
        income = income_by_date.get(report_date, {})
        cashflow = cashflow_by_date.get(report_date, {})
        balance = balance_by_date.get(report_date, {})

        free_cash_flow = cashflow.get("Free Cash Flow")
        if free_cash_flow is None:
            operating_cash_flow = cashflow.get("Operating Cash Flow")
            capital_expenditure = cashflow.get("Capital Expenditure")
            if operating_cash_flow is not None and capital_expenditure is not None:
                free_cash_flow = operating_cash_flow + capital_expenditure

        snapshots.append(
            FinancialSnapshot(
                period=report_date.isoformat() if report_date else "unknown",
                report_date=report_date,
                revenue=income.get("Total Revenue"),
                ebitda=income.get("EBITDA"),
                net_income=income.get("Net Income"),
                free_cash_flow=free_cash_flow,
                cash_and_equivalents=balance.get("Cash And Cash Equivalents"),
                total_debt=balance.get("Total Debt"),
                shareholders_equity=balance.get("Stockholders Equity"),
                currency=getattr(ticker_obj, "info", {}).get("currency"),
                frequency="annual",
            )
        )

    return snapshots


def build_yfinance_valuation_input(
    ticker: str,
    curr_date: str | None = None,
    freq: str = "annual",
) -> ValuationInput:
    del curr_date

    ticker_obj = yf.Ticker(ticker.upper())
    info = ticker_obj.info

    assumptions = {
        "risk_free_rate": _get_us_risk_free_rate(),
        "beta": AssumptionValue(
            value=info.get("beta"),
            source="yfinance.info",
            confidence="medium" if info.get("beta") is not None else "low",
            fallback_reason=(
                None
                if info.get("beta") is not None
                else "yfinance did not provide beta; downstream WACC should fall back."
            ),
        ),
    }
    short_term_growth = _extract_growth_assumption(ticker_obj)
    if short_term_growth is not None:
        assumptions["short_term_growth"] = short_term_growth
    assumptions.update(_extract_peg_assumptions(ticker_obj, info))

    instrument_type, valuation_applicability, valuation_applicability_reason = (
        _classify_instrument(info)
    )

    return ValuationInput(
        ticker=ticker.upper(),
        market=MarketContext(
            market="us",
            currency=info.get("currency") or "USD",
            share_price=_coerce_float(info.get("currentPrice")),
            shares_outstanding=_coerce_float(info.get("sharesOutstanding")),
            diluted_shares_outstanding=_coerce_float(
                info.get("impliedSharesOutstanding")
            ),
            market_cap=_coerce_float(info.get("marketCap")),
            enterprise_value=_coerce_float(info.get("enterpriseValue")),
            beta=_coerce_float(info.get("beta")),
        ),
        financials=_build_yfinance_snapshots(ticker_obj, freq=freq),
        assumptions=assumptions,
        instrument_type=instrument_type,
        valuation_applicability=valuation_applicability,
        valuation_applicability_reason=valuation_applicability_reason,
    )
