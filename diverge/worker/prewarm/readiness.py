from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, time, timezone

from diverge.common.market_calendar import latest_trading_day_on_or_before
from diverge.worker.prewarm.config import get_prewarm_market_config


@dataclass(frozen=True)
class PrewarmWindowDecision:
    market: str
    in_window: bool
    reason: str
    now_local: datetime
    window_start: time
    window_end: time


def _coerce_utc(now_utc: datetime | None) -> datetime:
    if now_utc is None:
        return datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        return now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(timezone.utc)


def _time_in_window(current: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def prewarm_window_status(
    market: str,
    now_utc: datetime | None = None,
) -> PrewarmWindowDecision:
    config = get_prewarm_market_config(market)
    local_now = _coerce_utc(now_utc).astimezone(config.timezone)
    local_time = local_now.timetz().replace(tzinfo=None)
    if _time_in_window(local_time, config.window_start, config.window_end):
        reason = "in_window"
    elif local_time < config.window_start:
        reason = "before_ready_cutoff"
    else:
        reason = "window_closed"
    return PrewarmWindowDecision(
        market=config.market,
        in_window=reason == "in_window",
        reason=reason,
        now_local=local_now,
        window_start=config.window_start,
        window_end=config.window_end,
    )


def is_in_prewarm_window(
    market: str,
    now_utc: datetime | None = None,
) -> bool:
    return prewarm_window_status(market, now_utc).in_window


def resolve_due_prewarm_trading_day(
    market: str,
    now_utc: datetime | None = None,
) -> str | None:
    decision = prewarm_window_status(market, now_utc)
    if not decision.in_window:
        return None

    trading_day = latest_trading_day_on_or_before(market, decision.now_local.date())
    if trading_day != decision.now_local.date():
        return None
    return trading_day.isoformat()


async def check_vendor_ready(market: str, trading_day: str) -> bool:
    from web.backend.runtime import data_sync_tasks, screener_prewarm

    payload = screener_prewarm.build_ohlcv_sync_payload(market, trading_day)
    try:
        await asyncio.to_thread(data_sync_tasks.ensure_ohlcv_vendor_ready, payload)
    except data_sync_tasks.VendorDataNotReadyError:
        return False
    return True
