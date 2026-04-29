from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pandas as pd

from diverge.agents.utils.core_stock_tools import get_stock_data
from diverge.agents.utils.technical_indicators_tools import get_indicators
from diverge.screener.history_cache import save_history_cache


def _history_rows(start: str, periods: int) -> pd.DataFrame:
    rows = []
    for index, day in enumerate(pd.date_range(start, periods=periods, freq="D")):
        close = 100.0 + index
        rows.append(
            {
                "Date": day.strftime("%Y-%m-%d"),
                "Open": close - 1,
                "High": close + 1,
                "Low": close - 2,
                "Close": close,
                "Volume": 1000 + index,
                "Amount": close * (1000 + index),
            }
        )
    return pd.DataFrame(rows)


def test_analysis_stock_data_uses_shared_history_cache_before_vendor_route(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_HISTORY_DIR", str(tmp_path))
    save_history_cache(
        tmp_path,
        "us",
        "AAPL",
        pd.DataFrame(
            [
                {
                    "Date": "2026-01-02",
                    "Open": 100.0,
                    "High": 103.0,
                    "Low": 99.0,
                    "Close": 102.0,
                    "Volume": 1000,
                    "Amount": 102000.0,
                },
                {
                    "Date": "2026-01-05",
                    "Open": 103.0,
                    "High": 106.0,
                    "Low": 102.0,
                    "Close": 105.0,
                    "Volume": 1200,
                    "Amount": 126000.0,
                },
            ]
        ),
    )

    with patch(
        "diverge.dataflows.interface.execute_vendor_chain",
        side_effect=AssertionError("analysis stock data should hit cache first"),
    ):
        result = get_stock_data.func("AAPL", "2026-01-02", "2026-01-05")

    assert "# Stock data for AAPL from 2026-01-02 to 2026-01-05" in result
    assert "2026-01-02" in result
    assert "105.0" in result


def test_analysis_indicators_are_computed_locally_from_shared_history_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_HISTORY_DIR", str(tmp_path))
    save_history_cache(tmp_path, "us", "AAPL", _history_rows("2025-01-01", 380))

    with patch(
        "diverge.dataflows.interface.execute_vendor_chain",
        side_effect=AssertionError("analysis indicators should be local"),
    ):
        result = get_indicators.func(
            "AAPL",
            "close_10_ema",
            datetime(2026, 1, 15).strftime("%Y-%m-%d"),
            3,
        )

    assert "## close_10_ema values from 2026-01-12 to 2026-01-15" in result
    assert "2026-01-15:" in result
    assert "10 EMA" in result
