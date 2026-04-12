from __future__ import annotations

import pandas as pd

from .market_calendar import trading_day_lag
from .schema import ScreenRunConfig


REQUIRED_FEATURE_COLUMNS = [
    "avg_amount_20d",
    "ma20",
    "ma60",
    "ret_20",
    "ret_60",
    "rsi",
    "macdh",
    "atr_pct",
    "vwma",
]
MAX_STALE_BUSINESS_DAYS = 3


def _missing_required_features(row: pd.Series) -> bool:
    return any(pd.isna(row.get(column)) for column in REQUIRED_FEATURE_COLUMNS)


def _is_stale_data(row: pd.Series) -> bool:
    lag = trading_day_lag(
        str(row.get("market") or ""),
        row.get("as_of_date"),
        row.get("data_end_date"),
    )
    return lag is not None and lag > MAX_STALE_BUSINESS_DAYS


def _price_floor_drop_reason(row: pd.Series, config: ScreenRunConfig) -> str | None:
    close = pd.to_numeric(row.get("close"), errors="coerce")
    if pd.isna(close):
        return None

    market = str(row.get("market") or "").strip().lower()
    if market == "cn" and float(close) < config.cn_min_price:
        return "low_price_cn"
    if market == "us" and float(close) < config.us_min_price:
        return "low_price_us"
    return None


def _has_insufficient_trading_continuity(row: pd.Series, config: ScreenRunConfig) -> bool:
    trading_days_20d = pd.to_numeric(row.get("trading_days_20d"), errors="coerce")
    return pd.isna(trading_days_20d) or float(trading_days_20d) < config.min_trading_days_20d


def apply_hard_filters(
    features_df: pd.DataFrame,
    config: ScreenRunConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    kept_rows: list[dict] = []
    dropped_rows: list[dict] = []

    for _, row in features_df.iterrows():
        reason = row.get("drop_reason")
        if reason:
            dropped_rows.append({**row.to_dict(), "drop_reason": reason})
            continue

        if _is_stale_data(row):
            dropped_rows.append({**row.to_dict(), "drop_reason": "stale_data"})
            continue

        if int(row.get("bar_count", 0) or 0) < 60:
            dropped_rows.append({**row.to_dict(), "drop_reason": "insufficient_bars"})
            continue

        if _missing_required_features(row):
            dropped_rows.append({**row.to_dict(), "drop_reason": "missing_features"})
            continue

        price_floor_reason = _price_floor_drop_reason(row, config)
        if price_floor_reason is not None:
            dropped_rows.append({**row.to_dict(), "drop_reason": price_floor_reason})
            continue

        if _has_insufficient_trading_continuity(row, config):
            dropped_rows.append({**row.to_dict(), "drop_reason": "insufficient_trading_days_20d"})
            continue

        if row["market"] == "cn" and float(row["avg_amount_20d"]) < config.cn_min_avg_amount_20d:
            dropped_rows.append({**row.to_dict(), "drop_reason": "illiquid_cn"})
            continue

        if row["market"] == "us" and float(row["avg_amount_20d"]) < config.us_min_avg_dollar_volume_20d:
            dropped_rows.append({**row.to_dict(), "drop_reason": "illiquid_us"})
            continue

        kept_rows.append(row.to_dict())

    kept = pd.DataFrame(kept_rows, columns=features_df.columns)
    dropped_columns = list(features_df.columns)
    if "drop_reason" not in dropped_columns:
        dropped_columns.append("drop_reason")
    dropped = pd.DataFrame(dropped_rows, columns=dropped_columns)
    return kept, dropped
