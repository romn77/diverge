from __future__ import annotations

from pathlib import Path

import pandas as pd

from tradingagents.dataflows.tushare_common import get_tushare_pro_client

from .schema import ScreenRunConfig


UNIVERSE_COLUMNS = ["symbol", "market", "name", "exchange", "sector", "list_date"]
US_MANIFEST_REQUIRED_COLUMNS = ["symbol", "name", "exchange", "sector", "list_date"]


def _limit_rows(df: pd.DataFrame, limit: int | None) -> pd.DataFrame:
    if limit is None:
        return df.reset_index(drop=True)
    return df.head(limit).reset_index(drop=True)


def load_cn_universe(limit: int | None = None) -> pd.DataFrame:
    pro = get_tushare_pro_client()
    raw = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,name,exchange,industry,list_date",
    )

    if raw is None:
        raw = pd.DataFrame(columns=["ts_code", "name", "exchange", "industry", "list_date"])

    result = (
        raw.rename(
            columns={
                "ts_code": "symbol",
                "industry": "sector",
            }
        )
        .assign(market="cn")
        .loc[:, ["symbol", "market", "name", "exchange", "sector", "list_date"]]
        .fillna("")
    )
    return _limit_rows(result, limit)


def load_us_universe(manifest_path: str, limit: int | None = None) -> pd.DataFrame:
    path = Path(manifest_path)
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)

    missing_columns = [column for column in US_MANIFEST_REQUIRED_COLUMNS if column not in raw.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    result = raw.loc[:, US_MANIFEST_REQUIRED_COLUMNS].copy()
    result.insert(1, "market", "us")
    return _limit_rows(result.loc[:, UNIVERSE_COLUMNS], limit)


def load_universe(config: ScreenRunConfig) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for market in config.markets:
        if market == "cn":
            frames.append(load_cn_universe(limit=config.limit_per_market))
        elif market == "us":
            frames.append(
                load_us_universe(
                    manifest_path=config.us_manifest_path or "",
                    limit=config.limit_per_market,
                )
            )

    if not frames:
        return pd.DataFrame(columns=UNIVERSE_COLUMNS)

    return pd.concat(frames, ignore_index=True)
