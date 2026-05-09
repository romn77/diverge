from __future__ import annotations

import re

import pandas as pd

from diverge.common.market_calendar import count_trading_days

from .schema import ScreenRunConfig
from .universe_rules import cap_market_bucket_rows, us_prefilter_drop_reason


CN_PRIMARY_EXCHANGES = {"SSE", "SZSE"}
CN_SPECIAL_TREATMENT_NAME_RE = re.compile(r"^(?:S\*ST|SST|\*ST|ST)", re.IGNORECASE)


def _is_too_new(row: pd.Series, config: ScreenRunConfig) -> bool:
    if not row.get("list_date"):
        return False

    list_date = pd.to_datetime(str(row["list_date"]), errors="coerce")
    as_of_date = pd.to_datetime(config.as_of_date, errors="coerce")
    if pd.isna(list_date) or pd.isna(as_of_date):
        return False

    return (as_of_date - list_date).days < config.min_listing_days


def _is_cn_special_treatment(name: object) -> bool:
    normalized = "".join(str(name or "").strip().upper().split())
    return bool(CN_SPECIAL_TREATMENT_NAME_RE.match(normalized))


def _cn_prefilter_drop_reason(row: pd.Series, config: ScreenRunConfig) -> str | None:
    if str(row.get("market") or "").strip().lower() != "cn":
        return None

    exchange = str(row.get("exchange") or "").strip().upper()
    if exchange not in CN_PRIMARY_EXCHANGES:
        return "cn_exchange"
    if _is_cn_special_treatment(row.get("name")):
        return "cn_special_treatment"
    if not row.get("list_date"):
        return None

    trading_days = count_trading_days(
        "cn",
        row.get("list_date"),
        config.as_of_date,
        fallback_to_weekdays=True,
    )
    if trading_days is not None and trading_days < config.cn_min_listing_trading_days:
        return "too_new"
    return None


def _apply_market_bucket_caps(
    kept_df: pd.DataFrame,
    config: ScreenRunConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if kept_df.empty:
        dropped_columns = list(kept_df.columns)
        if "drop_reason" not in dropped_columns:
            dropped_columns.append("drop_reason")
        return kept_df.copy(), pd.DataFrame(columns=dropped_columns)

    capped_frames: list[pd.DataFrame] = []
    dropped_frames: list[pd.DataFrame] = []
    for market, limit in (
        ("cn", config.cn_universe_cap),
        ("us", config.us_universe_cap),
    ):
        market_rows = (
            kept_df.loc[kept_df["market"] == market].copy().reset_index(drop=True)
        )
        if market_rows.empty:
            continue

        kept_rows, dropped_rows = cap_market_bucket_rows(
            kept_df,
            market=market,
            limit=limit,
        )
        capped_frames.append(kept_rows)
        if not dropped_rows.empty:
            dropped_frames.append(dropped_rows.assign(drop_reason=f"{market}_cap"))

    other_rows = (
        kept_df.loc[~kept_df["market"].isin({"cn", "us"})].copy().reset_index(drop=True)
    )
    if not other_rows.empty:
        capped_frames.append(other_rows)

    capped = (
        pd.concat(capped_frames, ignore_index=True, sort=False)
        if capped_frames
        else pd.DataFrame(columns=kept_df.columns)
    )
    dropped_columns = list(kept_df.columns)
    if "drop_reason" not in dropped_columns:
        dropped_columns.append("drop_reason")
    dropped = (
        pd.concat(dropped_frames, ignore_index=True, sort=False)
        if dropped_frames
        else pd.DataFrame(columns=dropped_columns)
    )
    return capped, dropped.loc[:, dropped_columns]


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
        market = str(row.get("market") or "").strip().lower()
        if market == "cn":
            cn_drop_reason = _cn_prefilter_drop_reason(row, config)
            if cn_drop_reason is not None:
                dropped_rows.append({**row.to_dict(), "drop_reason": cn_drop_reason})
                continue
        else:
            if _is_too_new(row, config):
                dropped_rows.append({**row.to_dict(), "drop_reason": "too_new"})
                continue
            us_drop_reason = us_prefilter_drop_reason(row)
            if us_drop_reason is not None:
                dropped_rows.append({**row.to_dict(), "drop_reason": us_drop_reason})
                continue
        kept_rows.append(row.to_dict())

    kept = pd.DataFrame(kept_rows, columns=universe_df.columns)
    kept, cap_dropped = _apply_market_bucket_caps(kept, config)
    if not cap_dropped.empty:
        dropped_rows.extend(cap_dropped.to_dict("records"))
    dropped_columns = list(universe_df.columns)
    if "drop_reason" not in dropped_columns:
        dropped_columns.append("drop_reason")
    dropped = pd.DataFrame(dropped_rows, columns=dropped_columns)
    return kept, dropped
