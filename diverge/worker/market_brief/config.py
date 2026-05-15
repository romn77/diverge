from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo

from diverge.market_brief.builder import normalize_markets
from diverge.market_brief.schema import MarketBriefMarket


DEFAULT_MARKET_BRIEF_TIMES = (time(8, 30), time(9, 0), time(9, 20))
DEFAULT_MARKET_BRIEF_MARKETS: tuple[MarketBriefMarket, ...] = ("cn", "us")
DEFAULT_MARKET_TIMEZONES: dict[MarketBriefMarket, str] = {
    "cn": "Asia/Shanghai",
    "us": "America/New_York",
}
DISABLED_MARKET_ALIASES = {"h", "hongkong", "hong_kong", "hk"}
DEFAULT_SCHEDULER_QUEUE_NAME = "arq:market-brief:scheduler"
DEFAULT_WORKFLOW_TTL_SECONDS = 14 * 24 * 60 * 60


@dataclass(frozen=True)
class MarketBriefMarketSchedule:
    market: MarketBriefMarket
    timezone: ZoneInfo
    times: tuple[time, ...]


@dataclass(frozen=True)
class MarketBriefScheduleConfig:
    enabled: bool
    markets: tuple[MarketBriefMarket, ...]
    schedules: tuple[MarketBriefMarketSchedule, ...]
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
        raise RuntimeError("Market brief time values must use HH:MM") from exc


def _parse_times_value(name: str, raw_value: str) -> tuple[time, ...]:
    values = tuple(_parse_time(part) for part in raw_value.split(",") if part.strip())
    if not values:
        raise RuntimeError(f"{name} must include at least one time")
    return values


def _parse_times_env(name: str, default: tuple[time, ...]) -> tuple[time, ...]:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return _parse_times_value(name, raw_value)


def _parse_markets_env() -> tuple[MarketBriefMarket, ...]:
    raw_value = os.environ.get("MARKET_BRIEF_MARKETS")
    if raw_value is None:
        return DEFAULT_MARKET_BRIEF_MARKETS
    requested_markets = [
        value.strip()
        for value in raw_value.split(",")
        if value.strip() and value.strip().lower() not in DISABLED_MARKET_ALIASES
    ]
    if not requested_markets:
        raise RuntimeError("MARKET_BRIEF_MARKETS must include at least cn or us")
    return tuple(normalize_markets(requested_markets))


def _market_env_name(market: MarketBriefMarket, suffix: str) -> str:
    return f"MARKET_BRIEF_{market.upper()}_{suffix}"


def _market_timezone(market: MarketBriefMarket) -> ZoneInfo:
    env_name = _market_env_name(market, "TIMEZONE")
    timezone_name = (
        os.environ.get(env_name) or DEFAULT_MARKET_TIMEZONES[market]
    ).strip()
    try:
        return ZoneInfo(timezone_name or DEFAULT_MARKET_TIMEZONES[market])
    except Exception as exc:
        raise RuntimeError(f"{env_name} must be a valid IANA timezone") from exc


def _market_times(market: MarketBriefMarket) -> tuple[time, ...]:
    env_name = _market_env_name(market, "TIMES")
    raw_value = os.environ.get(env_name)
    if raw_value is not None:
        return _parse_times_value(env_name, raw_value)
    return _parse_times_env("MARKET_BRIEF_TIMES", DEFAULT_MARKET_BRIEF_TIMES)


def _market_schedules(
    markets: tuple[MarketBriefMarket, ...],
) -> tuple[MarketBriefMarketSchedule, ...]:
    return tuple(
        MarketBriefMarketSchedule(
            market=market,
            timezone=_market_timezone(market),
            times=_market_times(market),
        )
        for market in markets
    )


def get_market_brief_schedule_config() -> MarketBriefScheduleConfig:
    markets = _parse_markets_env()
    return MarketBriefScheduleConfig(
        enabled=_bool_env("MARKET_BRIEF_ENABLED", False),
        markets=markets,
        schedules=_market_schedules(markets),
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
