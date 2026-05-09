from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

ISO_DATE_FORMAT = "%Y-%m-%d"


def today_iso() -> str:
    return date.today().isoformat()


def parse_iso_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip() if value is not None else ""
    if not text:
        return None
    try:
        return datetime.strptime(text, ISO_DATE_FORMAT).date()
    except ValueError:
        return None


def require_iso_date(value: Any, field_name: str = "date") -> str:
    parsed = parse_iso_date(value)
    if parsed is None:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format")
    return parsed.isoformat()


def offset_iso_date(value: Any, days: int, field_name: str = "date") -> str:
    parsed = parse_iso_date(value)
    if parsed is None:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format")
    return (parsed + timedelta(days=days)).isoformat()


def days_before_iso_date(value: Any, days: int, field_name: str = "date") -> str:
    return offset_iso_date(value, -days, field_name=field_name)


def days_before_or_original(value: Any, days: int) -> str:
    parsed = parse_iso_date(value)
    if parsed is None:
        return str(value)
    return (parsed - timedelta(days=days)).isoformat()


def iso_date_part(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    if len(text) < 10:
        return None
    candidate = text[:10]
    return candidate if parse_iso_date(candidate) is not None else None
