from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
import pytest

from tradingagents.dataflows.vendor_errors import VendorDataEmptyError, VendorRetryableError
from tradingagents.screener.history_cache import checkpoint_path, save_checkpoint
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


def _wrapped_retry_error(message: str, cause: Exception) -> VendorRetryableError:
    error = VendorRetryableError(message)
    error.__cause__ = cause
    return error


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


def test_fetch_price_history_uses_alpha_vantage_for_us_and_computes_amount_when_missing():
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
        "tradingagents.screener.market_data._fetch_alpha_vantage_stock_df",
        return_value=frame,
    ) as mock_fetch:
        result = fetch_price_history(
            "AAPL",
            "us",
            "2025-01-01",
            "2026-03-24",
            us_data_source="alpha_vantage",
        )

    mock_fetch.assert_called_once_with("AAPL", "2025-01-01", "2026-03-24")
    assert result.loc[0, "Amount"] == 50_500.0


def test_fetch_price_history_uses_tushare_for_us_and_keeps_amount():
    frame = pd.DataFrame(
        [
            {
                "Date": "2026-03-24",
                "Open": 100.0,
                "High": 102.0,
                "Low": 99.5,
                "Close": 101.0,
                "Volume": 500,
                "Amount": 50_500.0,
            }
        ]
    )

    with patch(
        "tradingagents.screener.market_data._fetch_tushare_us_stock_df",
        return_value=frame,
    ) as mock_fetch:
        result = fetch_price_history(
            "AAPL",
            "us",
            "2025-01-01",
            "2026-03-24",
            us_data_source="tushare",
        )

    mock_fetch.assert_called_once_with("AAPL", "2025-01-01", "2026-03-24")
    assert result.loc[0, "Amount"] == 50_500.0


def test_fetch_price_history_uses_akshare_for_us_and_computes_amount_when_missing():
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
        "tradingagents.screener.market_data._fetch_akshare_us_stock_df",
        return_value=frame,
    ) as mock_fetch:
        result = fetch_price_history(
            "AAPL",
            "us",
            "2025-01-01",
            "2026-03-24",
            us_data_source="akshare",
        )

    mock_fetch.assert_called_once_with("AAPL", "2025-01-01", "2026-03-24")
    assert result.loc[0, "Amount"] == 50_500.0


def test_fetch_price_history_uses_massive_for_us_and_computes_amount_when_missing():
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
        "tradingagents.screener.market_data._fetch_massive_stock_df",
        return_value=frame,
    ) as mock_fetch:
        result = fetch_price_history(
            "AAPL",
            "us",
            "2025-01-01",
            "2026-03-24",
            us_data_source="massive",
        )

    mock_fetch.assert_called_once_with("AAPL", "2025-01-01", "2026-03-24")
    assert result.loc[0, "Amount"] == 50_500.0


def test_fetch_price_history_handles_empty_us_frame_without_columns():
    with patch(
        "tradingagents.screener.market_data._fetch_yfinance_ohlcv_df",
        return_value=pd.DataFrame(),
    ) as mock_fetch:
        result = fetch_price_history("NVDA", "us", "2026-03-26", "2026-03-26")

    mock_fetch.assert_called_once_with(
        "NVDA",
        "2026-03-26",
        "2026-03-26",
        use_cache=True,
        auto_adjust=False,
    )
    assert result.empty
    assert result.columns.tolist() == ["Date", "Open", "High", "Low", "Close", "Volume", "Amount"]


def test_fetch_price_history_normalizes_us_share_class_symbol_for_yfinance():
    frame = pd.DataFrame(
        [
            {
                "Date": "2026-03-24",
                "Open": 500.0,
                "High": 505.0,
                "Low": 498.0,
                "Close": 503.0,
                "Volume": 100,
            }
        ]
    )

    with patch(
        "tradingagents.screener.market_data._fetch_yfinance_ohlcv_df",
        return_value=frame,
    ) as mock_fetch:
        result = fetch_price_history("BRK.B", "us", "2025-01-01", "2026-03-24")

    mock_fetch.assert_called_once_with(
        "BRK-B",
        "2025-01-01",
        "2026-03-24",
        use_cache=True,
        auto_adjust=False,
    )
    assert result.loc[0, "Close"] == 503.0


def test_fetch_history_for_universe_records_empty_results_as_history_empty():
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
            "drop_reason": "history_empty",
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


def test_fetch_history_for_universe_uses_configured_us_data_source(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    success_frame = _price_frame("2026-03-24")
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        return_value=success_frame,
    ) as mock_fetch:
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            us_data_source="alpha_vantage",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    assert "AAPL" in histories
    assert failures.empty
    mock_fetch.assert_called_once_with(
        "AAPL",
        "us",
        "2025-02-17",
        "2026-03-24",
        us_data_source="alpha_vantage",
    )


def test_fetch_history_for_universe_uses_configured_tushare_us_data_source(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    success_frame = _price_frame("2026-03-24")
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        return_value=success_frame,
    ) as mock_fetch:
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            us_data_source="tushare",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    assert "AAPL" in histories
    assert failures.empty
    mock_fetch.assert_called_once_with(
        "AAPL",
        "us",
        "2025-02-17",
        "2026-03-24",
        us_data_source="tushare",
    )


def test_fetch_history_for_universe_uses_configured_akshare_us_data_source(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    success_frame = _price_frame("2026-03-24")
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        return_value=success_frame,
    ) as mock_fetch:
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            us_data_source="akshare",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    assert "AAPL" in histories
    assert failures.empty
    mock_fetch.assert_called_once_with(
        "AAPL",
        "us",
        "2025-02-17",
        "2026-03-24",
        us_data_source="akshare",
    )


def test_fetch_history_for_universe_uses_configured_massive_us_data_source(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    success_frame = _price_frame("2026-03-24")
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        return_value=success_frame,
    ) as mock_fetch:
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            us_data_source="massive",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    assert "AAPL" in histories
    assert failures.empty
    mock_fetch.assert_called_once_with(
        "AAPL",
        "us",
        "2025-02-17",
        "2026-03-24",
        us_data_source="massive",
    )


def test_fetch_history_for_universe_reraises_raw_cn_error_after_retries_exhausted():
    universe = pd.DataFrame(
        [{"symbol": "600519.SH", "market": "cn", "name": "Kweichow Moutai", "exchange": "SSE", "sector": "Liquor", "list_date": "20010827"}]
    )

    def raise_wrapped(*args, **kwargs):
        raise _wrapped_retry_error(
            "tushare stock fetch failed: boom",
            RuntimeError("boom"),
        )

    with (
        patch("tradingagents.screener.market_data.fetch_price_history", side_effect=raise_wrapped),
        patch("tradingagents.screener.market_data.time.sleep"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            fetch_history_for_universe(universe, "2026-03-24")


def test_fetch_history_for_universe_falls_back_cn_source_after_primary_retryable_error():
    universe = pd.DataFrame(
        [{"symbol": "600519.SH", "market": "cn", "name": "Kweichow Moutai", "exchange": "SSE", "sector": "Liquor", "list_date": "20010827"}]
    )
    success_frame = _price_frame("2026-03-24")

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        side_effect=[
            VendorRetryableError("akshare down"),
            VendorRetryableError("akshare down"),
            VendorRetryableError("akshare down"),
            VendorRetryableError("akshare down"),
            success_frame,
        ],
    ) as mock_fetch:
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            cn_data_source="akshare",
            cn_data_source_fallbacks=["tushare"],
        )

    assert failures.empty
    assert "600519.SH" in histories
    attempted_sources = [
        call.kwargs["cn_data_source"]
        for call in mock_fetch.call_args_list
    ]
    assert attempted_sources[0] == "akshare"
    assert attempted_sources[-1] == "tushare"
    assert "tushare" in attempted_sources


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


def test_fetch_history_for_universe_rate_limits_us_requests_between_symbols(tmp_path):
    universe = pd.DataFrame(
        [
            {"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "Technology", "list_date": ""},
            {"symbol": "MSFT", "market": "us", "name": "Microsoft", "exchange": "NASDAQ", "sector": "Technology", "list_date": ""},
        ]
    )
    frame = _price_frame("2026-03-24")
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"

    with (
        patch(
            "tradingagents.screener.market_data.fetch_price_history",
            return_value=frame,
        ),
        patch("tradingagents.screener.market_data.time.sleep") as mock_sleep,
    ):
        fetch_history_for_universe(
            universe,
            "2026-03-24",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    sleep_values = [call.args[0] for call in mock_sleep.call_args_list]
    assert 2.0 in sleep_values


def test_fetch_history_for_universe_persists_empty_failures_and_retries_refetch_on_rerun(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        side_effect=VendorDataEmptyError("empty"),
    ) as mock_fetch:
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    assert histories == {}
    assert failures.to_dict("records") == [
        {
            "symbol": "AAPL",
            "market": "us",
            "drop_reason": "history_empty",
        }
    ]
    assert mock_fetch.call_count == 1

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
    assert histories["AAPL"]["Date"].tolist() == ["2026-03-24"]
    mock_fetch.assert_called_once_with(
        "AAPL",
        "us",
        "2025-02-17",
        "2026-03-24",
        us_data_source="yfinance",
    )


def test_fetch_history_for_universe_does_not_write_history_failure_cache_files(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        side_effect=VendorRetryableError("boom"),
    ):
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    assert histories == {}
    assert failures.to_dict("records") == [
        {
            "symbol": "AAPL",
            "market": "us",
            "drop_reason": "fetch_failed",
        }
    ]
    assert not (cache_dir / "history_failures").exists()


def test_save_checkpoint_persists_only_recovery_fields(tmp_path):
    path = tmp_path / "history.json"

    save_checkpoint(
        path,
        start_date="2025-02-17",
        failed_symbols=[{"symbol": "AAPL", "market": "us", "drop_reason": "fetch_failed"}],
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert sorted(payload.keys()) == ["failed_symbols", "start_date", "updated_at"]


def test_fetch_history_for_universe_skips_symbols_recorded_as_failed_in_checkpoint(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"
    path = checkpoint_path(
        checkpoint_dir,
        universe,
        "2026-03-24",
        "tushare",
        us_data_source="yfinance",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "start_date": "2025-02-17",
                "failed_symbols": [
                    {
                        "symbol": "AAPL",
                        "market": "us",
                        "drop_reason": "fetch_failed",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        side_effect=AssertionError("checkpoint failures should skip refetch"),
    ):
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    assert histories == {}
    assert failures.to_dict("records") == [
        {
            "symbol": "AAPL",
            "market": "us",
            "drop_reason": "fetch_failed",
        }
    ]


def test_fetch_history_for_universe_reports_checkpoint_source_in_progress_detail(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"
    updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = checkpoint_path(
        checkpoint_dir,
        universe,
        "2026-03-24",
        "tushare",
        us_data_source="yfinance",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "start_date": "2025-02-17",
                "failed_symbols": [
                    {
                        "symbol": "AAPL",
                        "market": "us",
                        "drop_reason": "history_empty",
                    }
                ],
                "updated_at": updated_at,
            }
        ),
        encoding="utf-8",
    )
    progress_events: list[dict[str, str | int | None]] = []

    def progress_callback(
        stage: str,
        current: int,
        total: int,
        symbol: str | None = None,
        status: str | None = None,
        detail: str | None = None,
    ) -> None:
        progress_events.append(
            {
                "stage": stage,
                "current": current,
                "total": total,
                "symbol": symbol,
                "status": status,
                "detail": detail,
            }
        )

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        side_effect=AssertionError("checkpoint failures should skip refetch"),
    ):
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
            progress_callback=progress_callback,
        )

    assert histories == {}
    assert failures.to_dict("records") == [
        {
            "symbol": "AAPL",
            "market": "us",
            "drop_reason": "history_empty",
        }
    ]
    assert progress_events == [
        {
            "stage": "history",
            "current": 1,
            "total": 1,
            "symbol": "AAPL",
            "status": "skip_checkpoint_failure",
            "detail": f"drop_reason=history_empty source=checkpoint updated_at={updated_at}",
        }
    ]


def test_fetch_history_for_universe_ignores_expired_checkpoint_and_refetches(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"
    path = checkpoint_path(
        checkpoint_dir,
        universe,
        "2026-03-24",
        "tushare",
        us_data_source="yfinance",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "start_date": "2025-02-17",
                "failed_symbols": [
                    {
                        "symbol": "AAPL",
                        "market": "us",
                        "drop_reason": "fetch_failed",
                    }
                ],
                "updated_at": "2026-03-20T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

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
    assert histories["AAPL"]["Date"].tolist() == ["2026-03-24"]
    mock_fetch.assert_called_once_with(
        "AAPL",
        "us",
        "2025-02-17",
        "2026-03-24",
        us_data_source="yfinance",
    )
    assert not path.exists()


def test_fetch_history_for_universe_uses_us_data_source_in_checkpoint_key(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"
    yfinance_path = checkpoint_path(
        checkpoint_dir,
        universe,
        "2026-03-24",
        "tushare",
        us_data_source="yfinance",
    )
    yfinance_path.parent.mkdir(parents=True, exist_ok=True)
    yfinance_path.write_text(
        json.dumps(
            {
                "start_date": "2025-02-17",
                "failed_symbols": [
                    {
                        "symbol": "AAPL",
                        "market": "us",
                        "drop_reason": "fetch_failed",
                    }
                ],
                "updated_at": "2026-03-24T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        return_value=_price_frame("2026-03-24"),
    ) as mock_fetch:
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            us_data_source="massive",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
        )

    assert failures.empty
    assert histories["AAPL"]["Date"].tolist() == ["2026-03-24"]
    mock_fetch.assert_called_once_with(
        "AAPL",
        "us",
        "2025-02-17",
        "2026-03-24",
        us_data_source="massive",
    )
    assert yfinance_path.exists()


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


def test_fetch_history_for_universe_reports_cache_hit_progress(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"
    symbol_cache_path = cache_dir / "history" / "us" / "AAPL.csv"
    symbol_cache_path.parent.mkdir(parents=True, exist_ok=True)
    _price_frame("2025-02-17", "2026-03-21", "2026-03-24").to_csv(symbol_cache_path, index=False)
    progress_events: list[dict[str, str | int | None]] = []

    def progress_callback(
        stage: str,
        current: int,
        total: int,
        symbol: str | None = None,
        status: str | None = None,
        detail: str | None = None,
    ) -> None:
        progress_events.append(
            {
                "stage": stage,
                "current": current,
                "total": total,
                "symbol": symbol,
                "status": status,
                "detail": detail,
            }
        )

    fetch_history_for_universe(
        universe,
        "2026-03-24",
        cache_dir=cache_dir,
        checkpoint_dir=checkpoint_dir,
        checkpoint_batch_size=1,
        progress_callback=progress_callback,
    )

    assert progress_events == [
        {
            "stage": "history",
            "current": 1,
            "total": 1,
            "symbol": "AAPL",
            "status": "cache_hit",
            "detail": "cache=2025-02-17..2026-03-24",
        }
    ]


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
        us_data_source="yfinance",
    )
    assert histories["AAPL"]["Date"].tolist() == [
        "2025-02-17",
        "2026-03-20",
        "2026-03-21",
        "2026-03-22",
        "2026-03-24",
    ]


def test_fetch_history_for_universe_reports_tail_fetch_progress(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"
    symbol_cache_path = cache_dir / "history" / "us" / "AAPL.csv"
    symbol_cache_path.parent.mkdir(parents=True, exist_ok=True)
    _price_frame("2025-02-17", "2026-03-20", "2026-03-21").to_csv(symbol_cache_path, index=False)
    progress_events: list[dict[str, str | int | None]] = []

    def progress_callback(
        stage: str,
        current: int,
        total: int,
        symbol: str | None = None,
        status: str | None = None,
        detail: str | None = None,
    ) -> None:
        progress_events.append(
            {
                "stage": stage,
                "current": current,
                "total": total,
                "symbol": symbol,
                "status": status,
                "detail": detail,
            }
        )

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        return_value=_price_frame("2026-03-22", "2026-03-24"),
    ):
        fetch_history_for_universe(
            universe,
            "2026-03-24",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
            progress_callback=progress_callback,
        )

    assert progress_events == [
        {
            "stage": "history",
            "current": 1,
            "total": 1,
            "symbol": "AAPL",
            "status": "fetch_tail",
            "detail": "cache=2025-02-17..2026-03-21 fetch=2026-03-22..2026-03-24 source=yfinance",
        }
    ]


def test_fetch_history_for_universe_reports_tail_fetch_progress_for_akshare_us(tmp_path):
    universe = pd.DataFrame(
        [{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}]
    )
    cache_dir = tmp_path / "cache"
    checkpoint_dir = tmp_path / "checkpoints"
    symbol_cache_path = cache_dir / "history" / "us" / "AAPL.csv"
    symbol_cache_path.parent.mkdir(parents=True, exist_ok=True)
    _price_frame("2025-02-17", "2026-03-20", "2026-03-21").to_csv(symbol_cache_path, index=False)
    progress_events: list[dict[str, str | int | None]] = []

    def progress_callback(
        stage: str,
        current: int,
        total: int,
        symbol: str | None = None,
        status: str | None = None,
        detail: str | None = None,
    ) -> None:
        progress_events.append(
            {
                "stage": stage,
                "current": current,
                "total": total,
                "symbol": symbol,
                "status": status,
                "detail": detail,
            }
        )

    with patch(
        "tradingagents.screener.market_data.fetch_price_history",
        return_value=_price_frame("2026-03-22", "2026-03-24"),
    ):
        fetch_history_for_universe(
            universe,
            "2026-03-24",
            us_data_source="akshare",
            cache_dir=cache_dir,
            checkpoint_dir=checkpoint_dir,
            checkpoint_batch_size=1,
            progress_callback=progress_callback,
        )

    assert progress_events == [
        {
            "stage": "history",
            "current": 1,
            "total": 1,
            "symbol": "AAPL",
            "status": "fetch_tail",
            "detail": "cache=2025-02-17..2026-03-21 fetch=2026-03-22..2026-03-24 source=akshare",
        }
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
    assert checkpoint_files == []
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


def test_fetch_history_for_universe_persists_checkpoint_on_keyboard_interrupt(tmp_path):
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
        side_effect=[_price_frame("2025-02-17", "2026-03-24"), KeyboardInterrupt()],
    ):
        with pytest.raises(KeyboardInterrupt):
            fetch_history_for_universe(
                universe,
                "2026-03-24",
                cache_dir=cache_dir,
                checkpoint_dir=checkpoint_dir,
                checkpoint_batch_size=100,
            )

    checkpoint_files = sorted(checkpoint_dir.glob("*/history.json"))
    assert checkpoint_files == []
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
            checkpoint_batch_size=100,
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
