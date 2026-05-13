from __future__ import annotations

from datetime import timezone
from urllib.parse import unquote, urlparse

from arq import cron
from arq.connections import RedisSettings
from arq.worker import func

from diverge.worker.prewarm.config import (
    get_prewarm_max_tries,
    get_prewarm_queue_name,
    get_prewarm_scheduler_queue_name,
    get_redis_url,
)
from diverge.worker.prewarm.scheduler import prewarm_due_tick
from diverge.worker.prewarm.worker import run_market_prewarm


EVERY_5_MINUTES = set(range(0, 60, 5))


def redis_settings_from_dsn(dsn: str) -> RedisSettings:
    parsed = urlparse(dsn)
    if parsed.scheme not in {"redis", "rediss"}:
        raise RuntimeError("REDIS_URL must use redis:// or rediss://")
    database = int((parsed.path or "/0").lstrip("/") or "0")
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=database,
        username=unquote(parsed.username) if parsed.username else None,
        password=unquote(parsed.password) if parsed.password else None,
        ssl=parsed.scheme == "rediss",
    )


class PrewarmSchedulerSettings:
    redis_settings = redis_settings_from_dsn(get_redis_url())
    queue_name = get_prewarm_scheduler_queue_name()
    max_jobs = 1
    timezone = timezone.utc
    functions = []
    cron_jobs = [
        cron(
            prewarm_due_tick,
            minute=EVERY_5_MINUTES,
            second=0,
            unique=True,
            run_at_startup=False,
            max_tries=1,
            timeout=60,
            keep_result=300,
        )
    ]


class PrewarmWorkerSettings:
    redis_settings = redis_settings_from_dsn(get_redis_url())
    queue_name = get_prewarm_queue_name()
    max_jobs = 1
    job_timeout = 60 * 60 * 3
    keep_result = 300
    job_completion_wait = 300
    functions = [
        func(
            run_market_prewarm,
            name="run_market_prewarm",
            max_tries=get_prewarm_max_tries(),
            timeout=60 * 60 * 3,
            keep_result=300,
        )
    ]
