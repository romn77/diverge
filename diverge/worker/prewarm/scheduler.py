from __future__ import annotations

from datetime import datetime
from typing import Any

from diverge.worker.prewarm.config import (
    get_prewarm_queue_name,
    iter_prewarm_market_configs,
    prewarm_job_id,
)
from diverge.worker.prewarm.readiness import resolve_due_prewarm_trading_day
from diverge.worker.prewarm.state import (
    SKIP_WORKFLOW_STATUSES,
    is_completed,
    mark_queued,
    workflow_status,
)


async def _maybe_await(value: Any) -> Any:
    import inspect

    if inspect.isawaitable(value):
        return await value
    return value


async def prewarm_due_tick(
    ctx: dict[str, Any],
    *,
    now_utc: datetime | None = None,
    markets: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    redis = ctx["redis"]
    configured_markets = (
        markets
        if markets is not None
        else [config.market for config in iter_prewarm_market_configs()]
    )
    enqueued: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for market in configured_markets:
        normalized_market = str(market).strip().lower()
        trading_day = resolve_due_prewarm_trading_day(normalized_market, now_utc)
        if trading_day is None:
            skipped.append({"market": normalized_market, "reason": "not_due"})
            continue

        if await is_completed(redis, normalized_market, trading_day):
            skipped.append(
                {
                    "market": normalized_market,
                    "trading_day": trading_day,
                    "reason": "completed",
                }
            )
            continue

        status = await workflow_status(redis, normalized_market, trading_day)
        if status in SKIP_WORKFLOW_STATUSES:
            skipped.append(
                {
                    "market": normalized_market,
                    "trading_day": trading_day,
                    "reason": "already_queued_or_running"
                    if status in {"queued", "running", "retrying"}
                    else status,
                }
            )
            continue

        job_id = prewarm_job_id(normalized_market, trading_day)
        job = await _maybe_await(
            redis.enqueue_job(
                "run_market_prewarm",
                normalized_market,
                trading_day,
                _queue_name=get_prewarm_queue_name(),
                _job_id=job_id,
            )
        )
        if job is None:
            skipped.append(
                {
                    "market": normalized_market,
                    "trading_day": trading_day,
                    "reason": "already_queued_or_running",
                }
            )
            continue

        await mark_queued(redis, normalized_market, trading_day, job_id)
        enqueued.append(
            {
                "market": normalized_market,
                "trading_day": trading_day,
                "job_id": job_id,
            }
        )

    return {"enqueued": enqueued, "skipped": skipped}
