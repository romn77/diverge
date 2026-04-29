from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_TICKER_PATTERN = re.compile(r"^[A-Z0-9](?:[A-Z0-9._-]{0,30}[A-Z0-9])?$")


def normalize_ticker_symbol(value: Any, *, field_name: str = "ticker") -> str:
    """Normalize a ticker while keeping it safe as a filesystem path component."""
    ticker = str(value).strip().upper() if value is not None else ""
    if not ticker:
        raise ValueError(f"{field_name} is required")
    if Path(ticker).is_absolute() or "/" in ticker or "\\" in ticker or ".." in ticker:
        raise ValueError(f"{field_name} contains unsupported path characters")
    if not _TICKER_PATTERN.fullmatch(ticker):
        raise ValueError(
            f"{field_name} must use 1-32 characters from letters, digits, dot, dash, or underscore"
        )
    return ticker
