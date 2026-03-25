from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from tradingagents.dataflows.akshare_stock import _import_akshare
from tradingagents.dataflows.cn_market_utils import infer_cn_exchange
from tradingagents.dataflows.tushare_common import get_tushare_pro_client

from .schema import ScreenRunConfig


UNIVERSE_COLUMNS = ["symbol", "market", "name", "exchange", "sector", "list_date"]
US_MANIFEST_REQUIRED_COLUMNS = ["symbol", "name", "exchange", "sector", "list_date"]
CN_EXCHANGE_LABELS = {
    "SH": "SSE",
    "SZ": "SZSE",
    "BJ": "BSE",
}
SPECIAL_TREATMENT_NAME_RE = re.compile(r"^(?:S\*ST|SST|\*ST|ST)", re.IGNORECASE)


def _is_special_treatment_name(name: str) -> bool:
    normalized = "".join(str(name or "").strip().upper().split())
    return bool(SPECIAL_TREATMENT_NAME_RE.match(normalized))


def _filter_special_treatment_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "name" not in df.columns:
        return df
    return df.loc[~df["name"].map(_is_special_treatment_name)].reset_index(drop=True)


def _load_akshare_cn_universe_rows() -> pd.DataFrame:
    ak = _import_akshare()
    raw = ak.stock_info_a_code_name()
    if raw is None:
        return pd.DataFrame(columns=["code", "name"])
    return raw


def load_cn_universe(data_source: str = "tushare") -> pd.DataFrame:
    if data_source == "akshare":
        raw = _load_akshare_cn_universe_rows()
        if raw is None or raw.empty:
            raw = pd.DataFrame(columns=["code", "name"])

        normalized = raw.copy()
        normalized["code"] = normalized["code"].astype(str).str.zfill(6)
        normalized["exchange_code"] = normalized["code"].map(infer_cn_exchange)
        normalized["symbol"] = normalized["code"] + "." + normalized["exchange_code"]
        normalized["exchange"] = normalized["exchange_code"].map(CN_EXCHANGE_LABELS)
        normalized["sector"] = ""
        normalized["list_date"] = ""
        result = (
            normalized.loc[:, ["symbol", "name", "exchange", "sector", "list_date"]]
            .assign(market="cn")
            .loc[:, UNIVERSE_COLUMNS]
            .fillna("")
        )
        return _filter_special_treatment_rows(result)

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
    return _filter_special_treatment_rows(result)


def load_us_universe(manifest_path: str) -> pd.DataFrame:
    path = Path(manifest_path)
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)

    missing_columns = [column for column in US_MANIFEST_REQUIRED_COLUMNS if column not in raw.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    result = raw.loc[:, US_MANIFEST_REQUIRED_COLUMNS].copy()
    result.insert(1, "market", "us")
    return result.loc[:, UNIVERSE_COLUMNS].reset_index(drop=True)


def load_universe(config: ScreenRunConfig) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for market in config.markets:
        if market == "cn":
            frames.append(
                load_cn_universe(
                    data_source=config.cn_data_source,
                )
            )
        elif market == "us":
            frames.append(
                load_us_universe(
                    manifest_path=config.us_manifest_path or "",
                )
            )

    if not frames:
        return pd.DataFrame(columns=UNIVERSE_COLUMNS)

    return pd.concat(frames, ignore_index=True)
