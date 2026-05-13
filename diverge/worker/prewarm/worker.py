from __future__ import annotations

from typing import Any

from arq.worker import Retry

from diverge.worker.prewarm.config import get_prewarm_market_config, prewarm_job_id
from diverge.worker.prewarm.readiness import check_vendor_ready
from diverge.worker.prewarm.state import (
    is_completed,
    mark_completed,
    mark_failed,
    mark_retrying,
    mark_running,
)
from diverge.worker.prewarm.workflow import run_market_prewarm_workflow


async def _retry_or_fail(
    *,
    redis: Any,
    market: str,
    trading_day: str,
    job_id: str,
    attempt: int,
    max_tries: int,
    defer_seconds: int,
    reason: str,
) -> None:
    if attempt >= max_tries:
        await mark_failed(
            redis,
            market=market,
            trading_day=trading_day,
            job_id=job_id,
            attempt=attempt,
            error=reason,
        )
        raise RuntimeError(reason)

    await mark_retrying(
        redis,
        market=market,
        trading_day=trading_day,
        job_id=job_id,
        attempt=attempt,
        reason=reason,
    )
    raise Retry(defer=defer_seconds)


async def run_market_prewarm(
    ctx: dict[str, Any],
    market: str,
    trading_day: str,
) -> dict[str, Any]:
    redis = ctx["redis"]
    job_id = str(ctx.get("job_id") or prewarm_job_id(market, trading_day))
    attempt = int(ctx.get("job_try") or 1)
    config = get_prewarm_market_config(market)

    if await is_completed(redis, market, trading_day):
        return {
            "status": "already_completed",
            "market": str(market).strip().lower(),
            "trading_day": str(trading_day).strip(),
        }

    await mark_running(
        redis,
        market=market,
        trading_day=trading_day,
        job_id=job_id,
        attempt=attempt,
    )

    try:
        ready = await check_vendor_ready(market, trading_day)
        if not ready:
            await _retry_or_fail(
                redis=redis,
                market=market,
                trading_day=trading_day,
                job_id=job_id,
                attempt=attempt,
                max_tries=config.max_tries,
                defer_seconds=config.retry_defer_seconds,
                reason="vendor_not_ready",
            )

        result = await run_market_prewarm_workflow(
            market=market,
            trading_day=trading_day,
        )
        if not result.get("success"):
            await _retry_or_fail(
                redis=redis,
                market=market,
                trading_day=trading_day,
                job_id=job_id,
                attempt=attempt,
                max_tries=config.max_tries,
                defer_seconds=config.retry_defer_seconds,
                reason="success_state_not_confirmed",
            )
    except Retry:
        raise
    except Exception as exc:
        if attempt >= config.max_tries:
            await mark_failed(
                redis,
                market=market,
                trading_day=trading_day,
                job_id=job_id,
                attempt=attempt,
                error=str(exc),
            )
            raise
        await mark_retrying(
            redis,
            market=market,
            trading_day=trading_day,
            job_id=job_id,
            attempt=attempt,
            reason=str(exc),
        )
        raise Retry(defer=config.retry_defer_seconds) from exc

    await mark_completed(
        redis,
        market=market,
        trading_day=trading_day,
        job_id=job_id,
        result=result,
    )
    return {
        "status": "completed",
        "market": str(market).strip().lower(),
        "trading_day": str(trading_day).strip(),
        "result": result,
    }
