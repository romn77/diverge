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


def _is_too_new(row: pd.Series, config: ScreenRunConfig) -> bool:
    if not row.get("list_date"):
        return False

    list_date = pd.to_datetime(str(row["list_date"]), errors="coerce")
    as_of_date = pd.to_datetime(row["as_of_date"], errors="coerce")
    if pd.isna(list_date) or pd.isna(as_of_date):
        return False

    return (as_of_date - list_date).days < config.min_listing_days


def _missing_required_features(row: pd.Series) -> bool:
    return any(pd.isna(row.get(column)) for column in REQUIRED_FEATURE_COLUMNS)


def _business_day_lag(as_of_date_value: object, data_end_date_value: object) -> int | None:
    return trading_day_lag("us", as_of_date_value, data_end_date_value)


def _is_stale_data(row: pd.Series) -> bool:
    lag = trading_day_lag(
        str(row.get("market") or ""),
        row.get("as_of_date"),
        row.get("data_end_date"),
    )
    return lag is not None and lag > MAX_STALE_BUSINESS_DAYS


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

        if _is_too_new(row, config):
            dropped_rows.append({**row.to_dict(), "drop_reason": "too_new"})
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
