from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from typing import Any

from diverge.common.market_calendar import is_market_trading_day
from diverge.worker.market_brief.config import (
    MarketBriefMarketSchedule,
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


def _slot_for_now(schedule: MarketBriefMarketSchedule, now_utc: datetime) -> str | None:
    local_now = now_utc.astimezone(schedule.timezone)
    for slot in schedule.times:
        if local_now.hour == slot.hour and local_now.minute == slot.minute:
            return slot.strftime("%H:%M")
    return None


def _timezone_key(schedule: MarketBriefMarketSchedule) -> str:
    return getattr(schedule.timezone, "key", str(schedule.timezone))


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

    due_schedules = [
        (schedule, slot)
        for schedule in config.schedules
        if (slot := _slot_for_now(schedule, current_utc)) is not None
    ]
    if not due_schedules:
        return {"enqueued": [], "skipped": [{"reason": "not_due"}]}

    redis = ctx["redis"]
    from web.backend.runtime import market_brief_tasks, task_store

    if not task_store.redis_task_backend_enabled():
        return {"enqueued": [], "skipped": [{"reason": "task_backend_not_redis"}]}

    enqueued: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    owner_user_id, tenant_id = market_brief_tasks.resolve_automation_owner()
    for schedule, slot in due_schedules:
        local_day = current_utc.astimezone(schedule.timezone).date()
        if not is_market_trading_day(schedule.market, local_day):
            skipped.append(
                {
                    "market": schedule.market,
                    "slot": slot,
                    "reason": "not_trading_day",
                }
            )
            continue

        local_day_text = local_day.isoformat()
        job_id = market_brief_job_id(
            brief_date=local_day_text,
            slot=slot,
            markets=(schedule.market,),
        )
        status = await _workflow_status(redis, job_id)
        if status in ACTIVE_STATUSES:
            skipped.append(
                {
                    "job_id": job_id,
                    "market": schedule.market,
                    "reason": "already_queued_or_done",
                }
            )
            continue

        timezone_name = _timezone_key(schedule)
        task = market_brief_tasks.create_market_brief_task(
            task_id=job_id,
            owner_user_id=owner_user_id,
            tenant_id=tenant_id,
            request_payload={
                "markets": [schedule.market],
                "output_language": config.output_language,
                "output_timezone": timezone_name,
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
            "brief_date": local_day_text,
            "markets": [schedule.market],
            "timezone": timezone_name,
            "updated_at": current_utc.isoformat(),
        }
        await _mark_queued(redis, job_id, workflow_payload)
        enqueued.append(workflow_payload)
    return {"enqueued": enqueued, "skipped": skipped}
