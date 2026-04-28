from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, time as day_time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from tradingagents.dataflows import vendor_usage
from tradingagents.screener.market_calendar import latest_trading_day_on_or_before
from tradingagents.screener.schema import ScreenRunConfig
from web.backend import app_config, screener_presets, screener_results
from web.backend.runtime import screener_tasks
from web.backend.services.config import get_screener_config_options_payload

logger = logging.getLogger(__name__)

MARKET_CLOSE_RULES: dict[str, tuple[str, day_time]] = {
    "cn": ("Asia/Shanghai", day_time(hour=15, minute=30)),
    "us": ("America/New_York", day_time(hour=16, minute=30)),
}
PREWARM_STATE_FILENAME = "prewarm_state.json"
_SCHEDULER_THREAD: threading.Thread | None = None
_SCHEDULER_STOP = threading.Event()


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _positive_int_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        parsed = int(raw_value.strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def screener_prewarm_enabled() -> bool:
    return _env_bool("SCREENER_PREWARM_ENABLED", False)


def _prewarm_state_path() -> Path:
    return app_config.SCREENER_STATE_DIR / PREWARM_STATE_FILENAME


def _load_prewarm_state() -> dict[str, str]:
    path = _prewarm_state_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    completed = payload.get("completed")
    return dict(completed) if isinstance(completed, dict) else {}


def _save_prewarm_state(state: dict[str, str]) -> None:
    path = _prewarm_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"completed": state}, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def due_market_trading_day(market: str, now_utc: datetime | None = None) -> str | None:
    rule = MARKET_CLOSE_RULES.get(market)
    if rule is None:
        return None

    zone_name, close_time = rule
    now = now_utc or datetime.now(timezone.utc)
    local_now = now.astimezone(ZoneInfo(zone_name))
    if local_now.timetz().replace(tzinfo=None) < close_time:
        return None

    trading_day = latest_trading_day_on_or_before(market, local_now.date())
    return trading_day.isoformat() if trading_day is not None else None


def _enabled_markets() -> list[str]:
    options = get_screener_config_options_payload()
    return [
        str(market["value"])
        for market in options["markets"]
        if market.get("enabled")
    ]


def _resolve_screener_data_sources() -> dict[str, object]:
    cn_chain = vendor_usage.get_data_source_route(
        module="screener",
        market="cn",
        category="core_stock_apis",
    ) or ["tushare"]
    us_chain = vendor_usage.get_data_source_route(
        module="screener",
        market="us",
        category="core_stock_apis",
    ) or ["massive"]
    return {
        "cn_data_source": cn_chain[0],
        "cn_data_source_fallbacks": cn_chain[1:],
        "us_data_source": us_chain[0],
        "us_data_source_fallbacks": us_chain[1:],
    }


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


def _payload_for_market(raw_payload: dict[str, Any], market: str, as_of_date: str) -> dict[str, Any]:
    payload = dict(raw_payload)
    payload["markets"] = [market]
    payload["as_of_date"] = as_of_date
    payload["history_cache_policy"] = "cache_only"
    return payload


def collect_screener_prewarm_payloads(market: str, as_of_date: str) -> list[dict[str, Any]]:
    payloads = [default_screener_prewarm_payload(market, as_of_date)]
    for preset in screener_presets.list_all_screener_preset_configs():
        config = preset.get("config") or {}
        configured_markets = set(config.get("markets") or [])
        if configured_markets and market not in configured_markets:
            continue
        payloads.append(_payload_for_market(config, market, as_of_date))
    return payloads


def build_screener_config_payload(request_payload: dict[str, Any]) -> dict[str, Any]:
    config_payload = dict(request_payload)
    config_payload.update(_resolve_screener_data_sources())
    config_payload["output_dir"] = str(app_config.SCREENER_RESULTS_DIR)
    config_payload["cache_dir"] = str(app_config.SCREENER_CACHE_DIR)
    config_payload["history_dir"] = str(app_config.STOCK_HISTORY_DIR)
    config_payload["fundamental_dir"] = str(app_config.FUNDAMENTALS_DIR)
    if "cn" in config_payload["markets"]:
        manifest_path = os.environ.get("SCREEN_CN_MANIFEST_PATH")
        if manifest_path:
            config_payload["cn_manifest_path"] = manifest_path
    if "us" in config_payload["markets"]:
        manifest_path = os.environ.get("SCREEN_US_MANIFEST_PATH")
        if not manifest_path:
            raise RuntimeError("SCREEN_US_MANIFEST_PATH is required for US screener prewarm.")
        config_payload["us_manifest_path"] = manifest_path
    ScreenRunConfig(**config_payload)
    return config_payload


def enqueue_screener_prewarm_tasks(market: str, as_of_date: str) -> int:
    enqueued = 0
    pending_keys: set[str] = set()
    for request_payload in collect_screener_prewarm_payloads(market, as_of_date):
        config_payload = build_screener_config_payload(request_payload)
        screener_key = screener_results.screener_key_for_config(config_payload)
        if (
            screener_key in pending_keys
            or screener_results.get_cached_screener_result(config_payload) is not None
        ):
            continue
        request_payload = dict(request_payload)
        request_payload["screener_key"] = screener_key
        screener_tasks.create_screener_task(
            request_payload=request_payload,
            config_payload=config_payload,
            owner_user_id=None,
            tenant_id=None,
        )
        pending_keys.add(screener_key)
        enqueued += 1
    return enqueued


def run_due_screener_prewarm_once(now_utc: datetime | None = None) -> dict[str, int]:
    state = _load_prewarm_state()
    enqueued_by_market: dict[str, int] = {}
    for market in _enabled_markets():
        trading_day = due_market_trading_day(market, now_utc)
        if trading_day is None or state.get(market) == trading_day:
            continue
        enqueued_by_market[market] = enqueue_screener_prewarm_tasks(market, trading_day)
        state[market] = trading_day
    if enqueued_by_market:
        _save_prewarm_state(state)
    return enqueued_by_market


def _scheduler_loop() -> None:
    interval_seconds = _positive_int_env("SCREENER_PREWARM_POLL_SECONDS", 300)
    while not _SCHEDULER_STOP.is_set():
        try:
            run_due_screener_prewarm_once()
        except Exception:  # pragma: no cover
            logger.exception("screener prewarm scheduler tick failed")
        _SCHEDULER_STOP.wait(interval_seconds)


def start_screener_prewarm_scheduler() -> None:
    global _SCHEDULER_THREAD
    if not screener_prewarm_enabled() or _SCHEDULER_THREAD is not None:
        return
    _SCHEDULER_STOP.clear()
    _SCHEDULER_THREAD = threading.Thread(
        target=_scheduler_loop,
        name="screener-prewarm",
        daemon=True,
    )
    _SCHEDULER_THREAD.start()


def stop_screener_prewarm_scheduler() -> None:
    global _SCHEDULER_THREAD
    if _SCHEDULER_THREAD is None:
        return
    _SCHEDULER_STOP.set()
    _SCHEDULER_THREAD.join(timeout=2)
    _SCHEDULER_THREAD = None
