from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from diverge.dataflows import vendor_usage
from diverge.screener.pipeline import run_screen
from diverge.screener.schema import ScreenRunConfig


def _snapshot_summary(snapshot: Any) -> dict[str, Any]:
    return {
        "run_id": getattr(snapshot, "source_run_id", None),
        "as_of_date": getattr(snapshot, "as_of_date", None),
        "markets": list(getattr(snapshot, "markets", []) or []),
        "candidate_count": int(getattr(snapshot, "candidate_count", 0) or 0),
        "match_count": int(getattr(snapshot, "match_count", 0) or 0),
        "generated_at": getattr(snapshot, "generated_at", None),
    }


def _confirmed_cached_snapshot(
    config_payload: dict[str, Any],
    market: str,
    trading_day: str,
) -> Any | None:
    from web.backend import screener_results

    snapshot = screener_results.get_cached_screener_result(config_payload)
    if snapshot is None:
        return None
    markets = {
        str(candidate).strip().lower()
        for candidate in getattr(snapshot, "markets", []) or []
    }
    if str(market).strip().lower() not in markets:
        return None
    snapshot_day = str(getattr(snapshot, "as_of_date", "") or "").strip()
    if snapshot_day != str(trading_day).strip():
        return None
    if not getattr(snapshot, "generated_at", None):
        return None
    return snapshot


def _run_screener_payload_sync(
    market: str,
    trading_day: str,
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    from web.backend.runtime import screener_prewarm
    from web.backend.services import screeners as screener_service

    config_payload = screener_prewarm.build_screener_config_payload(request_payload)
    cached_snapshot = _confirmed_cached_snapshot(config_payload, market, trading_day)
    if cached_snapshot is not None:
        return {"status": "cached", **_snapshot_summary(cached_snapshot)}

    config = ScreenRunConfig(**config_payload)
    screener_service.ensure_screener_cache_coverage(config)
    with vendor_usage.data_source_usage_context("screener"):
        result = run_screen(config)

    task = SimpleNamespace(
        id=f"prewarm-{market}-{trading_day}-{uuid.uuid4().hex}",
        request_payload=dict(request_payload),
        config_payload=config_payload,
        owner_user_id=None,
        tenant_id=None,
        run_id=Path(result.run_dir).name,
    )
    candidate = screener_service.run_screener(task, result)
    screener_service.persist_screener_run(task, candidate)

    snapshot = _confirmed_cached_snapshot(config_payload, market, trading_day)
    if snapshot is None:
        raise RuntimeError(
            f"Screener prewarm did not produce a confirmed cache for "
            f"{market}:{trading_day}."
        )
    return {"status": "completed", **_snapshot_summary(snapshot)}


def run_screener_prewarm_sync(market: str, trading_day: str) -> dict[str, Any]:
    from web.backend import screener_results
    from web.backend.runtime import screener_prewarm

    completed = 0
    cached = 0
    skipped_duplicates = 0
    runs: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for request_payload in screener_prewarm.collect_screener_prewarm_payloads(
        market,
        trading_day,
    ):
        config_payload = screener_prewarm.build_screener_config_payload(request_payload)
        screener_key = screener_results.screener_key_for_config(config_payload)
        if screener_key in seen_keys:
            skipped_duplicates += 1
            continue
        seen_keys.add(screener_key)

        result = _run_screener_payload_sync(market, trading_day, request_payload)
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
    from web.backend.runtime import data_sync_tasks, screener_prewarm

    sync_payload = screener_prewarm.build_ohlcv_sync_payload(market, trading_day)
    sync_result = data_sync_tasks.run_ohlcv_sync_payload(sync_payload)
    fundamentals_result = screener_prewarm.run_fundamental_prewarm_sync(
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
    return await asyncio.to_thread(
        run_market_prewarm_workflow_sync,
        market,
        trading_day,
    )
