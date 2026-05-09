from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schema import ScreenRunConfig
from .sync import FUNDAMENTAL_FIELDS


FUNDAMENTAL_METADATA_COLUMNS = {
    "symbol",
    "market",
    "source",
    "as_of_date",
    "report_period",
    "updated_at",
    "missing_fields",
    "data_status",
}


def _snapshot_path(config: ScreenRunConfig, market: str) -> Path:
    source = (
        config.cn_fundamental_source if market == "cn" else config.us_fundamental_source
    )
    return Path(config.fundamental_dir) / source / market / "snapshots.csv"


def _load_market_snapshot(config: ScreenRunConfig, market: str) -> pd.DataFrame:
    path = _snapshot_path(config, market)
    if not path.is_file():
        return pd.DataFrame(columns=["symbol", "market", *FUNDAMENTAL_FIELDS])
    frame = pd.read_csv(path)
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "market", *FUNDAMENTAL_FIELDS])
    frame = frame.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    frame["market"] = frame.get("market", market).astype(str).str.strip().str.lower()
    for column in FUNDAMENTAL_FIELDS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def load_fundamental_snapshots(config: ScreenRunConfig) -> pd.DataFrame:
    frames = [_load_market_snapshot(config, market) for market in config.markets]
    usable = [frame for frame in frames if not frame.empty]
    if not usable:
        return pd.DataFrame(columns=["symbol", "market", *FUNDAMENTAL_FIELDS])
    combined = pd.concat(usable, ignore_index=True, sort=False)
    sort_columns = [
        column
        for column in ("updated_at", "as_of_date", "report_period")
        if column in combined.columns
    ]
    if sort_columns:
        combined = combined.sort_values(sort_columns)
    return combined.groupby(["market", "symbol"], as_index=False).tail(1)


def enrich_features_with_fundamentals(
    features_df: pd.DataFrame,
    config: ScreenRunConfig,
) -> pd.DataFrame:
    if features_df.empty:
        return features_df

    fundamentals = load_fundamental_snapshots(config)
    if fundamentals.empty:
        result = features_df.copy()
        for column in FUNDAMENTAL_FIELDS:
            if column not in result.columns:
                result[column] = pd.NA
        result["fundamental_data_status"] = "missing_snapshot"
        return result

    fundamental_columns = [
        column
        for column in fundamentals.columns
        if column in FUNDAMENTAL_FIELDS or column in FUNDAMENTAL_METADATA_COLUMNS
    ]
    right = fundamentals.loc[:, fundamental_columns].rename(
        columns={
            "source": "fundamental_source",
            "as_of_date": "fundamental_as_of_date",
            "report_period": "fundamental_report_period",
            "updated_at": "fundamental_updated_at",
            "missing_fields": "fundamental_missing_fields",
            "data_status": "fundamental_data_status",
        }
    )
    result = features_df.merge(right, on=["symbol", "market"], how="left")
    for column in FUNDAMENTAL_FIELDS:
        if column not in result.columns:
            result[column] = pd.NA
    result["fundamental_data_status"] = result["fundamental_data_status"].fillna(
        "missing"
    )
    return result
