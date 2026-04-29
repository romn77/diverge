from __future__ import annotations

import numpy as np
import pandas as pd

from diverge.screener.breakouts import (
    BREAKOUT_HISTORY_MIN_BARS,
    detect_breakout_signal,
)
from diverge.screener.indicators import build_feature_row


def _history_frame(
    closes: list[float],
    *,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
    end: str = "2026-03-24",
) -> pd.DataFrame:
    closes_array = np.array(closes, dtype=float)
    highs_array = np.array(highs if highs is not None else closes_array + 0.8, dtype=float)
    lows_array = np.array(lows if lows is not None else closes_array - 0.8, dtype=float)
    volumes_array = np.array(
        volumes if volumes is not None else np.full(len(closes_array), 1_000_000.0),
        dtype=float,
    )
    opens_array = np.concatenate(([closes_array[0]], closes_array[:-1]))
    dates = pd.bdate_range(end=end, periods=len(closes_array))
    return pd.DataFrame(
        {
            "Date": dates.strftime("%Y-%m-%d"),
            "Open": opens_array,
            "High": highs_array,
            "Low": lows_array,
            "Close": closes_array,
            "Volume": volumes_array,
            "Amount": closes_array * volumes_array,
        }
    )


def _platform_breakout_history() -> pd.DataFrame:
    prefix = np.linspace(80.0, 95.0, 100)
    base = 100.0 + np.sin(np.linspace(0.0, 3.0 * np.pi, 19)) * 0.45
    closes = [*prefix, *base.tolist(), 103.2]
    highs = [*(prefix + 0.9).tolist(), *((base + 0.55).tolist()), 104.0]
    lows = [*(prefix - 0.9).tolist(), *((base - 0.55).tolist()), 100.8]
    volumes = [*([1_000_000.0] * 119), 2_400_000.0]
    return _history_frame(closes, highs=highs, lows=lows, volumes=volumes)


def _box_breakout_history() -> pd.DataFrame:
    prefix = np.linspace(70.0, 88.0, 80)
    base = 97.0 + np.sin(np.linspace(0.0, 6.0 * np.pi, 39)) * 3.2
    closes = [*prefix, *base.tolist(), 101.8]
    highs = [*(prefix + 1.0).tolist(), *((base + 1.2).tolist()), 102.6]
    lows = [*(prefix - 1.0).tolist(), *((base - 1.2).tolist()), 98.8]
    volumes = [*([900_000.0] * 119), 1_050_000.0]
    return _history_frame(closes, highs=highs, lows=lows, volumes=volumes)


def _wedge_breakout_history() -> pd.DataFrame:
    prefix = np.linspace(120.0, 112.0, 80)
    highs_tail = [109.5 - 0.28 * index for index in range(39)]
    lows_tail = [101.5 - 0.11 * index for index in range(39)]
    closes_tail = [
        (high + low) / 2.0 + (0.18 if index % 2 == 0 else -0.18)
        for index, (high, low) in enumerate(zip(highs_tail, lows_tail))
    ]
    closes = [*prefix, *closes_tail, 101.1]
    highs = [*(prefix + 1.1).tolist(), *highs_tail, 101.8]
    lows = [*(prefix - 1.1).tolist(), *lows_tail, 98.6]
    volumes = [*([1_100_000.0] * 119), 1_150_000.0]
    return _history_frame(closes, highs=highs, lows=lows, volumes=volumes)


def _no_breakout_history() -> pd.DataFrame:
    prefix = np.linspace(85.0, 98.0, 100)
    base = 100.0 + np.sin(np.linspace(0.0, 3.0 * np.pi, 19)) * 0.45
    closes = [*prefix, *base.tolist(), 100.2]
    highs = [*(prefix + 0.9).tolist(), *((base + 0.55).tolist()), 100.7]
    lows = [*(prefix - 0.9).tolist(), *((base - 0.55).tolist()), 99.6]
    return _history_frame(closes, highs=highs, lows=lows)


def test_build_feature_row_includes_platform_breakout_fields_with_volume_signal():
    meta_row = pd.Series(
        {
            "symbol": "AAPL",
            "market": "us",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "sector": "Technology",
            "list_date": "19801212",
        }
    )

    row = build_feature_row(meta_row, _platform_breakout_history(), "2026-03-24")

    assert row["breakout_hit"] is True
    assert row["breakout_type"] == "platform_breakout"
    assert row["breakout_with_volume"] is True
    assert row["breakout_volume_ratio"] > 1.5
    assert "platform_breakout" in row["breakout_reason"]


def test_detect_breakout_signal_identifies_box_breakout_without_volume_confirmation():
    signal = detect_breakout_signal(_box_breakout_history())

    assert signal.breakout_hit is True
    assert signal.breakout_type == "box_breakout"
    assert signal.breakout_with_volume is False
    assert 1.0 <= signal.breakout_volume_ratio < 1.5
    assert "box_breakout" in signal.breakout_reason


def test_detect_breakout_signal_identifies_wedge_breakout():
    signal = detect_breakout_signal(_wedge_breakout_history())

    assert signal.breakout_hit is True
    assert signal.breakout_type == "wedge_breakout"
    assert signal.breakout_with_volume is False
    assert signal.breakout_volume_ratio < 1.5
    assert "wedge_breakout" in signal.breakout_reason


def test_detect_breakout_signal_returns_no_hit_when_close_does_not_clear_resistance():
    signal = detect_breakout_signal(_no_breakout_history())

    assert signal.breakout_hit is False
    assert signal.breakout_type is None
    assert signal.breakout_with_volume is False
    assert "close_not_above_resistance" in signal.breakout_reason


def test_detect_breakout_signal_marks_insufficient_history():
    short_history = _platform_breakout_history().tail(BREAKOUT_HISTORY_MIN_BARS - 20)

    signal = detect_breakout_signal(short_history)

    assert signal.breakout_hit is False
    assert signal.breakout_type is None
    assert signal.breakout_with_volume is False
    assert signal.breakout_volume_ratio is None
    assert signal.breakout_reason == "insufficient_breakout_history"
