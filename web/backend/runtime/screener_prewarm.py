from __future__ import annotations

from typing import Any

from diverge.dataflows.routes import dual_market_history_source_kwargs
from web.backend import app_config, screener_presets
from web.backend.runtime import data_sync_tasks
from web.backend.services import screener_preparation
from web.backend.services.config import get_screener_config_options_payload


def _resolve_screener_data_sources() -> dict[str, object]:
    return dual_market_history_source_kwargs(module="screener")


def default_screener_prewarm_payload(market: str, as_of_date: str) -> dict[str, Any]:
    defaults = get_screener_config_options_payload()["defaults"]
    return {
        "markets": [market],
        "as_of_date": as_of_date,
        "top_k": defaults["top_k"],
        "cn_data_source": defaults["cn_data_source"],
        "us_data_source": defaults["us_data_source"],
        "history_cache_policy": "cache_only",
        "breakout_types": list(defaults["breakout_types"]),
        "filter_preset_selections": dict(defaults["filter_preset_selections"]),
        "ranking_profile_id": defaults["ranking_profile_id"],
        "include_fundamentals": defaults["include_fundamentals"],
        "cn_fundamental_source": defaults["cn_fundamental_source"],
        "us_fundamental_source": defaults["us_fundamental_source"],
    }


def _payload_for_market(
    raw_payload: dict[str, Any], market: str, as_of_date: str
) -> dict[str, Any]:
    payload = dict(raw_payload)
    payload["markets"] = [market]
    payload["as_of_date"] = as_of_date
    payload["history_cache_policy"] = "cache_only"
    return payload


def collect_screener_prewarm_payloads(
    market: str, as_of_date: str
) -> list[dict[str, Any]]:
    payloads = [default_screener_prewarm_payload(market, as_of_date)]
    for preset in screener_presets.list_all_screener_preset_configs():
        config = preset.get("config") or {}
        configured_markets = set(config.get("markets") or [])
        if configured_markets and market not in configured_markets:
            continue
        payloads.append(_payload_for_market(config, market, as_of_date))
    return payloads


def build_screener_config_payload(request_payload: dict[str, Any]) -> dict[str, Any]:
    default_path = app_config.default_manifest_path("us")
    try:
        return screener_preparation.build_screener_config_payload(
            request_payload,
            data_source_resolver=lambda markets: _resolve_screener_data_sources(),
            us_manifest_error=(
                "US screener prewarm requires a manifest at "
                f"{default_path} or SCREEN_US_MANIFEST_PATH."
            ),
        )
    except screener_preparation.ScreenerPreparationError as exc:
        raise RuntimeError(str(exc)) from exc


def build_ohlcv_sync_payload(market: str, as_of_date: str) -> dict[str, Any]:
    defaults = get_screener_config_options_payload()["defaults"]
    payload: dict[str, Any] = {
        "markets": [market],
        "as_of_date": as_of_date,
        "top_k": min(int(defaults["top_k"]), 100),
    }
    payload.update(_resolve_screener_data_sources())
    if market == "cn":
        manifest_path = app_config.resolve_manifest_path("cn", require_exists=True)
        if manifest_path:
            payload["cn_manifest_path"] = str(manifest_path)
    if market == "us":
        manifest_path = app_config.resolve_manifest_path("us", require_exists=True)
        if not manifest_path:
            default_path = app_config.default_manifest_path("us")
            raise RuntimeError(
                "US OHLCV sync requires a manifest at "
                f"{default_path} or SCREEN_US_MANIFEST_PATH."
            )
        payload["us_manifest_path"] = str(manifest_path)
    return payload


def build_fundamental_sync_payload(
    market: str,
    as_of_date: str,
    *,
    symbols: list[str],
) -> dict[str, Any]:
    defaults = get_screener_config_options_payload()["defaults"]
    if market == "cn":
        return {
            "market": "cn",
            "source": defaults["cn_fundamental_source"],
            "symbols": symbols,
            "as_of_date": as_of_date,
        }
    return {
        "market": "us",
        "source": defaults["us_fundamental_source"],
        "symbols": symbols,
        "as_of_date": as_of_date,
    }


def run_fundamental_prewarm_sync(
    market: str,
    as_of_date: str,
    *,
    ohlcv_payload: dict[str, Any],
) -> dict[str, Any]:
    symbols_by_market = data_sync_tasks.resolve_universe_symbols(ohlcv_payload)
    symbols = symbols_by_market.get(market, [])
    if not symbols:
        return {
            "market": market,
            "as_of_date": as_of_date,
            "status": "skipped",
            "reason": "no_universe_symbols",
        }
    payload = build_fundamental_sync_payload(market, as_of_date, symbols=symbols)
    return data_sync_tasks.run_fundamental_sync_payload(payload)
