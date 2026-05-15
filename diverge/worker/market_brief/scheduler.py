from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from typing import Any

from diverge.common.market_calendar import is_market_trading_day
from diverge.worker.market_brief.config import (
    MarketBriefScheduleConfig,
    get_market_brief_schedule_config,
    get_market_brief_workflow_ttl_seconds,
    market_brief_job_id,
)


ACTIVE_STATUSES = {"queued", "running", "completed", "failed"}


def _coerce_utc(now_utc: datetime | None) -> datetime:
    if now_utc is None:
        return datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        return now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(timezone.utc)


def _slot_for_now(config: MarketBriefScheduleConfig, now_utc: datetime) -> str | None:
    local_now = now_utc.astimezone(config.timezone)
    for slot in config.times:
        if local_now.hour == slot.hour and local_now.minute == slot.minute:
            return slot.strftime("%H:%M")
    return None


def _has_due_market(config: MarketBriefScheduleConfig, now_utc: datetime) -> bool:
    local_day = now_utc.astimezone(config.timezone).date()
    return any(is_market_trading_day(market, local_day) for market in config.markets)


def _workflow_key(job_id: str) -> str:
    return f"market_brief:workflow:{job_id}"


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


async def _workflow_status(redis: Any, job_id: str) -> str | None:
    decoded = _decode(await _redis_call(redis, "get", _workflow_key(job_id)))
    if decoded is None:
        return None
    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError:
        return None
    status = str((payload if isinstance(payload, dict) else {}).get("status") or "")
    return status.strip().lower() or None


async def _mark_queued(redis: Any, job_id: str, payload: dict[str, Any]) -> None:
    await _redis_call(
        redis,
        "set",
        _workflow_key(job_id),
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        ex=get_market_brief_workflow_ttl_seconds(),
    )


async def market_brief_due_tick(
    ctx: dict[str, Any],
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    config = get_market_brief_schedule_config()
    current_utc = _coerce_utc(now_utc)
    if not config.enabled:
        return {"enqueued": [], "skipped": [{"reason": "disabled"}]}

    slot = _slot_for_now(config, current_utc)
    if slot is None:
        return {"enqueued": [], "skipped": [{"reason": "not_due"}]}

    if not _has_due_market(config, current_utc):
        return {"enqueued": [], "skipped": [{"reason": "not_trading_day"}]}

    local_day = current_utc.astimezone(config.timezone).date().isoformat()
    job_id = market_brief_job_id(
        brief_date=local_day,
        slot=slot,
        markets=tuple(config.markets),
    )
    redis = ctx["redis"]
    status = await _workflow_status(redis, job_id)
    if status in ACTIVE_STATUSES:
        return {
            "enqueued": [],
            "skipped": [{"job_id": job_id, "reason": "already_queued_or_done"}],
        }

    from web.backend.runtime import market_brief_tasks, task_store

    if not task_store.redis_task_backend_enabled():
        return {"enqueued": [], "skipped": [{"reason": "task_backend_not_redis"}]}

    owner_user_id, tenant_id = market_brief_tasks.resolve_automation_owner()
    task = market_brief_tasks.create_market_brief_task(
        task_id=job_id,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        request_payload={
            "markets": list(config.markets),
            "output_language": config.output_language,
            "report_visibility": config.report_visibility,
            "trigger": "scheduled",
            "slot": slot,
            "automation_key": job_id,
            "scheduler_provider": config.scheduler_provider,
        },
    )
    workflow_payload = {
        "job_id": job_id,
        "task_id": task["task_id"],
        "status": task["status"],
        "slot": slot,
        "brief_date": local_day,
        "markets": list(config.markets),
        "updated_at": current_utc.isoformat(),
    }
    await _mark_queued(redis, job_id, workflow_payload)
    return {"enqueued": [workflow_payload], "skipped": []}
