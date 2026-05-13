from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from typing import Any

from diverge.worker.prewarm.config import (
    get_completed_ttl_seconds,
    get_workflow_ttl_seconds,
)


WORKFLOW_STATUSES = {"queued", "running", "retrying", "completed", "failed", "skipped"}
ACTIVE_WORKFLOW_STATUSES = {"queued", "running", "retrying"}
SKIP_WORKFLOW_STATUSES = ACTIVE_WORKFLOW_STATUSES | {"failed", "completed"}
ERROR_LIMIT = 500
RESULT_FIELDS = {
    "success",
    "market",
    "trading_day",
    "status",
    "ohlcv_synced",
    "screener_prewarmed",
    "manifest_as_of_date",
    "symbols_count",
    "screener_runs_total",
    "screener_runs_completed",
    "screener_runs_cached",
}


def completed_key(market: str, trading_day: str) -> str:
    return (
        f"prewarm:completed:{_normalize_market(market)}:{_normalize_day(trading_day)}"
    )


def workflow_key(market: str, trading_day: str) -> str:
    return f"prewarm:workflow:{_normalize_market(market)}:{_normalize_day(trading_day)}"


def lock_key(market: str, trading_day: str) -> str:
    return f"prewarm:lock:{_normalize_market(market)}:{_normalize_day(trading_day)}"


def _normalize_market(market: str) -> str:
    return str(market).strip().lower()


def _normalize_day(trading_day: str) -> str:
    return str(trading_day).strip()


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _redis_call(redis: Any, method_name: str, *args: Any, **kwargs: Any) -> Any:
    method = getattr(redis, method_name)
    return await _maybe_await(method(*args, **kwargs))


def _decode(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _compact_error(error: str | None) -> str | None:
    if error is None:
        return None
    return str(error).strip()[:ERROR_LIMIT] or None


def _compact_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not result:
        return None
    return {key: result[key] for key in RESULT_FIELDS if key in result}


def _workflow_payload(
    *,
    market: str,
    trading_day: str,
    job_id: str,
    status: str,
    attempt: int,
    existing: dict[str, Any] | None = None,
    reason: str | None = None,
    error: str | None = None,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in WORKFLOW_STATUSES:
        raise ValueError(f"Unsupported prewarm workflow status: {status}")
    now = _utc_iso()
    payload = dict(existing or {})
    payload.update(
        {
            "market": _normalize_market(market),
            "trading_day": _normalize_day(trading_day),
            "job_id": job_id,
            "status": status,
            "attempt": int(attempt),
            "updated_at": now,
        }
    )
    payload.setdefault("created_at", now)
    if reason is not None:
        payload["last_error"] = _compact_error(reason)
    if error is not None:
        payload["last_error"] = _compact_error(error)
    if result is not None:
        payload["result"] = _compact_result(result)
    if status == "completed":
        payload["last_error"] = None
    return payload


async def get_workflow(
    redis: Any,
    market: str,
    trading_day: str,
) -> dict[str, Any] | None:
    raw_value = await _redis_call(redis, "get", workflow_key(market, trading_day))
    decoded = _decode(raw_value)
    if decoded is None:
        return None
    try:
        value = json.loads(decoded)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


async def workflow_status(redis: Any, market: str, trading_day: str) -> str | None:
    workflow = await get_workflow(redis, market, trading_day)
    if not workflow:
        return None
    status = str(workflow.get("status") or "").strip().lower()
    return status or None


async def is_completed(redis: Any, market: str, trading_day: str) -> bool:
    value = await _redis_call(redis, "get", completed_key(market, trading_day))
    return value is not None


async def _write_workflow(
    redis: Any,
    market: str,
    trading_day: str,
    payload: dict[str, Any],
) -> None:
    await _redis_call(
        redis,
        "set",
        workflow_key(market, trading_day),
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        ex=get_workflow_ttl_seconds(),
    )


async def mark_queued(
    redis: Any,
    market: str,
    trading_day: str,
    job_id: str,
) -> None:
    existing = await get_workflow(redis, market, trading_day)
    payload = _workflow_payload(
        market=market,
        trading_day=trading_day,
        job_id=job_id,
        status="queued",
        attempt=int((existing or {}).get("attempt") or 1),
        existing=existing,
    )
    await _write_workflow(redis, market, trading_day, payload)


async def mark_running(
    redis: Any,
    market: str,
    trading_day: str,
    job_id: str,
    attempt: int,
) -> None:
    payload = _workflow_payload(
        market=market,
        trading_day=trading_day,
        job_id=job_id,
        status="running",
        attempt=attempt,
        existing=await get_workflow(redis, market, trading_day),
    )
    await _write_workflow(redis, market, trading_day, payload)


async def mark_retrying(
    redis: Any,
    market: str,
    trading_day: str,
    job_id: str,
    attempt: int,
    reason: str,
) -> None:
    payload = _workflow_payload(
        market=market,
        trading_day=trading_day,
        job_id=job_id,
        status="retrying",
        attempt=attempt,
        reason=reason,
        existing=await get_workflow(redis, market, trading_day),
    )
    await _write_workflow(redis, market, trading_day, payload)


async def mark_completed(
    redis: Any,
    market: str,
    trading_day: str,
    job_id: str,
    result: dict[str, Any],
) -> None:
    existing = await get_workflow(redis, market, trading_day)
    payload = _workflow_payload(
        market=market,
        trading_day=trading_day,
        job_id=job_id,
        status="completed",
        attempt=int((existing or {}).get("attempt") or 1),
        result=result,
        existing=existing,
    )
    await _write_workflow(redis, market, trading_day, payload)
    await _redis_call(
        redis,
        "set",
        completed_key(market, trading_day),
        "1",
        ex=get_completed_ttl_seconds(),
    )


async def mark_failed(
    redis: Any,
    market: str,
    trading_day: str,
    job_id: str,
    attempt: int,
    error: str,
) -> None:
    payload = _workflow_payload(
        market=market,
        trading_day=trading_day,
        job_id=job_id,
        status="failed",
        attempt=attempt,
        error=error,
        existing=await get_workflow(redis, market, trading_day),
    )
    await _write_workflow(redis, market, trading_day, payload)
