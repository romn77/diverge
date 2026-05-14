from datetime import date

from diverge.common.market_calendar import (
    latest_trading_day_on_or_before,
    resolve_market_trading_date,
)


def test_latest_trading_day_on_or_before_keeps_open_session():
    assert latest_trading_day_on_or_before("us", "2024-03-15") == date(2024, 3, 15)


def test_latest_trading_day_on_or_before_moves_us_weekend_to_previous_close():
    assert latest_trading_day_on_or_before("us", "2024-03-17") == date(2024, 3, 15)


def test_latest_trading_day_on_or_before_moves_cn_holiday_to_previous_close():
    assert latest_trading_day_on_or_before("cn", "2025-10-05") == date(2025, 9, 30)


def test_resolve_market_trading_date_returns_iso_string():
    assert resolve_market_trading_date("us", "2024-03-17") == "2024-03-15"


def test_screener_market_calendar_compatibility_import():
    from diverge.screener.market_calendar import resolve_market_trading_date

    assert resolve_market_trading_date("us", "2024-03-17") == "2024-03-15"
