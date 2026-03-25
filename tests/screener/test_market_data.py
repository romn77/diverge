from __future__ import annotations

import json
from unittest.mock import patch

import pandas as pd

from tradingagents.dataflows.vendor_errors import VendorRetryableError
from tradingagents.screener.market_data import (
    fetch_history_for_universe,
    fetch_price_history,
)


def _price_frame(*dates: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date": date,
                "Open": 10.0,
                "High": 10.5,
                "Low": 9.8,
                "Close": 10.2,
                "Volume": 1000,
                "Amount": 25_000.0,
            }
            for date in dates
        ]
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


def test_fetch_price_history_uses_akshare_for_cn_and_normalizes_symbol():
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

    with patch(
        "tradingagents.screener.market_data._fetch_akshare_stock_df",
        return_value=frame,
    ) as mock_fetch:
        result = fetch_price_history(
            "600519.SH",
            "cn",
            "2025-01-01",
            "2026-03-24",
            cn_data_source="akshare",
        )

    mock_fetch.assert_called_once_with("600519", "2025-01-01", "2026-03-24")
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


def test_fetch_history_for_universe_writes_symbol_cache_and_reuses_it_without_refetch(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"
    cached_frame = _price_frame("2025-02-17", "2026-03-21", "2026-03-24")

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        return_value=cached_frame,
    ) as mock_fetch:
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    assert failures.empty
    assert mock_fetch.call_count == 1
    assert histories["AAPL"]["Date"].tolist() == ["2025-02-17", "2026-03-21", "2026-03-24"]
    assert (cache_dir / "history" / "us" / "AAPL.csv").is_file()

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        side_effect=AssertionError("cache hit should avoid refetch"),
    ):
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    assert failures.empty
    assert histories["AAPL"]["Date"].tolist() == ["2025-02-17", "2026-03-21", "2026-03-24"]


def test_fetch_history_for_universe_fetches_only_missing_tail_when_cache_is_stale(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"
    symbol_cache_path = cache_dir / "history" / "us" / "AAPL.csv"
    symbol_cache_path.parent.mkdir(parents=True, exist_ok=True)
    _price_frame("2025-02-17", "2026-03-20", "2026-03-21").to_csv(symbol_cache_path, index=False)

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        return_value=_price_frame("2026-03-22", "2026-03-24"),
    ) as mock_fetch:
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    assert failures.empty
    mock_fetch.assert_called_once_with(
        "AAPL",
        "us",
        "2026-03-22",
        "2026-03-24",
        cn_data_source="tushare",
    )
    assert histories["AAPL"]["Date"].tolist() == [
        "2025-02-17",
        "2026-03-20",
        "2026-03-21",
        "2026-03-22",
        "2026-03-24",
    ]


def test_fetch_history_for_universe_recovers_from_checkpoint_and_symbol_cache_after_failure(tmp_path):
    universe = pd.DataFrame(
        [
            {"symbol": "600519.SH", "market": "cn", "name": "Kweichow Moutai", "exchange": "SSE", "sector": "Liquor", "list_date": "20010827"},
            {"symbol": "000001.SZ", "market": "cn", "name": "Ping An Bank", "exchange": "SZSE", "sector": "Banking", "list_date": "19910403"},
        ]
    )
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        side_effect=[_price_frame("2025-02-17", "2026-03-24"), RuntimeError("boom")],
    ):
        try:
            fetch_history_for_universe(
                universe,
                "2026-03-24",
                cache_dir=cache_dir,
                checkpoint_dir=checkpoint_dir,
                checkpoint_batch_size=1,
            )
        except RuntimeError as exc:
            assert str(exc) == "boom"
        else:  # pragma: no cover
            raise AssertionError("expected runtime error")

    checkpoint_files = sorted(checkpoint_dir.glob("*/history.json"))
    assert len(checkpoint_files) == 1
    checkpoint_payload = json.loads(checkpoint_files[0].read_text(encoding="utf-8"))
    assert checkpoint_payload["processed_symbols"] == ["600519.SH"]
    assert (cache_dir / "history" / "cn" / "600519.SH.csv").is_file()

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        return_value=_price_frame("2026-03-24"),
    ) as mock_fetch:
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    assert failures.empty
    mock_fetch.assert_called_once_with(
        "000001.SZ",
        "cn",
        "2025-02-17",
        "2026-03-24",
        cn_data_source="tushare",
    )
    assert set(histories) == {"600519.SH", "000001.SZ"}
    assert not checkpoint_files[0].exists()
