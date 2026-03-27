from __future__ import annotations

import re

import pandas as pd

from .schema import ScreenRunConfig


US_NON_PRIMARY_SYMBOL_SUFFIXES = {"U", "UN", "W", "R"}
US_ALLOWED_DOT_SUFFIXES = {"A", "B", "C", "V"}
US_NON_PRIMARY_NAME_RE = re.compile(r"\b(WARRANT|WARRANTS|RIGHT|RIGHTS|UNIT|UNITS)\b", re.IGNORECASE)
US_SPAC_NAME_RE = re.compile(r"\bACQUISITION\b", re.IGNORECASE)
US_TEST_LISTING_NAME_RE = re.compile(r"\bTICK PILOT TEST\b", re.IGNORECASE)
US_TEST_LISTING_SYMBOL_RE = re.compile(r"^(?:A|C|N|P)TEST(?:[.-]|$)", re.IGNORECASE)


def _is_too_new(row: pd.Series, config: ScreenRunConfig) -> bool:
    if not row.get("list_date"):
        return False

    list_date = pd.to_datetime(str(row["list_date"]), errors="coerce")
    as_of_date = pd.to_datetime(config.as_of_date, errors="coerce")
    if pd.isna(list_date) or pd.isna(as_of_date):
        return False

    return (as_of_date - list_date).days < config.min_listing_days


def _us_prefilter_drop_reason(row: pd.Series) -> str | None:
    if str(row.get("market") or "").strip().lower() != "us":
        return None

    symbol = str(row.get("symbol") or "").strip().upper()
    name = str(row.get("name") or "").strip()
    suffix = symbol.split(".")[-1] if "." in symbol else ""

    if US_TEST_LISTING_NAME_RE.search(name) or US_TEST_LISTING_SYMBOL_RE.match(symbol):
        return "us_test_listing"
    if suffix in US_NON_PRIMARY_SYMBOL_SUFFIXES or US_NON_PRIMARY_NAME_RE.search(name):
        return "us_non_primary_issue"
    if US_SPAC_NAME_RE.search(name):
        return "us_spac"
    if "." in symbol and suffix not in US_ALLOWED_DOT_SUFFIXES:
        return "us_symbol_variant"
    return None


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
        us_drop_reason = _us_prefilter_drop_reason(row)
        if us_drop_reason is not None:
            dropped_rows.append({**row.to_dict(), "drop_reason": us_drop_reason})
            continue
        kept_rows.append(row.to_dict())

    kept = pd.DataFrame(kept_rows, columns=universe_df.columns)
    dropped_columns = list(universe_df.columns)
    if "drop_reason" not in dropped_columns:
        dropped_columns.append("drop_reason")
    dropped = pd.DataFrame(dropped_rows, columns=dropped_columns)
    return kept, dropped
