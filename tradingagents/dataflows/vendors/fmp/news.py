from __future__ import annotations

from datetime import datetime, timedelta

from .common import _make_api_request, dumps, require_non_empty


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    payload = require_non_empty(
        _make_api_request(
            "/stable/news/stock",
            {
                "symbols": ticker.upper(),
                "from": start_date,
                "to": end_date,
                "limit": 50,
            },
        ),
        context=f"stock news {ticker}",
    )
    return dumps(payload)


def get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 50) -> str:
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_date = (curr_dt - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
    payload = require_non_empty(
        _make_api_request(
            "/stable/news/general",
            {
                "from": start_date,
                "to": curr_date,
                "limit": limit,
            },
        ),
        context=f"global news {curr_date}",
    )
    return dumps(payload)


def get_insider_transactions(ticker: str) -> str:
    payload = require_non_empty(
        _make_api_request(
            "/stable/insider-trading/search",
            {
                "symbol": ticker.upper(),
                "page": 0,
                "limit": 100,
            },
        ),
        context=f"insider transactions {ticker}",
    )
    return dumps(payload)
