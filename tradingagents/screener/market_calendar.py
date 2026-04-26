from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

import pandas as pd
from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    GoodFriday,
    Holiday,
    USLaborDay,
    USMartinLutherKingJr,
    USMemorialDay,
    USPresidentsDay,
    USThanksgivingDay,
    nearest_workday,
)


class _NYSEHolidayCalendar(AbstractHolidayCalendar):
    rules = [
        Holiday("NewYearsDay", month=1, day=1, observance=nearest_workday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, observance=nearest_workday, start_date="2021-06-19"),
        Holiday("IndependenceDay", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
    ]


CN_MARKET_CLOSED_RANGES: dict[int, tuple[tuple[str, str], ...]] = {
    2022: (
        ("2022-01-01", "2022-01-03"),
        ("2022-01-31", "2022-02-06"),
        ("2022-04-03", "2022-04-05"),
        ("2022-04-30", "2022-05-04"),
        ("2022-06-03", "2022-06-05"),
        ("2022-09-10", "2022-09-12"),
        ("2022-10-01", "2022-10-07"),
    ),
    2023: (
        ("2023-01-01", "2023-01-02"),
        ("2023-01-21", "2023-01-27"),
        ("2023-04-05", "2023-04-05"),
        ("2023-04-29", "2023-05-03"),
        ("2023-06-22", "2023-06-24"),
        ("2023-09-29", "2023-10-06"),
    ),
    2024: (
        ("2023-12-30", "2024-01-01"),
        ("2024-02-09", "2024-02-17"),
        ("2024-04-04", "2024-04-06"),
        ("2024-05-01", "2024-05-05"),
        ("2024-06-10", "2024-06-10"),
        ("2024-09-15", "2024-09-17"),
        ("2024-10-01", "2024-10-07"),
    ),
    2025: (
        ("2025-01-01", "2025-01-01"),
        ("2025-01-28", "2025-02-04"),
        ("2025-04-04", "2025-04-06"),
        ("2025-05-01", "2025-05-05"),
        ("2025-05-31", "2025-06-02"),
        ("2025-10-01", "2025-10-08"),
    ),
    2026: (
        ("2026-01-01", "2026-01-03"),
        ("2026-02-15", "2026-02-23"),
        ("2026-04-04", "2026-04-06"),
        ("2026-05-01", "2026-05-05"),
        ("2026-06-19", "2026-06-21"),
        ("2026-09-25", "2026-09-27"),
        ("2026-10-01", "2026-10-07"),
    ),
}


def _parse_date(value: object) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _count_weekdays(start_date: date, end_date: date) -> int:
    if end_date < start_date:
        return 0

    count = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


@lru_cache(maxsize=1)
def _cn_closed_dates() -> set[date]:
    closed_dates: set[date] = set()
    for ranges in CN_MARKET_CLOSED_RANGES.values():
        for start_value, end_value in ranges:
            current = _parse_date(start_value)
            end_date = _parse_date(end_value)
            if current is None or end_date is None:
                continue
            while current <= end_date:
                if current.weekday() < 5:
                    closed_dates.add(current)
                current += timedelta(days=1)
    return closed_dates


@lru_cache(maxsize=None)
def _us_holidays(year: int) -> set[date]:
    holidays = _NYSEHolidayCalendar().holidays(
        f"{year}-01-01",
        f"{year}-12-31",
    )
    return {timestamp.date() for timestamp in holidays}


def is_market_trading_day(market: str, day: date) -> bool:
    if day.weekday() >= 5:
        return False

    normalized_market = str(market).strip().lower()
    if normalized_market == "us":
        return day not in _us_holidays(day.year)
    if normalized_market == "cn":
        return day not in _cn_closed_dates()
    return True


def latest_trading_day_on_or_before(market: str, day_value: object) -> date | None:
    day = _parse_date(day_value)
    if day is None:
        return None

    normalized_market = str(market).strip().lower()
    current = day
    while not is_market_trading_day(normalized_market, current):
        current -= timedelta(days=1)
    return current


def count_trading_days(
    market: str,
    start_date_value: object,
    end_date_value: object,
    *,
    fallback_to_weekdays: bool = False,
) -> int | None:
    start_date = _parse_date(start_date_value)
    end_date = _parse_date(end_date_value)
    if start_date is None or end_date is None:
        return None
    if end_date < start_date:
        return 0

    normalized_market = str(market).strip().lower()
    if normalized_market == "cn":
        years = range(start_date.year, end_date.year + 1)
        unsupported_years = [year for year in years if year not in CN_MARKET_CLOSED_RANGES]
        if unsupported_years:
            if fallback_to_weekdays:
                return _count_weekdays(start_date, end_date)
            unsupported = ", ".join(str(year) for year in unsupported_years)
            raise ValueError(
                f"cn market calendar is not configured for year(s): {unsupported}"
            )

    count = 0
    current = start_date
    while current <= end_date:
        if is_market_trading_day(normalized_market, current):
            count += 1
        current += timedelta(days=1)
    return count


def last_n_trading_days(
    market: str,
    end_date_value: object,
    num_days: int,
) -> list[date]:
    if num_days <= 0:
        return []

    end_date = _parse_date(end_date_value)
    if end_date is None:
        return []

    normalized_market = str(market).strip().lower()
    trading_days: list[date] = []
    current = end_date
    while len(trading_days) < num_days:
        if is_market_trading_day(normalized_market, current):
            trading_days.append(current)
        current -= timedelta(days=1)
    trading_days.reverse()
    return trading_days


def trading_day_lag(
    market: str,
    as_of_date_value: object,
    data_end_date_value: object,
) -> int | None:
    as_of_date = _parse_date(as_of_date_value)
    data_end_date = _parse_date(data_end_date_value)
    if as_of_date is None or data_end_date is None:
        return None
    if data_end_date >= as_of_date:
        return 0

    normalized_market = str(market).strip().lower()
    if normalized_market == "cn":
        years = range(data_end_date.year, as_of_date.year + 1)
        unsupported_years = [year for year in years if year not in CN_MARKET_CLOSED_RANGES]
        if unsupported_years:
            unsupported = ", ".join(str(year) for year in unsupported_years)
            raise ValueError(
                f"cn market calendar is not configured for year(s): {unsupported}"
            )

    lag = 0
    current = data_end_date + timedelta(days=1)
    while current <= as_of_date:
        if is_market_trading_day(normalized_market, current):
            lag += 1
        current += timedelta(days=1)
    return lag
