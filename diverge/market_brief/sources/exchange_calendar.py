from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from diverge.common.market_calendar import latest_trading_day_on_or_before
from diverge.market_brief.schema import MarketBriefMarket, MarketCalendarItem


MARKET_LABELS: dict[MarketBriefMarket, str] = {
    "cn": "A-share",
    "us": "US",
}

MARKET_TIMEZONES: dict[MarketBriefMarket, str] = {
    "cn": "Asia/Shanghai",
    "us": "America/New_York",
}

MARKET_OPEN_CLOSE: dict[MarketBriefMarket, tuple[time, time]] = {
    "cn": (time(9, 30), time(15, 0)),
    "us": (time(9, 30), time(16, 0)),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def coerce_utc(value: datetime | None) -> datetime:
    if value is None:
        return utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_market_calendar(
    markets: list[MarketBriefMarket],
    *,
    now_utc: datetime | None = None,
) -> list[MarketCalendarItem]:
    current_utc = coerce_utc(now_utc)
    items: list[MarketCalendarItem] = []
    for market in markets:
        timezone_name = MARKET_TIMEZONES[market]
        local_now = current_utc.astimezone(ZoneInfo(timezone_name))
        open_time, close_time = MARKET_OPEN_CLOSE[market]
        trading_day = latest_trading_day_on_or_before(market, local_now.date())
        is_trading_day = trading_day == local_now.date()
        local_time = local_now.timetz().replace(tzinfo=None)
        minutes_to_open: int | None = None
        if is_trading_day and local_time < open_time:
            open_at = local_now.replace(
                hour=open_time.hour,
                minute=open_time.minute,
                second=0,
                microsecond=0,
            )
            minutes_to_open = max(0, int((open_at - local_now).total_seconds() // 60))

        if not is_trading_day:
            session_status = "closed"
        elif local_time < open_time:
            session_status = "preopen"
        elif local_time <= close_time:
            session_status = "open"
        else:
            session_status = "closed"

        items.append(
            MarketCalendarItem(
                market=market,
                label=MARKET_LABELS[market],
                timezone=timezone_name,
                local_date=local_now.date().isoformat(),
                trading_day=trading_day.isoformat() if trading_day else None,
                is_trading_day=is_trading_day,
                open_time=open_time.strftime("%H:%M"),
                close_time=close_time.strftime("%H:%M"),
                minutes_to_open=minutes_to_open,
                session_status=session_status,
            )
        )
    return items
