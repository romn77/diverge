from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from diverge.dataflows import vendor_usage
from diverge.screener.pipeline import run_screen
from diverge.screener.schema import ScreenRunConfig


class VendorNotReady(RuntimeError):
    """Raised when the backend OHLCV readiness probe is not ready yet."""


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


def build_ohlcv_sync_payload(market: str, trading_day: str) -> dict[str, Any]:
    from web.backend.runtime import screener_prewarm

    return screener_prewarm.build_ohlcv_sync_payload(market, trading_day)


def ensure_ohlcv_vendor_ready(market: str, trading_day: str) -> None:
    from web.backend.runtime import data_sync_tasks

    try:
        data_sync_tasks.ensure_ohlcv_vendor_ready(
            build_ohlcv_sync_payload(market, trading_day)
        )
    except data_sync_tasks.VendorDataNotReadyError as exc:
        raise VendorNotReady(str(exc)) from exc


def run_ohlcv_sync_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from web.backend.runtime import data_sync_tasks

    return data_sync_tasks.run_ohlcv_sync_payload(payload)


def run_fundamental_prewarm_sync(
    market: str,
    trading_day: str,
    *,
    ohlcv_payload: dict[str, Any],
) -> dict[str, Any]:
    from web.backend.runtime import screener_prewarm

    return screener_prewarm.run_fundamental_prewarm_sync(
        market,
        trading_day,
        ohlcv_payload=ohlcv_payload,
    )


def collect_screener_prewarm_payloads(
    market: str,
    trading_day: str,
) -> list[dict[str, Any]]:
    from web.backend.runtime import screener_prewarm

    return screener_prewarm.collect_screener_prewarm_payloads(market, trading_day)


def build_screener_config_payload(request_payload: dict[str, Any]) -> dict[str, Any]:
    from web.backend.runtime import screener_prewarm

    return screener_prewarm.build_screener_config_payload(request_payload)


def screener_key_for_config(config_payload: dict[str, Any]) -> str:
    from web.backend import screener_results

    return screener_results.screener_key_for_config(config_payload)


def run_screener_payload(
    market: str,
    trading_day: str,
    request_payload: dict[str, Any],
    config_payload: dict[str, Any],
) -> dict[str, Any]:
    from web.backend.services import screeners as screener_service

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
