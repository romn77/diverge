from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from tradingagents.dataflows.vendor_errors import VendorRetryableError
from tradingagents.screener.market_data import (
    fetch_history_for_universe,
    fetch_price_history,
)


def test_fetch_price_history_uses_tushare_for_cn_and_normalizes_amount():
    frame = pd.DataFrame(
        [
            {
                "Date": "2026-03-24",
                "Open": 10.0,
                "High": 10.5,
                "Low": 9.8,
                "Close": 10.2,
                "Volume": 1000,
                "Amount": 25.0,
            }
        ]
    )

    with patch(
        "tradingagents.screener.market_data._fetch_tushare_stock_df",
        return_value=frame,
    ) as mock_fetch:
        result = fetch_price_history("600519.SH", "cn", "2025-01-01", "2026-03-24")

    mock_fetch.assert_called_once_with("600519.SH", "2025-01-01", "2026-03-24")
    assert result.loc[0, "Amount"] == 25_000.0


def test_fetch_price_history_uses_yfinance_for_us_and_computes_amount_when_missing():
    frame = pd.DataFrame(
        [
            {
                "Date": "2026-03-24",
                "Open": 100.0,
                "High": 102.0,
                "Low": 99.5,
                "Close": 101.0,
                "Volume": 500,
            }
        ]
    )

    with patch(
        "tradingagents.screener.market_data._fetch_yfinance_ohlcv_df",
        return_value=frame,
    ) as mock_fetch:
        result = fetch_price_history("AAPL", "us", "2025-01-01", "2026-03-24")

    mock_fetch.assert_called_once_with(
        "AAPL",
        "2025-01-01",
        "2026-03-24",
        use_cache=True,
        auto_adjust=False,
    )
    assert result.loc[0, "Amount"] == 50_500.0


def test_fetch_history_for_universe_records_empty_results_as_fetch_failed():
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        return_value=pd.DataFrame(),
    ):
        histories, failures = fetch_history_for_universe(universe, "2026-03-24")

    assert histories == {}
    assert failures.to_dict("records") == [
        {
            "symbol": "AAPL",
            "market": "us",
            "drop_reason": "fetch_failed",
        }
    ]


def test_fetch_history_for_universe_retries_retryable_errors_before_succeeding():
    universe = pd.DataFrame(
        [{"symbol": "600519.SH", "market": "cn", "name": "Kweichow Moutai", "exchange": "SSE", "sector": "Liquor", "list_date": "20010827"}]
    )
    success_frame = pd.DataFrame(
        [
            {
                "Date": "2026-03-24",
                "Open": 10.0,
                "High": 10.5,
                "Low": 9.8,
                "Close": 10.2,
                "Volume": 1000,
                "Amount": 25_000.0,
            }
        ]
    )

    with (
        patch(
            "tradingagents.screener.market_data.fetch_price_history",
            side_effect=[
                VendorRetryableError("retry 1"),
                VendorRetryableError("retry 2"),
                success_frame,
            ],
        ) as mock_fetch,
        patch("tradingagents.screener.market_data.time.sleep") as mock_sleep,
    ):
        histories, failures = fetch_history_for_universe(universe, "2026-03-24")

    assert "600519.SH" in histories
    assert failures.empty
    assert mock_fetch.call_count == 3
    sleep_values = [call.args[0] for call in mock_sleep.call_args_list]
    assert 0.5 in sleep_values
    assert 1.0 in sleep_values


def test_fetch_history_for_universe_rate_limits_cn_requests_between_symbols():
    universe = pd.DataFrame(
        [
            {"symbol": "600519.SH", "market": "cn", "name": "Kweichow Moutai", "exchange": "SSE", "sector": "Liquor", "list_date": "20010827"},
            {"symbol": "000001.SZ", "market": "cn", "name": "Ping An Bank", "exchange": "SZSE", "sector": "Banking", "list_date": "19910403"},
        ]
    )
    frame = pd.DataFrame(
        [
            {
                "Date": "2026-03-24",
                "Open": 10.0,
                "High": 10.5,
                "Low": 9.8,
                "Close": 10.2,
                "Volume": 1000,
                "Amount": 25_000.0,
            }
        ]
    )

    with (
        patch(
            "tradingagents.screener.market_data.fetch_price_history",
            return_value=frame,
        ),
        patch("tradingagents.screener.market_data.time.sleep") as mock_sleep,
    ):
        fetch_history_for_universe(universe, "2026-03-24")

    sleep_values = [call.args[0] for call in mock_sleep.call_args_list]
    assert 0.35 in sleep_values
