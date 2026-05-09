from __future__ import annotations

import pandas as pd
from stockstats import wrap

from .breakouts import detect_breakout_signal
from .history_cache import empty_history_frame, prepare_history_frame_for_indicators
from .market_calendar import last_n_trading_days


INDICATOR_COLUMNS = [
    "rsi",
    "macd",
    "macds",
    "macdh",
    "atr",
    "boll",
    "boll_ub",
    "boll_lb",
    "vwma",
    "mfi",
]


def _blank_feature_row(
    meta_row: pd.Series, as_of_date: str, working: pd.DataFrame
) -> dict:
    data_end_date = (
        working.iloc[-1]["Date"].strftime("%Y-%m-%d") if not working.empty else None
    )
    data_start_date = (
        working.iloc[0]["Date"].strftime("%Y-%m-%d") if not working.empty else None
    )
    row = {
        "symbol": meta_row["symbol"],
        "market": meta_row["market"],
        "name": meta_row["name"],
        "exchange": meta_row["exchange"],
        "sector": meta_row["sector"],
        "list_date": meta_row["list_date"],
        "as_of_date": as_of_date,
        "close": pd.NA,
        "volume": pd.NA,
        "amount": pd.NA,
        "avg_amount_20d": pd.NA,
        "trading_days_20d": pd.NA,
        "ma20": pd.NA,
        "ma60": pd.NA,
        "ret_20": pd.NA,
        "ret_60": pd.NA,
        "rsi": pd.NA,
        "macd": pd.NA,
        "macds": pd.NA,
        "macdh": pd.NA,
        "atr": pd.NA,
        "atr_pct": pd.NA,
        "boll": pd.NA,
        "boll_ub": pd.NA,
        "boll_lb": pd.NA,
        "vwma": pd.NA,
        "mfi": pd.NA,
        "breakout_hit": False,
        "breakout_type": None,
        "breakout_with_volume": False,
        "breakout_reason": "insufficient_breakout_history",
        "breakout_volume_ratio": pd.NA,
        "data_start_date": data_start_date,
        "data_end_date": data_end_date,
        "bar_count": len(working),
    }
    return row


def _count_recent_trading_days(meta_row: pd.Series, eligible: pd.DataFrame) -> object:
    if eligible.empty:
        return pd.NA

    expected_dates = last_n_trading_days(
        str(meta_row.get("market") or ""),
        eligible.iloc[-1]["Date"],
        20,
    )
    if not expected_dates:
        return pd.NA

    actual_dates = set(
        pd.to_datetime(eligible["Date"], errors="coerce").dt.normalize().dropna()
    )
    expected_timestamps = {pd.Timestamp(day) for day in expected_dates}
    return int(len(actual_dates.intersection(expected_timestamps)))


def _prepare_price_df(price_df: pd.DataFrame) -> pd.DataFrame:
    if price_df is None or price_df.empty:
        return empty_history_frame()
    return prepare_history_frame_for_indicators(price_df)


def _latest_row_on_or_before(
    working: pd.DataFrame, as_of_date: str
) -> tuple[pd.DataFrame, pd.Series | None]:
    as_of_dt = pd.to_datetime(as_of_date)
    eligible = working[working["Date"] <= as_of_dt].copy()
    if eligible.empty:
        return eligible, None
    return eligible, eligible.iloc[-1]


def _compute_indicator_values(eligible: pd.DataFrame) -> dict[str, object]:
    wrapped = wrap(eligible.copy())
    values: dict[str, object] = {}
    latest_index = wrapped.index[-1]

    for indicator in INDICATOR_COLUMNS:
        try:
            wrapped[indicator]
            raw_value = wrapped.loc[latest_index, indicator]
            values[indicator] = pd.NA if pd.isna(raw_value) else float(raw_value)
        except Exception:
            values[indicator] = pd.NA

    return values


def build_feature_row(
    meta_row: pd.Series, price_df: pd.DataFrame, as_of_date: str
) -> dict:
    working = _prepare_price_df(price_df)
    eligible, latest_row = _latest_row_on_or_before(working, as_of_date)
    breakout_signal = detect_breakout_signal(eligible)

    if latest_row is None:
        row = _blank_feature_row(meta_row, as_of_date, working)
        row.update(breakout_signal.to_feature_payload())
        return row

    if len(eligible) < 20:
        row = _blank_feature_row(meta_row, as_of_date, eligible)
        row["close"] = float(latest_row["Close"])
        row["volume"] = float(latest_row["Volume"])
        row["amount"] = float(latest_row["Amount"])
        row["trading_days_20d"] = _count_recent_trading_days(meta_row, eligible)
        row.update(breakout_signal.to_feature_payload())
        return row

    trailing_20 = eligible.tail(20)
    row = {
        "symbol": meta_row["symbol"],
        "market": meta_row["market"],
        "name": meta_row["name"],
        "exchange": meta_row["exchange"],
        "sector": meta_row["sector"],
        "list_date": meta_row["list_date"],
        "as_of_date": as_of_date,
        "close": float(latest_row["Close"]),
        "volume": float(latest_row["Volume"]),
        "amount": float(latest_row["Amount"]),
        "avg_amount_20d": float(trailing_20["Amount"].mean()),
        "trading_days_20d": _count_recent_trading_days(meta_row, eligible),
        "ma20": float(trailing_20["Close"].mean()),
        "ma60": float(eligible.tail(60)["Close"].mean())
        if len(eligible) >= 60
        else pd.NA,
        "ret_20": float((latest_row["Close"] / eligible.iloc[-21]["Close"]) - 1)
        if len(eligible) >= 21
        else pd.NA,
        "ret_60": float((latest_row["Close"] / eligible.iloc[-61]["Close"]) - 1)
        if len(eligible) >= 61
        else pd.NA,
        "data_start_date": eligible.iloc[0]["Date"].strftime("%Y-%m-%d"),
        "data_end_date": latest_row["Date"].strftime("%Y-%m-%d"),
        "bar_count": len(eligible),
    }

    indicator_values = _compute_indicator_values(eligible)
    row.update(indicator_values)
    row.update(breakout_signal.to_feature_payload())
    atr_value = row.get("atr")
    row["atr_pct"] = (
        float(atr_value / row["close"])
        if atr_value is not pd.NA and pd.notna(atr_value) and row["close"]
        else pd.NA
    )
    return row


def build_features_table(
    universe_df: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    as_of_date: str,
) -> pd.DataFrame:
    successful_universe = universe_df.loc[
        universe_df["symbol"].isin(histories)
    ].reset_index(drop=True)
    rows = [
        build_feature_row(row, histories[row["symbol"]], as_of_date)
        for _, row in successful_universe.iterrows()
    ]
    return pd.DataFrame(rows)
