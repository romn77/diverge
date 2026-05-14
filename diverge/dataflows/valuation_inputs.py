from __future__ import annotations

from diverge.dataflows.interface import resolve_market_and_symbol


def build_yfinance_valuation_input(
    ticker: str,
    curr_date: str | None = None,
    freq: str = "annual",
):
    from .vendors.yfinance.valuation import build_yfinance_valuation_input as _impl

    return _impl(ticker=ticker, curr_date=curr_date, freq=freq)


def build_akshare_valuation_input(
    ticker: str,
    curr_date: str | None = None,
    freq: str = "annual",
):
    from .vendors.akshare.valuation import build_akshare_valuation_input as _impl

    return _impl(ticker=ticker, curr_date=curr_date, freq=freq)


def route_to_valuation_input(
    ticker: str,
    curr_date: str | None = None,
    freq: str = "annual",
):
    market, _, _ = resolve_market_and_symbol(
        "get_fundamentals", (ticker, curr_date), {}
    )
    if market == "cn":
        return build_akshare_valuation_input(
            ticker=ticker, curr_date=curr_date, freq=freq
        )
    return build_yfinance_valuation_input(ticker=ticker, curr_date=curr_date, freq=freq)
