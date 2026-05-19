from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from diverge.dataflows.vendor_errors import VendorDataEmptyError
from diverge.market_data.history_cache import load_history_cache, save_history_cache
from diverge.market_data.price_history import HistoryFetchExecutor, fetch_ticker_history


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


def test_fetch_ticker_history_uses_cache_without_vendor(tmp_path):
    save_history_cache(tmp_path, "us", "AAPL", _history_rows("2026-01-01", 10))

    with patch(
        "diverge.market_data.price_history.fetch_price_history",
        side_effect=AssertionError("cache hit should not call vendor"),
    ):
        market, frame = fetch_ticker_history(
            "AAPL",
            market="us",
            as_of_date="2026-01-10",
            lookback_days=9,
            cache_dir=tmp_path,
        )

    assert market == "us"
    assert frame["Date"].tolist() == [
        "2026-01-01",
        "2026-01-02",
        "2026-01-03",
        "2026-01-04",
        "2026-01-05",
        "2026-01-06",
        "2026-01-07",
        "2026-01-08",
        "2026-01-09",
        "2026-01-10",
    ]


def test_fetch_ticker_history_fetches_missing_tail_and_updates_cache(tmp_path):
    save_history_cache(tmp_path, "us", "AAPL", _history_rows("2026-01-01", 8))
    tail_frame = _history_rows("2026-01-09", 2)

    with patch(
        "diverge.market_data.price_history.fetch_price_history",
        return_value=tail_frame,
    ) as fetch_price_history:
        market, frame = fetch_ticker_history(
            "AAPL",
            market="us",
            as_of_date="2026-01-10",
            lookback_days=9,
            cache_dir=tmp_path,
        )

    assert market == "us"
    fetch_price_history.assert_called_once_with(
        "AAPL",
        "us",
        "2026-01-09",
        "2026-01-10",
        us_data_source="yfinance",
    )
    assert frame["Date"].tolist()[-2:] == ["2026-01-09", "2026-01-10"]
    cached = load_history_cache(tmp_path, "us", "AAPL")
    assert cached["Date"].tolist()[-2:] == ["2026-01-09", "2026-01-10"]


def test_fetch_ticker_history_falls_back_between_us_sources_on_empty_data(tmp_path):
    fallback_frame = _history_rows("2026-01-01", 10)
    calls: list[str] = []

    def fake_fetch_price_history(
        symbol,
        market,
        start_date,
        end_date,
        *,
        us_data_source,
    ):
        calls.append(us_data_source)
        if us_data_source == "massive":
            raise VendorDataEmptyError("massive had no rows")
        return fallback_frame

    with patch(
        "diverge.market_data.price_history.fetch_price_history",
        side_effect=fake_fetch_price_history,
    ):
        market, frame = fetch_ticker_history(
            "SMH",
            market="us",
            as_of_date="2026-01-10",
            lookback_days=9,
            cache_dir=tmp_path,
            us_data_source="massive",
            us_data_source_fallbacks=["yfinance"],
        )

    assert market == "us"
    assert calls[:-1] == ["massive"] * 4
    assert calls[-1] == "yfinance"
    assert frame["Date"].tolist()[-1] == "2026-01-10"


def test_history_fetch_executor_uses_short_massive_delay_between_us_calls():
    executor = HistoryFetchExecutor(
        as_of_date="2026-01-10",
        cn_source_chain=[],
        us_data_source="massive",
        price_fetcher=lambda *args, **kwargs: _history_rows("2026-01-01", 10),
    )

    with patch("diverge.market_data.price_history.time.sleep") as sleep:
        executor.fetch("AAPL", "us", "2026-01-01")
        executor.fetch("MSFT", "us", "2026-01-01")

    sleep.assert_called_once_with(0.1)


def test_history_fetch_executor_keeps_default_delay_for_non_massive_us_sources():
    executor = HistoryFetchExecutor(
        as_of_date="2026-01-10",
        cn_source_chain=[],
        us_data_source="yfinance",
        price_fetcher=lambda *args, **kwargs: _history_rows("2026-01-01", 10),
    )

    with patch("diverge.market_data.price_history.time.sleep") as sleep:
        executor.fetch("AAPL", "us", "2026-01-01")
        executor.fetch("MSFT", "us", "2026-01-01")

    sleep.assert_called_once_with(2.0)


def test_fetch_ticker_history_can_normalize_weekend_as_of_to_trading_day(tmp_path):
    save_history_cache(tmp_path, "us", "AAPL", _history_rows("2026-01-01", 9))

    with patch(
        "diverge.market_data.price_history.fetch_price_history",
        side_effect=AssertionError(
            "normalized weekend cache hit should not call vendor"
        ),
    ):
        market, frame = fetch_ticker_history(
            "AAPL",
            market="us",
            as_of_date="2026-01-10",
            lookback_days=9,
            cache_dir=tmp_path,
            normalize_as_of_to_trading_day=True,
        )

    assert market == "us"
    assert frame["Date"].min() == "2026-01-01"
    assert frame["Date"].max() == "2026-01-09"
