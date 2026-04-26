from datetime import date

from tradingagents.screener.market_calendar import latest_trading_day_on_or_before


def test_latest_trading_day_on_or_before_keeps_open_session():
    assert latest_trading_day_on_or_before("us", "2024-03-15") == date(2024, 3, 15)


def test_latest_trading_day_on_or_before_moves_us_weekend_to_previous_close():
    assert latest_trading_day_on_or_before("us", "2024-03-17") == date(2024, 3, 15)


def test_latest_trading_day_on_or_before_moves_cn_holiday_to_previous_close():
    assert latest_trading_day_on_or_before("cn", "2025-10-05") == date(2025, 9, 30)
