from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from diverge.worker.prewarm import backend_adapter


async def _run_blocking(function: Callable[..., Any], *args: Any) -> Any:
    return await asyncio.to_thread(function, *args)


def run_screener_prewarm_sync(market: str, trading_day: str) -> dict[str, Any]:
    completed = 0
    cached = 0
    skipped_duplicates = 0
    runs: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for request_payload in backend_adapter.collect_screener_prewarm_payloads(
        market,
        trading_day,
    ):
        config_payload = backend_adapter.build_screener_config_payload(request_payload)
        screener_key = backend_adapter.screener_key_for_config(config_payload)
        if screener_key in seen_keys:
            skipped_duplicates += 1
            continue
        seen_keys.add(screener_key)

        result = backend_adapter.run_screener_payload(
            market,
            trading_day,
            request_payload,
            config_payload,
        )
        runs.append(result)
        if result["status"] == "cached":
            cached += 1
        elif result["status"] == "completed":
            completed += 1

    return {
        "status": "completed" if runs else "skipped",
        "runs_total": len(runs),
        "runs_completed": completed,
        "runs_cached": cached,
        "duplicates_skipped": skipped_duplicates,
        "runs": runs,
    }


def build_workflow_success_result(
    market: str,
    trading_day: str,
    raw_result: dict[str, Any],
) -> dict[str, Any]:
    ohlcv_result = raw_result.get("ohlcv_sync") or {}
    try:
        symbols_count = int(ohlcv_result.get("symbols_success") or 0)
    except (TypeError, ValueError):
        symbols_count = 0

    ohlcv_synced = (
        str(ohlcv_result.get("status") or "").strip().lower() == "completed"
        and symbols_count > 0
    )
    screener_result = raw_result.get("screener_prewarm") or {}
    try:
        screener_runs_total = int(screener_result.get("runs_total") or 0)
    except (TypeError, ValueError):
        screener_runs_total = 0
    try:
        screener_runs_completed = int(screener_result.get("runs_completed") or 0)
    except (TypeError, ValueError):
        screener_runs_completed = 0
    try:
        screener_runs_cached = int(screener_result.get("runs_cached") or 0)
    except (TypeError, ValueError):
        screener_runs_cached = 0
    screener_prewarmed = (
        str(screener_result.get("status") or "").strip().lower() == "completed"
        and screener_runs_total > 0
        and screener_runs_total == screener_runs_completed + screener_runs_cached
    )
    success = bool(ohlcv_synced and screener_prewarmed)

    return {
        "success": success,
        "status": "completed" if success else "not_confirmed",
        "market": str(market).strip().lower(),
        "trading_day": str(trading_day).strip(),
        "ohlcv_synced": ohlcv_synced,
        "screener_prewarmed": screener_prewarmed,
        "manifest_as_of_date": str(raw_result.get("as_of_date") or trading_day),
        "symbols_count": symbols_count,
        "screener_runs_total": screener_runs_total,
        "screener_runs_completed": screener_runs_completed,
        "screener_runs_cached": screener_runs_cached,
    }


def run_market_prewarm_workflow_sync(market: str, trading_day: str) -> dict[str, Any]:
    sync_payload = backend_adapter.build_ohlcv_sync_payload(market, trading_day)
    sync_result = backend_adapter.run_ohlcv_sync_payload(sync_payload)
    fundamentals_result = backend_adapter.run_fundamental_prewarm_sync(
        market,
        trading_day,
        ohlcv_payload=sync_payload,
    )
    screener_result = run_screener_prewarm_sync(market, trading_day)
    raw_result = {
        "as_of_date": trading_day,
        "market": market,
        "ohlcv_sync": sync_result,
        "fundamentals_sync": {str(market).strip().lower(): fundamentals_result},
        "screener_prewarm": screener_result,
    }
    return build_workflow_success_result(market, trading_day, raw_result)


async def run_market_prewarm_workflow(
    market: str,
    trading_day: str,
) -> dict[str, Any]:
    return await _run_blocking(
        run_market_prewarm_workflow_sync,
        market,
        trading_day,
    )
