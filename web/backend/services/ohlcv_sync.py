from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

from diverge.screener.schema import ScreenRunConfig
from diverge.screener.stages import prepare_universe_stage
from diverge.screener.sync import sync_ohlcv_cache
from diverge.screener.universe import load_universe
from web.backend.services import ohlcv_readiness, ohlcv_sync_payloads

ProgressCallback = Callable[..., None]
BuildConfigPayload = Callable[[dict[str, Any]], dict[str, Any]]
EnsureVendorReady = Callable[[dict[str, Any]], None]
SyncOhlcvCache = Callable[..., Any]
ScreenRunConfigFactory = Callable[..., ScreenRunConfig]
PrepareUniverseStage = Callable[..., Any]
LoadUniverse = Callable[..., Any]


def build_ohlcv_config_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return ohlcv_sync_payloads.build_ohlcv_config_payload(payload)


def _result_to_dict(result: Any) -> dict[str, Any]:
    if is_dataclass(result):
        return asdict(result)
    return dict(result)


def run_ohlcv_sync_payload(
    payload: dict[str, Any],
    *,
    progress_callback: ProgressCallback | None = None,
    ensure_vendor_ready: EnsureVendorReady = ohlcv_readiness.ensure_ohlcv_vendor_ready,
    build_config_payload: BuildConfigPayload = build_ohlcv_config_payload,
    sync_ohlcv_cache_fn: SyncOhlcvCache = sync_ohlcv_cache,
    config_factory: ScreenRunConfigFactory = ScreenRunConfig,
) -> dict[str, Any]:
    ensure_vendor_ready(payload)
    config_payload = build_config_payload(payload)
    result = sync_ohlcv_cache_fn(
        config_factory(**config_payload),
        progress_callback=progress_callback,
    )
    return _result_to_dict(result)


def _symbols_by_market(frame: Any, *, dedupe: bool) -> dict[str, list[str]]:
    symbols_by_market: dict[str, list[str]] = {}
    if frame.empty:
        return symbols_by_market
    for market, market_frame in frame.groupby("market"):
        symbols = [
            str(symbol).strip()
            for symbol in market_frame["symbol"].tolist()
            if str(symbol).strip()
        ]
        if dedupe:
            symbols = list(dict.fromkeys(symbols))
        symbols_by_market[str(market).strip().lower()] = symbols
    return symbols_by_market


def resolve_prefiltered_symbols(
    payload: dict[str, Any],
    *,
    build_config_payload: BuildConfigPayload = build_ohlcv_config_payload,
    config_factory: ScreenRunConfigFactory = ScreenRunConfig,
    prepare_universe_stage_fn: PrepareUniverseStage = prepare_universe_stage,
) -> dict[str, list[str]]:
    config_payload = build_config_payload(payload)
    config = config_factory(**config_payload)
    universe_stage = prepare_universe_stage_fn(config, Path(config.cache_dir))
    return _symbols_by_market(universe_stage.prefiltered_df, dedupe=False)


def resolve_universe_symbols(
    payload: dict[str, Any],
    *,
    build_config_payload: BuildConfigPayload = build_ohlcv_config_payload,
    config_factory: ScreenRunConfigFactory = ScreenRunConfig,
    load_universe_fn: LoadUniverse = load_universe,
) -> dict[str, list[str]]:
    config_payload = build_config_payload(payload)
    config = config_factory(**config_payload)
    universe_df = load_universe_fn(config, cache_dir=Path(config.cache_dir))
    return _symbols_by_market(universe_df, dedupe=True)
