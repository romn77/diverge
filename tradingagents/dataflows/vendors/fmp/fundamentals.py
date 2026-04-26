from __future__ import annotations

from typing import Any

from .common import _make_api_request, dumps, require_non_empty


def _period(freq: str) -> str:
    return "annual" if str(freq or "").lower().startswith("annual") else "quarter"


def _filter_rows_by_date(rows: list[dict[str, Any]], curr_date: str | None) -> list[dict[str, Any]]:
    if not curr_date:
        return rows
    return [
        row
        for row in rows
        if str(row.get("date") or row.get("fillingDate") or row.get("acceptedDate") or "")[:10]
        <= curr_date
    ]


def _statement_payload(
    endpoint: str,
    ticker: str,
    freq: str,
    curr_date: str | None,
) -> str:
    period = _period(freq)
    rows = require_non_empty(
        _make_api_request(
            f"/stable/{endpoint}",
            {"symbol": ticker.upper(), "period": period, "limit": 120},
        ),
        context=f"{endpoint} {ticker}",
    )
    if not isinstance(rows, list):
        rows = [rows]
    filtered_rows = _filter_rows_by_date(rows, curr_date)
    require_non_empty(filtered_rows, context=f"{endpoint} {ticker} before {curr_date}")
    key = "annualReports" if period == "annual" else "quarterlyReports"
    return dumps({key: filtered_rows})


def get_fundamentals(ticker: str, curr_date: str | None = None) -> str:
    rows = require_non_empty(
        _make_api_request("/stable/profile", {"symbol": ticker.upper()}),
        context=f"profile {ticker}",
    )
    if isinstance(rows, list):
        require_non_empty(rows, context=f"profile {ticker}")
        return dumps(rows[0])
    return dumps(rows)


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    return _statement_payload("balance-sheet-statement", ticker, freq, curr_date)


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    return _statement_payload("cash-flow-statement", ticker, freq, curr_date)


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    return _statement_payload("income-statement", ticker, freq, curr_date)
