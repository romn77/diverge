from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from diverge.market_data.history_cache import prepare_history_frame_for_indicators


BREAKOUT_HISTORY_MIN_BARS = 120
BREAKOUT_VOLUME_RATIO_THRESHOLD = 1.5
PLATFORM_LOOKBACK = 20
BOX_LOOKBACK = 40
WEDGE_LOOKBACK = 40
BREAKOUT_PRIORITY = (
    "platform_breakout",
    "box_breakout",
    "wedge_breakout",
)


@dataclass(slots=True)
class BreakoutSignal:
    breakout_hit: bool
    breakout_type: str | None
    breakout_with_volume: bool
    breakout_reason: str
    breakout_volume_ratio: float | None

    def to_feature_payload(self) -> dict[str, object]:
        return {
            "breakout_hit": self.breakout_hit,
            "breakout_type": self.breakout_type,
            "breakout_with_volume": self.breakout_with_volume,
            "breakout_reason": self.breakout_reason,
            "breakout_volume_ratio": self.breakout_volume_ratio,
        }


def _empty_signal(reason: str, *, volume_ratio: float | None = None) -> BreakoutSignal:
    return BreakoutSignal(
        breakout_hit=False,
        breakout_type=None,
        breakout_with_volume=False,
        breakout_reason=reason,
        breakout_volume_ratio=volume_ratio,
    )


def _volume_ratio(frame: pd.DataFrame) -> float | None:
    if len(frame) < 21:
        return None

    baseline = pd.to_numeric(frame.iloc[-21:-1]["Volume"], errors="coerce")
    current = pd.to_numeric(frame.iloc[-1]["Volume"], errors="coerce")
    baseline_mean = float(baseline.mean()) if baseline.notna().any() else np.nan
    if pd.isna(current) or pd.isna(baseline_mean) or baseline_mean <= 0:
        return None
    return float(current) / baseline_mean


def _breakout_strength(latest_close: float, resistance: float) -> float:
    if resistance <= 0:
        return 0.0
    return (latest_close / resistance) - 1


def _window_return(closes: pd.Series) -> float:
    first = float(closes.iloc[0])
    last = float(closes.iloc[-1])
    if first == 0:
        return 0.0
    return (last / first) - 1


def _window_range_pct(highs: pd.Series, lows: pd.Series) -> float:
    highest = float(highs.max())
    lowest = float(lows.min())
    if highest <= 0:
        return 0.0
    return (highest - lowest) / highest


def _upper_trendline_value(values: pd.Series) -> float:
    x_axis = np.arange(len(values), dtype=float)
    slope, intercept = np.polyfit(x_axis, values.astype(float).to_numpy(), 1)
    return float((slope * len(values)) + intercept)


def _platform_candidate(frame: pd.DataFrame) -> tuple[bool, float, str]:
    window = frame.iloc[-(PLATFORM_LOOKBACK + 1) : -1].copy()
    latest = frame.iloc[-1]
    resistance = float(window["High"].max())
    breakout_strength = _breakout_strength(float(latest["Close"]), resistance)
    if breakout_strength <= 0.01:
        return False, resistance, "close_not_above_resistance"

    range_pct = _window_range_pct(window["High"], window["Low"])
    if range_pct > 0.07:
        return False, resistance, f"platform_range_too_wide:{range_pct:.4f}"

    if abs(_window_return(window["Close"])) > 0.06:
        return False, resistance, "platform_drift_too_large"

    return True, resistance, f"platform_range_pct={range_pct:.4f}"


def _box_candidate(frame: pd.DataFrame) -> tuple[bool, float, str]:
    window = frame.iloc[-(BOX_LOOKBACK + 1) : -1].copy()
    latest = frame.iloc[-1]
    resistance = float(window["High"].max())
    breakout_strength = _breakout_strength(float(latest["Close"]), resistance)
    if breakout_strength <= 0.003:
        return False, resistance, "close_not_above_resistance"

    range_pct = _window_range_pct(window["High"], window["Low"])
    if range_pct < 0.05:
        return False, resistance, f"box_range_too_tight:{range_pct:.4f}"
    if range_pct > 0.18:
        return False, resistance, f"box_range_too_wide:{range_pct:.4f}"
    if abs(_window_return(window["Close"])) > 0.12:
        return False, resistance, "box_drift_too_large"

    return True, resistance, f"box_range_pct={range_pct:.4f}"


def _wedge_candidate(frame: pd.DataFrame) -> tuple[bool, float, str]:
    window = frame.iloc[-(WEDGE_LOOKBACK + 1) : -1].copy()
    latest = frame.iloc[-1]
    highs = pd.to_numeric(window["High"], errors="coerce")
    lows = pd.to_numeric(window["Low"], errors="coerce")
    if highs.isna().any() or lows.isna().any():
        return False, np.nan, "wedge_missing_prices"

    x_axis = np.arange(len(window), dtype=float)
    high_slope, high_intercept = np.polyfit(x_axis, highs.to_numpy(), 1)
    low_slope, _low_intercept = np.polyfit(x_axis, lows.to_numpy(), 1)
    projected_resistance = float((high_slope * len(window)) + high_intercept)
    breakout_strength = _breakout_strength(float(latest["Close"]), projected_resistance)
    if breakout_strength <= 0.008:
        return False, projected_resistance, "close_not_above_resistance"

    if not (high_slope < 0 and low_slope < 0 and high_slope < low_slope):
        return False, projected_resistance, "wedge_slopes_not_converging"

    opening_range = float(highs.iloc[:10].max() - lows.iloc[:10].min())
    ending_range = float(highs.iloc[-10:].max() - lows.iloc[-10:].min())
    if opening_range <= 0 or ending_range >= opening_range * 0.75:
        return False, projected_resistance, "wedge_not_contracting"

    return (
        True,
        projected_resistance,
        f"wedge_slopes=({high_slope:.4f},{low_slope:.4f})",
    )


def detect_breakout_signal(price_df: pd.DataFrame) -> BreakoutSignal:
    working = prepare_history_frame_for_indicators(price_df)
    if len(working) < BREAKOUT_HISTORY_MIN_BARS:
        return _empty_signal("insufficient_breakout_history")

    volume_ratio = _volume_ratio(working)
    breakout_with_volume = (
        volume_ratio is not None and volume_ratio >= BREAKOUT_VOLUME_RATIO_THRESHOLD
    )

    evaluators = {
        "platform_breakout": _platform_candidate,
        "box_breakout": _box_candidate,
        "wedge_breakout": _wedge_candidate,
    }
    no_hit_reasons: list[str] = []

    for breakout_type in BREAKOUT_PRIORITY:
        matched, resistance, detail = evaluators[breakout_type](working)
        if not matched:
            no_hit_reasons.append(detail)
            continue

        latest_close = float(working.iloc[-1]["Close"])
        return BreakoutSignal(
            breakout_hit=True,
            breakout_type=breakout_type,
            breakout_with_volume=breakout_with_volume,
            breakout_reason=(
                f"{breakout_type} close={latest_close:.2f} resistance={resistance:.2f} {detail}"
            ),
            breakout_volume_ratio=volume_ratio,
        )

    if no_hit_reasons and all(
        reason == "close_not_above_resistance" for reason in no_hit_reasons
    ):
        return _empty_signal(
            "close_not_above_resistance",
            volume_ratio=volume_ratio,
        )

    return _empty_signal(
        ";".join(no_hit_reasons) or "no_breakout_match",
        volume_ratio=volume_ratio,
    )
