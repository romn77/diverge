from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import time
from zoneinfo import ZoneInfo


DEFAULT_COMPLETED_TTL_SECONDS = 90 * 24 * 60 * 60
DEFAULT_WORKFLOW_TTL_SECONDS = 90 * 24 * 60 * 60
DEFAULT_RETRY_DEFER_SECONDS = 300
DEFAULT_MAX_TRIES = 5
DEFAULT_PREWARM_QUEUE_NAME = "arq:prewarm"
DEFAULT_PREWARM_SCHEDULER_QUEUE_NAME = "arq:prewarm:scheduler"


@dataclass(frozen=True)
class PrewarmMarketConfig:
    market: str
    vendor: str
    timezone: ZoneInfo
    ready_cutoff: time
    window_end: time
    retry_defer_seconds: int = DEFAULT_RETRY_DEFER_SECONDS
    max_tries: int = DEFAULT_MAX_TRIES

    @property
    def window_start(self) -> time:
        return self.ready_cutoff


PREWARM_MARKETS: dict[str, PrewarmMarketConfig] = {
    "cn": PrewarmMarketConfig(
        market="cn",
        vendor="tushare",
        timezone=ZoneInfo("Asia/Shanghai"),
        ready_cutoff=time(18, 10),
        window_end=time(21, 30),
    ),
    "us": PrewarmMarketConfig(
        market="us",
        vendor="massive",
        timezone=ZoneInfo("America/New_York"),
        ready_cutoff=time(21, 10),
        window_end=time(23, 30),
    ),
}


def _parse_time_env(name: str, default: time) -> time:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        hour_text, minute_text = raw_value.strip().split(":", 1)
        return time(hour=int(hour_text), minute=int(minute_text))
    except Exception as exc:
        raise RuntimeError(f"{name} must use HH:MM format") from exc


def _positive_int_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value.strip())
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero")
    return value


def get_prewarm_retry_defer_seconds(market: str | None = None) -> int:
    if market:
        market_name = str(market).strip().upper()
        specific = os.environ.get(f"PREWARM_{market_name}_RETRY_DEFER_SECONDS")
        if specific is not None:
            return _positive_int_env(
                f"PREWARM_{market_name}_RETRY_DEFER_SECONDS",
                DEFAULT_RETRY_DEFER_SECONDS,
            )
    return _positive_int_env(
        "PREWARM_RETRY_DEFER_SECONDS",
        DEFAULT_RETRY_DEFER_SECONDS,
    )


def get_prewarm_max_tries(market: str | None = None) -> int:
    if market:
        market_name = str(market).strip().upper()
        specific = os.environ.get(f"PREWARM_{market_name}_MAX_TRIES")
        if specific is not None:
            return _positive_int_env(
                f"PREWARM_{market_name}_MAX_TRIES",
                DEFAULT_MAX_TRIES,
            )
    return _positive_int_env("PREWARM_MAX_TRIES", DEFAULT_MAX_TRIES)


def get_completed_ttl_seconds() -> int:
    return _positive_int_env(
        "PREWARM_COMPLETED_TTL_SECONDS",
        DEFAULT_COMPLETED_TTL_SECONDS,
    )


def get_workflow_ttl_seconds() -> int:
    return _positive_int_env(
        "PREWARM_WORKFLOW_TTL_SECONDS",
        DEFAULT_WORKFLOW_TTL_SECONDS,
    )


def get_prewarm_queue_name() -> str:
    return os.environ.get("PREWARM_QUEUE_NAME", DEFAULT_PREWARM_QUEUE_NAME).strip() or (
        DEFAULT_PREWARM_QUEUE_NAME
    )


def get_prewarm_scheduler_queue_name() -> str:
    return (
        os.environ.get(
            "PREWARM_SCHEDULER_QUEUE_NAME",
            DEFAULT_PREWARM_SCHEDULER_QUEUE_NAME,
        ).strip()
        or DEFAULT_PREWARM_SCHEDULER_QUEUE_NAME
    )


def get_redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://redis:6379/0")


def get_prewarm_market_config(market: str) -> PrewarmMarketConfig:
    normalized_market = str(market).strip().lower()
    default = PREWARM_MARKETS.get(normalized_market)
    if default is None:
        raise ValueError(f"Unsupported prewarm market: {market}")
    env_prefix = f"PREWARM_{normalized_market.upper()}"
    return replace(
        default,
        ready_cutoff=_parse_time_env(
            f"{env_prefix}_READY_TIME",
            default.ready_cutoff,
        ),
        window_end=_parse_time_env(
            f"{env_prefix}_WINDOW_END",
            default.window_end,
        ),
        retry_defer_seconds=get_prewarm_retry_defer_seconds(normalized_market),
        max_tries=get_prewarm_max_tries(normalized_market),
    )


def iter_prewarm_market_configs() -> list[PrewarmMarketConfig]:
    return [get_prewarm_market_config(market) for market in PREWARM_MARKETS]


def prewarm_job_id(market: str, trading_day: str) -> str:
    version = os.environ.get("PREWARM_JOB_VERSION", "v1").strip() or "v1"
    return f"prewarm:{str(market).strip().lower()}:{str(trading_day).strip()}:{version}"
