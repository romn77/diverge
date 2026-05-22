from __future__ import annotations

import pandas as pd
import pytest

from diverge.dataflows.vendor_errors import VendorDataEmptyError, VendorRetryableError
from diverge.market_data.price_history_router import (
    PriceHistoryRouter,
    build_source_chain,
)


def _history_rows(start: str, periods: int) -> pd.DataFrame:
    dates = pd.date_range(start=start, periods=periods, freq="D")
    return pd.DataFrame(
        [
            {
                "Date": date.strftime("%Y-%m-%d"),
                "Open": 100.0 + index,
                "High": 101.0 + index,
                "Low": 99.0 + index,
                "Close": 100.5 + index,
                "Volume": 1000 + index,
                "Amount": (100.5 + index) * (1000 + index),
            }
            for index, date in enumerate(dates)
        ]
    )


def test_build_source_chain_normalizes_and_dedupes_sources():
    assert build_source_chain(" Massive ", ["YFinance", "massive", ""]) == [
        "massive",
        "yfinance",
    ]


def test_price_history_router_falls_back_and_returns_source_metadata():
    calls: list[str] = []
    sleeps: list[float] = []

    def price_fetcher(
        symbol,
        market,
        start_date,
        end_date,
        *,
        us_data_source,
    ):
        del symbol, market, start_date, end_date
        calls.append(us_data_source)
        if us_data_source == "massive":
            raise VendorDataEmptyError("massive had no rows")
        return _history_rows("2026-01-01", 3)

    router = PriceHistoryRouter(
        as_of_date="2026-01-10",
        cn_source_chain=[],
        us_data_source="massive",
        us_data_source_fallbacks=["yfinance"],
        price_fetcher=price_fetcher,
        retry_backoff_seconds=(),
        us_request_delay_seconds=0.2,
        massive_us_request_delay_seconds=0.01,
        sleep=sleeps.append,
    )

    fetched = router.fetch("SMH", "us", "2026-01-01")

    assert calls == ["massive", "yfinance"]
    assert sleeps == [0.2]
    assert fetched.source == "yfinance"
    assert fetched.frame["Date"].tolist()[-1] == "2026-01-03"


def test_price_history_router_unwraps_retryable_cn_source_error():
    cause = RuntimeError("upstream disconnected")
    wrapped = VendorRetryableError("wrapped")
    wrapped.__cause__ = cause

    def price_fetcher(*_args, **_kwargs):
        raise wrapped

    router = PriceHistoryRouter(
        as_of_date="2026-01-10",
        cn_source_chain=["tushare"],
        us_data_source="yfinance",
        price_fetcher=price_fetcher,
        retry_backoff_seconds=(),
        sleep=lambda _seconds: None,
    )

    with pytest.raises(RuntimeError, match="upstream disconnected"):
        router.fetch("600519.SH", "cn", "2026-01-01")
    assert router.last_source == "tushare"
