from __future__ import annotations

from datetime import timezone
from urllib.parse import unquote, urlparse

from arq import cron
from arq.connections import RedisSettings

from diverge.worker.market_brief.config import (
    get_market_brief_scheduler_queue_name,
    get_redis_url,
)
from diverge.worker.market_brief.scheduler import market_brief_due_tick
from web.backend.monitoring import initialize_sentry


initialize_sentry(default_service_name="market-brief-scheduler")


EVERY_MINUTE = set(range(0, 60))


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


class MarketBriefSchedulerSettings:
    redis_settings = redis_settings_from_dsn(get_redis_url())
    queue_name = get_market_brief_scheduler_queue_name()
    max_jobs = 1
    timezone = timezone.utc
    functions = []
    cron_jobs = [
        cron(
            market_brief_due_tick,
            minute=EVERY_MINUTE,
            second=0,
            unique=True,
            run_at_startup=False,
            max_tries=1,
            timeout=60,
            keep_result=300,
        )
    ]
