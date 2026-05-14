from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from diverge.common.dates import parse_iso_date
from diverge.common.market_calendar import latest_trading_day_on_or_before
from diverge.dataflows.vendor_errors import VendorDataEmptyError
from diverge.market_data.price_history import fetch_price_history

OHLCV_READY_CHECKS = {
    ("cn", "tushare"): {
        "vendor_label": "Tushare",
        "timezone": "Asia/Shanghai",
        "cutoff_env": "DATA_SYNC_TUSHARE_READY_TIME",
        "default_cutoff": "18:10",
        "probe_symbols": ["000001.SZ", "600519.SH"],
    },
    ("us", "massive"): {
        "vendor_label": "Massive",
        "timezone": "America/New_York",
        "cutoff_env": "DATA_SYNC_MASSIVE_READY_TIME",
        "default_cutoff": "21:10",
        "probe_symbols": ["AAPL", "MSFT"],
    },
}
DEFAULT_READY_SOURCES = {"cn": "tushare", "us": "massive"}
MARKET_TIMEZONES = {"cn": "Asia/Shanghai", "us": "America/New_York"}

NowForVendorTimezone = Callable[[str], datetime]
PriceHistoryFetcher = Callable[..., pd.DataFrame]


class VendorDataNotReadyError(RuntimeError):
    """Raised when same-day vendor bars are not available enough to start sync."""


def now_for_vendor_timezone(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name)).replace(tzinfo=None)


def _parse_cutoff_time(raw_value: str) -> time:
    try:
        hour_text, minute_text = raw_value.strip().split(":", 1)
        return time(hour=int(hour_text), minute=int(minute_text))
    except Exception as exc:
        raise RuntimeError(
            f"Invalid data sync ready cutoff time '{raw_value}'. Use HH:MM."
        ) from exc


def _configured_cutoff_time(env_name: str, default_value: str) -> time:
    return _parse_cutoff_time(os.environ.get(env_name, default_value))


def _ohlcv_source_for_payload(payload: dict[str, Any], market: str) -> str:
    if market == "cn":
        return str(payload.get("cn_data_source") or "tushare").strip().lower()
    return str(payload.get("us_data_source") or "yfinance").strip().lower()


def _ohlcv_ready_context(
    market: str,
    source: str,
    *,
    now_for_timezone: NowForVendorTimezone = now_for_vendor_timezone,
) -> dict[str, Any] | None:
    check = OHLCV_READY_CHECKS.get((market, source))
    if check is None:
        return None

    timezone_name = str(check["timezone"])
    return {
        **check,
        "timezone": timezone_name,
        "now_local": now_for_timezone(timezone_name),
        "cutoff": _configured_cutoff_time(
            str(check["cutoff_env"]),
            str(check["default_cutoff"]),
        ),
    }


def _price_frame_has_as_of_date(frame: pd.DataFrame, as_of_date: str) -> bool:
    if frame is None or frame.empty or "Date" not in frame.columns:
        return False
    dates = pd.to_datetime(frame["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return bool((dates == as_of_date).any())


def _raise_vendor_not_ready(
    *,
    vendor_label: str,
    as_of_date: str,
    cutoff: time,
    timezone_name: str,
    reason: str,
) -> None:
    raise VendorDataNotReadyError(
        f"{vendor_label} daily data for {as_of_date} is not ready. "
        f"{reason} Retry after {cutoff.strftime('%H:%M')} {timezone_name}."
    )


def _probe_ohlcv_vendor_ready(
    *,
    market: str,
    source: str,
    as_of_date: str,
    probe_symbols: list[str],
    fetch_price_history_fn: PriceHistoryFetcher = fetch_price_history,
) -> bool:
    for symbol in probe_symbols:
        try:
            frame = fetch_price_history_fn(
                symbol,
                market,
                as_of_date,
                as_of_date,
                cn_data_source=source if market == "cn" else "tushare",
                us_data_source=source if market == "us" else "yfinance",
            )
        except VendorDataEmptyError:
            continue
        if _price_frame_has_as_of_date(frame, as_of_date):
            return True
    return False


def ensure_ohlcv_vendor_ready(
    payload: dict[str, Any],
    *,
    now_for_timezone: NowForVendorTimezone = now_for_vendor_timezone,
    fetch_price_history_fn: PriceHistoryFetcher = fetch_price_history,
) -> None:
    as_of_date = str(payload["as_of_date"])
    requested_date = parse_iso_date(as_of_date)
    if requested_date is None:
        raise RuntimeError("as_of_date must use YYYY-MM-DD format")
    markets = [str(market).strip().lower() for market in payload.get("markets") or []]

    for market in markets:
        source = _ohlcv_source_for_payload(payload, market)
        ready_context = _ohlcv_ready_context(
            market,
            source,
            now_for_timezone=now_for_timezone,
        )
        if ready_context is None:
            continue

        timezone_name = str(ready_context["timezone"])
        now_local = ready_context["now_local"]
        cutoff = ready_context["cutoff"]
        vendor_label = str(ready_context["vendor_label"])

        if requested_date > now_local.date():
            _raise_vendor_not_ready(
                vendor_label=vendor_label,
                as_of_date=as_of_date,
                cutoff=cutoff,
                timezone_name=timezone_name,
                reason="Requested date is ahead of the vendor-local date.",
            )
        if requested_date < now_local.date():
            continue
        if now_local.time() < cutoff:
            _raise_vendor_not_ready(
                vendor_label=vendor_label,
                as_of_date=as_of_date,
                cutoff=cutoff,
                timezone_name=timezone_name,
                reason=f"Current vendor-local time is {now_local.strftime('%H:%M')}.",
            )

        if not _probe_ohlcv_vendor_ready(
            market=market,
            source=source,
            as_of_date=as_of_date,
            probe_symbols=list(ready_context["probe_symbols"]),
            fetch_price_history_fn=fetch_price_history_fn,
        ):
            _raise_vendor_not_ready(
                vendor_label=vendor_label,
                as_of_date=as_of_date,
                cutoff=cutoff,
                timezone_name=timezone_name,
                reason="Readiness probe returned no bars for representative symbols.",
            )


def resolve_ready_ohlcv_as_of_date(
    market: str,
    source: str,
    candidate_day: date,
    *,
    now_for_timezone: NowForVendorTimezone = now_for_vendor_timezone,
) -> date:
    """Resolve the latest default screener date that should have vendor OHLCV data."""
    normalized_market = str(market).strip().lower()
    normalized_source = str(source).strip().lower()
    ready_context = _ohlcv_ready_context(
        normalized_market,
        normalized_source,
        now_for_timezone=now_for_timezone,
    )
    if ready_context is None:
        return candidate_day

    now_local = ready_context["now_local"]
    cutoff = ready_context["cutoff"]

    ready_day = min(candidate_day, now_local.date())
    if ready_day == now_local.date() and now_local.time() < cutoff:
        ready_day = ready_day - timedelta(days=1)

    resolved_day = latest_trading_day_on_or_before(normalized_market, ready_day)
    return resolved_day or ready_day


def resolve_latest_ready_trading_day(
    market: str,
    source: str | None = None,
    *,
    now_for_timezone: NowForVendorTimezone = now_for_vendor_timezone,
) -> date:
    """Resolve the latest market-local trading day with expected ready data."""
    normalized_market = str(market).strip().lower()
    normalized_source = (
        str(source or DEFAULT_READY_SOURCES.get(normalized_market) or "")
        .strip()
        .lower()
    )
    ready_context = _ohlcv_ready_context(
        normalized_market,
        normalized_source,
        now_for_timezone=now_for_timezone,
    )
    if ready_context is not None:
        candidate_day = ready_context["now_local"].date()
        return resolve_ready_ohlcv_as_of_date(
            normalized_market,
            normalized_source,
            candidate_day,
            now_for_timezone=now_for_timezone,
        )

    timezone_name = MARKET_TIMEZONES.get(normalized_market, "UTC")
    candidate_day = now_for_timezone(timezone_name).date()
    trading_day = latest_trading_day_on_or_before(normalized_market, candidate_day)
    return trading_day or candidate_day
