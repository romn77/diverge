from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from datetime import date
from io import StringIO

from tradingagents.valuation.schemas import FinancialSnapshot, MarketContext, ValuationInput


SECTION_KEYS = (
    "fundamentals",
    "balance_sheet",
    "cashflow",
    "income_statement",
)


ALIASES = {
    "report_date": ["reportDate", "report_date", "Report Date", "fiscalDateEnding", "end_date", "报告日"],
    "market_cap": ["Market Cap", "MarketCapitalization", "marketCap", "marketCapitalization"],
    "shares_outstanding": [
        "Shares Outstanding",
        "SharesOutstanding",
        "sharesOutstanding",
        "commonStockSharesOutstanding",
        "Ordinary Shares Number",
        "总股本",
    ],
    "share_price": ["Current Price", "currentPrice", "Share Price"],
    "revenue": ["Revenue", "Revenue (TTM)", "totalRevenue", "Total Revenue", "营业总收入", "营业收入"],
    "ebitda": ["EBITDA", "ebitda"],
    "net_income": ["Net Income", "netIncome", "netIncomeToCommon", "净利润"],
    "free_cash_flow": ["Free Cash Flow", "freeCashFlow", "freeCashflow", "FreeCashFlow", "经营活动产生的现金流量净额"],
    "cash_and_equivalents": [
        "Cash And Cash Equivalents",
        "cashAndCashEquivalentsAtCarryingValue",
        "Cash And Short Term Investments",
        "货币资金",
    ],
    "total_debt": ["Total Debt", "shortLongTermDebtTotal", "totalDebt", "负债合计"],
    "shareholders_equity": [
        "Stockholders Equity",
        "totalShareholderEquity",
        "Shareholders Equity",
        "股东权益合计",
    ],
    "currency": ["Currency", "currency"],
    "instrument_metadata": [
        "Quote Type",
        "quoteType",
        "AssetType",
        "assetType",
        "instrument_type",
    ],
    "fund_family": ["Fund Family", "fundFamily", "fund_family", "Category", "category"],
}


def normalize_fundamentals_payload(
    raw_payload: Mapping[str, object],
    *,
    vendor: str | None = None,
    market: str = "us",
    ticker: str | None = None,
    frequency: str | None = None,
) -> ValuationInput:
    if not isinstance(raw_payload, Mapping):
        raise ValueError("Could not normalize fundamentals payload: expected section mapping")

    flattened_sections = {
        key: _flatten_payload(raw_payload.get(key))
        for key in SECTION_KEYS
    }
    merged = {}
    for section in SECTION_KEYS:
        merged.update(flattened_sections[section])

    report_date = _parse_date(_first_value(merged, "report_date"))
    market_cap = _first_number(merged, "market_cap")
    shares_outstanding = _first_number(merged, "shares_outstanding")
    share_price = _first_number(merged, "share_price")
    currency = _first_text(merged, "currency") or "USD"

    revenue = _first_number(merged, "revenue")
    ebitda = _first_number(merged, "ebitda")
    net_income = _first_number(merged, "net_income")
    free_cash_flow = _first_number(merged, "free_cash_flow")
    cash_and_equivalents = _first_number(merged, "cash_and_equivalents")
    total_debt = _first_number(merged, "total_debt")
    shareholders_equity = _first_number(merged, "shareholders_equity")

    if free_cash_flow is None:
        operating_cashflow = _find_number(merged, ["operatingCashflow", "Operating Cash Flow"])
        capital_expenditures = _find_number(merged, ["capitalExpenditures", "Capital Expenditures"])
        if operating_cashflow is not None and capital_expenditures is not None:
            free_cash_flow = operating_cashflow + capital_expenditures

    if market_cap is None and share_price is not None and shares_outstanding:
        market_cap = share_price * shares_outstanding

    if all(
        value is None
        for value in (
            revenue,
            ebitda,
            net_income,
            free_cash_flow,
            cash_and_equivalents,
            total_debt,
            shareholders_equity,
            market_cap,
            shares_outstanding,
        )
    ):
        descriptor = vendor or "unknown"
        raise ValueError(
            f"Could not normalize fundamentals payload: no valuation fields found for vendor '{descriptor}'"
        )

    instrument_type, valuation_applicability, valuation_applicability_reason = (
        _classify_instrument(
            merged,
            ticker=ticker,
        )
    )

    return ValuationInput(
        ticker=ticker or _first_text(merged, "Symbol") or _first_text(merged, "Ticker") or "UNKNOWN",
        market=MarketContext(
            market=market,
            currency=currency,
            share_price=share_price,
            shares_outstanding=shares_outstanding,
            market_cap=market_cap,
            report_date=report_date,
        ),
        financials=[
            FinancialSnapshot(
                period=frequency or "unknown",
                report_date=report_date,
                revenue=revenue,
                ebitda=ebitda,
                net_income=net_income,
                free_cash_flow=free_cash_flow,
                cash_and_equivalents=cash_and_equivalents,
                total_debt=total_debt,
                shareholders_equity=shareholders_equity,
                currency=currency,
                frequency=frequency,
            )
        ],
        instrument_type=instrument_type,
        valuation_applicability=valuation_applicability,
        valuation_applicability_reason=valuation_applicability_reason,
    )


def _flatten_payload(payload: object) -> dict[str, object]:
    if payload is None:
        return {}

    if isinstance(payload, str):
        stripped = payload.strip()
        if not stripped:
            return {}
        try:
            return _flatten_payload(json.loads(stripped))
        except json.JSONDecodeError:
            return _parse_string_payload(stripped)

    if isinstance(payload, Mapping):
        flattened = {
            key: value
            for key, value in payload.items()
            if not isinstance(value, (list, dict))
        }
        report_candidates = payload.get("annualReports") or payload.get("quarterlyReports")
        if isinstance(report_candidates, list) and report_candidates:
            latest_report = _pick_latest_report(report_candidates)
            flattened.update(_flatten_payload(latest_report))
        return flattened

    return {}


def _pick_latest_report(reports: list[object]) -> Mapping[str, object]:
    parsed_reports = [report for report in reports if isinstance(report, Mapping)]
    if not parsed_reports:
        return {}
    return max(
        parsed_reports,
        key=lambda report: _parse_date(
            report.get("fiscalDateEnding")
            or report.get("report_date")
            or report.get("end_date")
            or report.get("报告日")
        )
        or date.min,
    )


def _parse_string_payload(payload: str) -> dict[str, object]:
    parsed: dict[str, object] = {}
    body_lines = [line for line in payload.splitlines() if line.strip() and not line.startswith("#")]

    for line in body_lines:
        if ":" in line:
            key, value = line.split(":", 1)
            parsed[key.strip()] = value.strip()

    csv_lines = [line for line in body_lines if "," in line]
    if csv_lines:
        parsed.update(_parse_csv_payload(csv_lines))

    return parsed


def _parse_csv_payload(lines: list[str]) -> dict[str, object]:
    reader = list(csv.reader(StringIO("\n".join(lines))))
    if len(reader) < 2:
        return {}

    header = reader[0]
    if header and (header[0] == "" or header[0] is None):
        first_data_column = 1 if len(header) > 1 else None
        if first_data_column is None:
            return {}
        parsed = {"report_date": header[first_data_column]}
        for row in reader[1:]:
            if not row:
                continue
            key = row[0].strip()
            value = row[first_data_column].strip() if len(row) > first_data_column else ""
            if key:
                parsed[key] = value
        return parsed

    dict_reader = csv.DictReader(StringIO("\n".join(lines)))
    rows = list(dict_reader)
    if not rows:
        return {}
    latest_row = max(
        rows,
        key=lambda row: _parse_date(
            row.get("report_date") or row.get("end_date") or row.get("报告日")
        )
        or date.min,
    )
    parsed = dict(latest_row)
    if "report_date" not in parsed:
        parsed["report_date"] = (
            latest_row.get("end_date") or latest_row.get("报告日") or latest_row.get("report_date")
        )
    return parsed


def _first_value(data: Mapping[str, object], field: str) -> object | None:
    return _find_value(data, ALIASES.get(field, [field]))


def _first_number(data: Mapping[str, object], field: str) -> float | None:
    return _find_number(data, ALIASES.get(field, [field]))


def _first_text(data: Mapping[str, object], field: str) -> str | None:
    value = _first_value(data, field)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _find_value(data: Mapping[str, object], aliases: list[str]) -> object | None:
    for alias in aliases:
        if alias in data and data[alias] not in (None, ""):
            return data[alias]
    return None


def _find_number(data: Mapping[str, object], aliases: list[str]) -> float | None:
    value = _find_value(data, aliases)
    return _coerce_number(value)


def _coerce_number(value: object) -> float | None:
    if value in (None, "", "None", "null", "N/A"):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace(",", "")
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1]

    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for candidate in (text[:10], text):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _classify_instrument(
    data: Mapping[str, object],
    *,
    ticker: str | None,
) -> tuple[str, str, str | None]:
    quote_type = (_find_value(data, ALIASES["instrument_metadata"]) or "").__str__().strip()
    fund_family = _first_text(data, "fund_family")
    normalized_quote_type = quote_type.upper().replace(" ", "")

    if "ETF" in normalized_quote_type:
        return (
            "etf",
            "not_applicable",
            "ETF instruments do not have operating cash flows suitable for DCF.",
        )
    if "INDEX" in normalized_quote_type:
        return (
            "index",
            "not_applicable",
            "Index instruments do not support company-style DCF valuation.",
        )
    if "FUND" in normalized_quote_type or fund_family:
        return (
            "fund",
            "not_applicable",
            "Fund-like instruments are not suitable for operating-company DCF valuation.",
        )
    if normalized_quote_type in {"EQUITY", "COMMONSTOCK", "COMMONSHARES", "STOCK"}:
        return ("operating_company", "applicable", None)

    return ("operating_company", "applicable", None)
