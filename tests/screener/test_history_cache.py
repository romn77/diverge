from __future__ import annotations

import pandas as pd

from tradingagents.screener.history_cache import merge_history_frames


def _history_row(date_value: object, close: float) -> dict[str, object]:
    return {
        "Date": date_value,
        "Open": close - 1.0,
        "High": close + 1.0,
        "Low": close - 2.0,
        "Close": close,
        "Volume": 1000,
        "Amount": close * 1000,
    }


def test_merge_history_frames_normalizes_mixed_timezone_date_values():
    cached_frame = pd.DataFrame(
        [
            _history_row("2026-04-16", 198.35),
        ]
    )
    fetched_frame = pd.DataFrame(
        [
            _history_row(pd.Timestamp("2026-04-17 04:00:00+00:00"), 200.87),
        ]
    )

    merged = merge_history_frames(cached_frame, fetched_frame)

    assert merged["Date"].tolist() == ["2026-04-16", "2026-04-17"]
    assert merged["Close"].tolist() == [198.35, 200.87]
