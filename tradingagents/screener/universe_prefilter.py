from __future__ import annotations

import pandas as pd

from .schema import ScreenRunConfig


def _is_too_new(row: pd.Series, config: ScreenRunConfig) -> bool:
    if not row.get("list_date"):
        return False

    list_date = pd.to_datetime(str(row["list_date"]), errors="coerce")
    as_of_date = pd.to_datetime(config.as_of_date, errors="coerce")
    if pd.isna(list_date) or pd.isna(as_of_date):
        return False

    return (as_of_date - list_date).days < config.min_listing_days


def apply_universe_prefilters(
    universe_df: pd.DataFrame,
    config: ScreenRunConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if universe_df.empty:
        dropped_columns = list(universe_df.columns)
        if "drop_reason" not in dropped_columns:
            dropped_columns.append("drop_reason")
        return universe_df.copy(), pd.DataFrame(columns=dropped_columns)

    kept_rows: list[dict] = []
    dropped_rows: list[dict] = []

    for _, row in universe_df.iterrows():
        if _is_too_new(row, config):
            dropped_rows.append({**row.to_dict(), "drop_reason": "too_new"})
            continue
        kept_rows.append(row.to_dict())

    kept = pd.DataFrame(kept_rows, columns=universe_df.columns)
    dropped_columns = list(universe_df.columns)
    if "drop_reason" not in dropped_columns:
        dropped_columns.append("drop_reason")
    dropped = pd.DataFrame(dropped_rows, columns=dropped_columns)
    return kept, dropped
