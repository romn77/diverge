from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd

from tradingagents.data.manifest_schema import COMMON_MANIFEST_COLUMNS, COMPARE_MANIFEST_COLUMNS
from tradingagents.dataflows.akshare_stock import _import_akshare
from tradingagents.dataflows.cn_market_utils import infer_cn_exchange
from tradingagents.dataflows.tushare_common import get_tushare_pro_client
from tradingagents.dataflows.vendor_errors import (
    VendorAuthError,
    VendorNotSupportedError,
    VendorRetryableError,
)

from .schema import ScreenRunConfig, build_cn_source_chain


UNIVERSE_COLUMNS = ["symbol", "market", "name", "exchange", "sector", "list_date"]
US_MANIFEST_REQUIRED_COLUMNS = COMMON_MANIFEST_COLUMNS
CN_MANIFEST_REQUIRED_COLUMNS = COMPARE_MANIFEST_COLUMNS
CN_EXCHANGE_LABELS = {
    "SH": "SSE",
    "SZ": "SZSE",
    "BJ": "BSE",
}
SPECIAL_TREATMENT_NAME_RE = re.compile(r"^(?:S\*ST|SST|\*ST|ST)", re.IGNORECASE)
UNIVERSE_RETRY_BACKOFF_SECONDS = (0.5, 1.0, 2.0)
UNIVERSE_CACHE_DIRNAME = "universe"
UNIVERSE_CACHE_MAX_AGE_SECONDS = 60 * 60 * 24


def _is_special_treatment_name(name: str) -> bool:
    normalized = "".join(str(name or "").strip().upper().split())
    return bool(SPECIAL_TREATMENT_NAME_RE.match(normalized))


def _filter_special_treatment_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "name" not in df.columns:
        return df
    return df.loc[~df["name"].map(_is_special_treatment_name)].reset_index(drop=True)


def _universe_cache_path(cache_dir: str | Path, market: str, source: str) -> Path:
    return Path(cache_dir) / UNIVERSE_CACHE_DIRNAME / f"{market}_{source}.csv"


def _load_universe_cache(
    cache_dir: str | Path,
    market: str,
    source: str,
    *,
    allow_stale: bool = False,
) -> pd.DataFrame | None:
    path = _universe_cache_path(cache_dir, market, source)
    if not path.is_file():
        return None

    cache_age_seconds = time.time() - path.stat().st_mtime
    if cache_age_seconds > UNIVERSE_CACHE_MAX_AGE_SECONDS and not allow_stale:
        return None

    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _save_universe_cache(cache_dir: str | Path, market: str, source: str, frame: pd.DataFrame) -> Path:
    path = _universe_cache_path(cache_dir, market, source)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _load_akshare_cn_universe_rows() -> pd.DataFrame:
    ak = _import_akshare()
    raw = _retry_universe_request(
        ak.stock_info_a_code_name,
        label="akshare CN universe",
    )
    if raw is None:
        return pd.DataFrame(columns=["code", "name"])
    return raw


def _retry_universe_request(loader, *, label: str) -> pd.DataFrame:
    attempt = 0
    while True:
        try:
            return loader()
        except Exception as exc:
            if attempt >= len(UNIVERSE_RETRY_BACKOFF_SECONDS):
                raise VendorRetryableError(f"{label} fetch failed: {exc}") from exc
            time.sleep(UNIVERSE_RETRY_BACKOFF_SECONDS[attempt])
            attempt += 1


def _load_cn_universe_from_source(
    data_source: str,
    cache_dir: str | Path | None = None,
) -> pd.DataFrame:
    if cache_dir is not None:
        cached = _load_universe_cache(cache_dir, "cn", data_source)
        if cached is not None:
            return _filter_special_treatment_rows(cached)

    if data_source == "akshare":
        try:
            raw = _load_akshare_cn_universe_rows()
        except VendorRetryableError:
            if cache_dir is not None:
                stale_cached = _load_universe_cache(cache_dir, "cn", data_source, allow_stale=True)
                if stale_cached is not None:
                    return _filter_special_treatment_rows(stale_cached)
            raise
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
        result = _filter_special_treatment_rows(result)
        if cache_dir is not None:
            _save_universe_cache(cache_dir, "cn", data_source, result)
        return result

    pro = get_tushare_pro_client()
    try:
        raw = _retry_universe_request(
            lambda: pro.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,name,exchange,industry,list_date",
            ),
            label="tushare CN universe",
        )
    except VendorRetryableError:
        if cache_dir is not None:
            stale_cached = _load_universe_cache(cache_dir, "cn", data_source, allow_stale=True)
            if stale_cached is not None:
                return _filter_special_treatment_rows(stale_cached)
        raise

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
    result = _filter_special_treatment_rows(result)
    if cache_dir is not None:
        _save_universe_cache(cache_dir, "cn", data_source, result)
    return result


def load_cn_universe_from_manifest(manifest_path: str) -> pd.DataFrame:
    path = Path(manifest_path)
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)

    missing_columns = [column for column in CN_MANIFEST_REQUIRED_COLUMNS if column not in raw.columns]
    if missing_columns:
        raise ValueError(f"Missing required CN manifest columns: {', '.join(missing_columns)}")

    # Avoid a top-level import cycle because cn_manifest.py imports load_cn_universe().
    from tradingagents.data.cn_manifest import build_cn_manifest

    manifest_df = build_cn_manifest(raw.loc[:, CN_MANIFEST_REQUIRED_COLUMNS])
    result = manifest_df.loc[:, COMMON_MANIFEST_COLUMNS].copy()
    result.insert(1, "market", "cn")
    result = _filter_special_treatment_rows(result)
    return result.loc[:, UNIVERSE_COLUMNS].reset_index(drop=True)


def load_cn_universe(
    data_source: str = "tushare",
    cache_dir: str | Path | None = None,
    fallback_data_sources: list[str] | None = None,
    manifest_path: str | None = None,
) -> pd.DataFrame:
    if manifest_path:
        return load_cn_universe_from_manifest(manifest_path)

    source_chain = build_cn_source_chain(data_source, fallback_data_sources)
    last_error: Exception | None = None

    for source in source_chain:
        try:
            return _load_cn_universe_from_source(
                data_source=source,
                cache_dir=cache_dir,
            )
        except (VendorRetryableError, VendorAuthError, VendorNotSupportedError) as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error

    return pd.DataFrame(columns=UNIVERSE_COLUMNS)


def load_us_universe(manifest_path: str) -> pd.DataFrame:
    path = Path(manifest_path)
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)

    missing_columns = [column for column in US_MANIFEST_REQUIRED_COLUMNS if column not in raw.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    result = raw.loc[:, US_MANIFEST_REQUIRED_COLUMNS].copy()
    result.insert(1, "market", "us")
    return result.loc[:, UNIVERSE_COLUMNS].reset_index(drop=True)


def load_universe(config: ScreenRunConfig, cache_dir: str | Path | None = None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for market in config.markets:
        if market == "cn":
            frames.append(
                load_cn_universe(
                    data_source=config.cn_data_source,
                    cache_dir=cache_dir,
                    fallback_data_sources=config.cn_data_source_fallbacks,
                    manifest_path=config.cn_manifest_path,
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
