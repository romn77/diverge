from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

DEFAULT_HORIZONS = (1, 3, 5, 10, 20)


def _event_rows(
    signal_events: list[dict[str, Any]] | pd.DataFrame,
) -> list[dict[str, Any]]:
    if isinstance(signal_events, pd.DataFrame):
        return signal_events.to_dict(orient="records")
    return [dict(row) for row in signal_events]


def _cost(cost_model: dict[str, Any] | None) -> float:
    model = cost_model or {}
    return (
        float(model.get("buy_fee", 0) or 0)
        + float(model.get("sell_fee", 0) or 0)
        + float(model.get("stamp_tax_sell", 0) or 0)
        + (float(model.get("slippage", 0) or 0) * 2)
    )


def run_backtest_snapshot(
    *,
    strategy_id: str,
    signal_events: list[dict[str, Any]] | pd.DataFrame,
    price_history: pd.DataFrame,
    cost_model: dict[str, Any] | None = None,
    benchmark_history: pd.DataFrame | None = None,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    run_id: str | None = None,
) -> dict[str, Any]:
    events = _event_rows(signal_events)
    prices = price_history.copy()
    if prices.empty or not events:
        return {
            "strategy_id": strategy_id,
            "run_id": run_id
            or f"bt_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "engine": "event_study",
            "status": "unavailable",
            "sample_size": 0,
            "holding_periods": {},
            "risk_notes": ["insufficient_sample"],
            "data_quality_notes": ["No signal events or price history were available."],
        }
    prices["trade_date"] = pd.to_datetime(prices["trade_date"])
    prices = prices.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    by_symbol = {
        symbol: frame.reset_index(drop=True)
        for symbol, frame in prices.groupby("symbol")
    }
    total_cost = _cost(cost_model)
    outcomes: list[dict[str, Any]] = []
    for event in events:
        symbol = str(event.get("symbol") or "")
        frame = by_symbol.get(symbol)
        if frame is None or frame.empty:
            continue
        signal_date = pd.to_datetime(event.get("trade_date"))
        after = frame.index[frame["trade_date"] > signal_date].tolist()
        if not after:
            outcomes.append(
                {
                    "symbol": symbol,
                    "trade_date": str(event.get("trade_date")),
                    "skipped_reason": "no_t_plus_1_bar",
                }
            )
            continue
        entry_idx = after[0]
        entry = frame.iloc[entry_idx]
        entry_price = (
            entry.get("open") if pd.notna(entry.get("open")) else entry.get("close")
        )
        if not entry_price or pd.isna(entry_price):
            outcomes.append(
                {
                    "symbol": symbol,
                    "trade_date": str(event.get("trade_date")),
                    "skipped_reason": "missing_entry_price",
                }
            )
            continue
        base: dict[str, Any] = {
            "symbol": symbol,
            "trade_date": str(event.get("trade_date")),
            "entry_date": entry["trade_date"].date().isoformat(),
            "entry_price": float(entry_price),
            "skipped_reason": None,
        }
        for horizon in horizons:
            exit_idx = entry_idx + horizon - 1
            if exit_idx >= len(frame):
                base[f"return_{horizon}d"] = None
                base[f"mae_{horizon}d"] = None
                continue
            window = frame.iloc[entry_idx : exit_idx + 1]
            exit_price = window.iloc[-1].get("close")
            low_price = (
                pd.to_numeric(window.get("low"), errors="coerce").min()
                if "low" in window
                else None
            )
            if pd.isna(exit_price):
                base[f"return_{horizon}d"] = None
            else:
                base[f"return_{horizon}d"] = (
                    float(exit_price) / float(entry_price) - 1 - total_cost
                )
            base[f"mae_{horizon}d"] = (
                (float(low_price) / float(entry_price) - 1)
                if low_price and not pd.isna(low_price)
                else None
            )
        outcomes.append(base)
    outcome_df = pd.DataFrame(outcomes)
    holding_periods: dict[str, Any] = {}
    for horizon in horizons:
        column = f"return_{horizon}d"
        if column not in outcome_df.columns:
            continue
        values = pd.to_numeric(outcome_df[column], errors="coerce").dropna()
        if len(values) == 0:
            continue
        mae_values = pd.to_numeric(
            outcome_df.get(f"mae_{horizon}d"), errors="coerce"
        ).dropna()
        holding_periods[f"{horizon}d"] = {
            "sample_size": int(len(values)),
            "win_rate": round(float((values > 0).mean()), 4),
            "avg_return": round(float(values.mean()), 6),
            "median_return": round(float(values.median()), 6),
            "max_adverse_excursion_median": round(float(mae_values.median()), 6)
            if len(mae_values)
            else None,
        }
    return {
        "strategy_id": strategy_id,
        "run_id": run_id
        or f"bt_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "engine": "event_study",
        "engine_version": "phase2-v1",
        "status": "completed" if holding_periods else "unavailable",
        "sample_size": int(sum(1 for row in outcomes if not row.get("skipped_reason"))),
        "holding_periods": holding_periods,
        "cost_model": cost_model or {},
        "risk_notes": ["Daily signal validation; intraday fills are not simulated."],
        "data_quality_notes": [] if holding_periods else ["insufficient_sample"],
        "signal_outcomes": outcomes,
    }


def summarize_by_horizon(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy_id": snapshot.get("strategy_id"),
        "holding_periods": snapshot.get("holding_periods") or {},
        "sample_size": snapshot.get("sample_size") or 0,
    }
