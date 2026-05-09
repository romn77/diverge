from __future__ import annotations

import pandas as pd

from diverge.screener.history_cache import (
    load_history_cache,
    merge_history_frames,
    normalize_history_frame,
    save_history_cache,
)


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


def test_normalize_history_frame_enforces_canonical_contract():
    frame = pd.DataFrame(
        [
            {
                "Date": pd.Timestamp("2026-04-17 04:00:00+00:00"),
                "Open": "200.0",
                "High": "201.0",
                "Low": "199.0",
                "Close": "200.5",
                "Volume": "1000",
            },
            {
                "Date": "not-a-date",
                "Open": "bad",
                "High": "bad",
                "Low": "bad",
                "Close": "bad",
                "Volume": "bad",
            },
            {
                "Date": "2026-04-16",
                "Open": "198.0",
                "High": "199.0",
                "Low": "197.0",
                "Close": "198.5",
                "Volume": "900",
                "Amount": "178650",
            },
            {
                "Date": "2026-04-17",
                "Open": "210.0",
                "High": "211.0",
                "Low": "209.0",
                "Close": "210.5",
                "Volume": "1100",
            },
        ]
    )

    normalized = normalize_history_frame(frame)

    assert normalized.columns.tolist() == [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Amount",
    ]
    assert normalized["Date"].tolist() == ["2026-04-16", "2026-04-17"]
    assert normalized["Close"].tolist() == [198.5, 210.5]
    assert normalized["Amount"].tolist() == [178650.0, 231550.0]


def test_save_history_cache_backfills_missing_amount_and_round_trips(tmp_path):
    frame = pd.DataFrame(
        [
            {
                "Date": "2026-04-17",
                "Open": "210.0",
                "High": "211.0",
                "Low": "209.0",
                "Close": "210.5",
                "Volume": "1100",
            }
        ]
    )

    save_history_cache(tmp_path, "us", "AAPL", frame)
    loaded = load_history_cache(tmp_path, "us", "AAPL")

    assert loaded.columns.tolist() == [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Amount",
    ]
    assert loaded["Date"].tolist() == ["2026-04-17"]
    assert loaded["Amount"].tolist() == [231550.0]
