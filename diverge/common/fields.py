from __future__ import annotations

from typing import Any, TypeVar

ErrorT = TypeVar("ErrorT", bound=Exception)


def require_text(
    value: Any,
    field_name: str,
    *,
    error_type: type[ErrorT] = ValueError,
) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise error_type(f"{field_name} is required")
    return text


def normalize_optional_text(
    value: Any, *, empty_value: str | None = None
) -> str | None:
    if value is None:
        return empty_value
    candidate = str(value).strip()
    return candidate or empty_value


def normalize_optional_number(value: Any, field_name: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
