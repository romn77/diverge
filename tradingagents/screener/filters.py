from __future__ import annotations

import pandas as pd

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
