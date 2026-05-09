from datetime import date, datetime

import pytest

from diverge.common.dates import (
    days_before_iso_date,
    days_before_or_original,
    iso_date_part,
    offset_iso_date,
    parse_iso_date,
    require_iso_date,
)


def test_parse_iso_date_accepts_date_datetime_and_yyyy_mm_dd():
    assert parse_iso_date("2026-05-09") == date(2026, 5, 9)
    assert parse_iso_date(date(2026, 5, 9)) == date(2026, 5, 9)
    assert parse_iso_date(datetime(2026, 5, 9, 10, 30)) == date(2026, 5, 9)


def test_require_iso_date_rejects_invalid_text():
    with pytest.raises(ValueError, match="trade_date must use YYYY-MM-DD format"):
        require_iso_date("2026/05/09", "trade_date")


def test_offset_and_days_before_iso_date():
    assert offset_iso_date("2026-05-09", -7) == "2026-05-02"
    assert days_before_iso_date("2026-05-09", 7) == "2026-05-02"


def test_days_before_or_original_preserves_invalid_text():
    assert days_before_or_original("not-a-date", 7) == "not-a-date"


def test_iso_date_part_validates_first_ten_chars():
    assert iso_date_part("2026-05-09T12:00:00") == "2026-05-09"
    assert iso_date_part("not-a-date") is None
