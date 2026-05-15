from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo

from diverge.market_brief.builder import normalize_markets
from diverge.market_brief.schema import MarketBriefMarket


DEFAULT_MARKET_BRIEF_TIMES = (time(8, 30), time(9, 0), time(9, 20))
DEFAULT_MARKET_BRIEF_MARKETS: tuple[MarketBriefMarket, ...] = ("cn", "hk", "us")
DEFAULT_SCHEDULER_QUEUE_NAME = "arq:market-brief:scheduler"
DEFAULT_WORKFLOW_TTL_SECONDS = 14 * 24 * 60 * 60


@dataclass(frozen=True)
class MarketBriefScheduleConfig:
    enabled: bool
    timezone: ZoneInfo
    times: tuple[time, ...]
    markets: tuple[MarketBriefMarket, ...]
    output_language: str
    report_visibility: str
    scheduler_provider: str


def _bool_env(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


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


def _parse_time(value: str) -> time:
    try:
        hour_text, minute_text = value.strip().split(":", 1)
        return time(hour=int(hour_text), minute=int(minute_text))
    except Exception as exc:
        raise RuntimeError("MARKET_BRIEF_TIMES must use HH:MM values") from exc


def _parse_times_env() -> tuple[time, ...]:
    raw_value = os.environ.get("MARKET_BRIEF_TIMES")
    if raw_value is None:
        return DEFAULT_MARKET_BRIEF_TIMES
    values = tuple(_parse_time(part) for part in raw_value.split(",") if part.strip())
    if not values:
        raise RuntimeError("MARKET_BRIEF_TIMES must include at least one time")
    return values


def _parse_markets_env() -> tuple[MarketBriefMarket, ...]:
    raw_value = os.environ.get("MARKET_BRIEF_MARKETS")
    if raw_value is None:
        return DEFAULT_MARKET_BRIEF_MARKETS
    return tuple(normalize_markets(raw_value.split(",")))


def get_market_brief_schedule_config() -> MarketBriefScheduleConfig:
    timezone_name = os.environ.get("MARKET_BRIEF_TIMEZONE", "Asia/Shanghai").strip()
    return MarketBriefScheduleConfig(
        enabled=_bool_env("MARKET_BRIEF_ENABLED", False),
        timezone=ZoneInfo(timezone_name or "Asia/Shanghai"),
        times=_parse_times_env(),
        markets=_parse_markets_env(),
        output_language=os.environ.get("MARKET_BRIEF_OUTPUT_LANGUAGE", "zh-CN").strip()
        or "zh-CN",
        report_visibility=(
            os.environ.get("MARKET_BRIEF_REPORT_VISIBILITY", "workspace").strip()
            or "workspace"
        ),
        scheduler_provider=os.environ.get(
            "MARKET_BRIEF_SCHEDULER_PROVIDER",
            "arq",
        ).strip()
        or "arq",
    )


def get_market_brief_scheduler_queue_name() -> str:
    return (
        os.environ.get(
            "MARKET_BRIEF_SCHEDULER_QUEUE_NAME", DEFAULT_SCHEDULER_QUEUE_NAME
        ).strip()
        or DEFAULT_SCHEDULER_QUEUE_NAME
    )


def get_market_brief_workflow_ttl_seconds() -> int:
    return _positive_int_env(
        "MARKET_BRIEF_WORKFLOW_TTL_SECONDS",
        DEFAULT_WORKFLOW_TTL_SECONDS,
    )


def get_redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://redis:6379/0")


def market_brief_job_id(*, brief_date: str, slot: str, markets: tuple[str, ...]) -> str:
    version = os.environ.get("MARKET_BRIEF_JOB_VERSION", "v1").strip() or "v1"
    market_key = "-".join(str(market).strip().lower() for market in markets)
    slot_key = slot.replace(":", "")
    return f"market_brief:{brief_date}:{slot_key}:{market_key}:{version}"
