from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Callable

from diverge.screener.sync import (
    sync_cn_tushare_fundamentals,
    sync_us_simfin_fundamentals,
)
from diverge.screener.universe import (
    load_cn_universe_from_manifest,
    load_us_universe,
)
from web.backend import app_config

DEFAULT_SIMFIN_DAILY_TICKER_LIMIT = 2500


def simfin_daily_ticker_limit() -> int:
    raw_value = os.environ.get("SIMFIN_DAILY_TICKER_LIMIT")
    if raw_value is None:
        return DEFAULT_SIMFIN_DAILY_TICKER_LIMIT
    try:
        parsed = int(raw_value.strip())
    except ValueError as exc:
        raise RuntimeError("SIMFIN_DAILY_TICKER_LIMIT must be an integer") from exc
    if parsed <= 0:
        raise RuntimeError("SIMFIN_DAILY_TICKER_LIMIT must be greater than zero")
    return parsed


def dedupe_symbols(symbols: list[Any]) -> list[str]:
    return list(
        dict.fromkeys(
            str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()
        )
    )


def resolve_fundamental_symbols(payload: dict[str, Any]) -> list[str]:
    symbols = dedupe_symbols(payload.get("symbols") or [])
    if symbols:
        return symbols

    market = str(payload["market"]).strip().lower()
    manifest_path = payload.get("manifest_path")
    if market == "us":
        manifest_path = manifest_path or app_config.resolve_manifest_path(
            "us",
            app_config.PROJECT_ROOT,
            require_exists=True,
        )
        if not manifest_path:
            return []
        universe_df = load_us_universe(str(manifest_path))
    elif market == "cn":
        manifest_path = manifest_path or app_config.resolve_manifest_path(
            "cn", app_config.PROJECT_ROOT, require_exists=True
        )
        if not manifest_path:
            return []
        universe_df = load_cn_universe_from_manifest(str(manifest_path))
    else:
        return []
    if universe_df.empty or "symbol" not in universe_df.columns:
        return []
    return dedupe_symbols(universe_df["symbol"].tolist())


def run_fundamental_sync_payload(
    payload: dict[str, Any],
    *,
    progress_callback: Callable[..., None] | None = None,
) -> dict[str, Any]:
    market = str(payload["market"]).strip().lower()
    source = str(payload["source"]).strip().lower()
    symbols = resolve_fundamental_symbols(payload)
    if market == "us" and source == "simfin":
        ticker_limit = simfin_daily_ticker_limit()
        if not symbols:
            raise RuntimeError(
                "symbols are required for US SimFin fundamental sync. "
                "Pass symbols, manifest_path, add DATA_DIR/manifest/us.csv, "
                "or set SCREEN_US_MANIFEST_PATH as a compatibility override."
            )
        if len(symbols) > ticker_limit:
            raise RuntimeError(
                f"US SimFin fundamental sync requested {len(symbols)} symbols, "
                f"which exceeds SIMFIN_DAILY_TICKER_LIMIT={ticker_limit}. "
                "Reduce DATA_DIR/manifest/us.csv or raise the limit only if your SimFin plan allows it."
            )
        api_key = os.environ.get("SIMFIN_API_KEY")
        if not api_key:
            raise RuntimeError(
                "SIMFIN_API_KEY is required for US SimFin fundamental sync."
            )
        result = sync_us_simfin_fundamentals(
            api_key=api_key,
            tickers=symbols or None,
            data_dir=payload.get("data_dir"),
            output_dir=str(app_config.FUNDAMENTALS_DIR),
            as_of_date=payload.get("as_of_date"),
        )
        return asdict(result)
    if market == "cn" and source == "tushare":
        if not symbols:
            raise RuntimeError("symbols are required for CN Tushare fundamental sync.")

        def cn_progress(current: int, total: int, symbol: str) -> None:
            if progress_callback is not None:
                progress_callback("fundamentals", current, total, symbol)

        result = sync_cn_tushare_fundamentals(
            symbols=symbols,
            output_dir=str(app_config.FUNDAMENTALS_DIR),
            as_of_date=payload.get("as_of_date"),
            progress_callback=cn_progress,
        )
        return asdict(result)
    raise RuntimeError(f"Unsupported fundamental sync route: {market}/{source}")
