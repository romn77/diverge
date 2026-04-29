from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_TICKER_PATTERN = re.compile(r"^[A-Z0-9](?:[A-Z0-9._-]{0,30}[A-Z0-9])?$")
_ANALYSIS_TICKER_EXCHANGES = {"AUTO", "SH", "SZ", "BJ"}
_UNSUPPORTED_BJ_ANALYSIS_MESSAGE = (
    "BJ exchange tickers are not supported for analysis yet. "
    "Use SH or SZ tickers for now."
)


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


def normalize_analysis_ticker_symbol(
    value: Any,
    *,
    ticker_exchange: str | None = None,
    field_name: str = "ticker",
) -> str:
    """Normalize analysis tickers, adding CN exchange suffixes when possible."""
    ticker = normalize_ticker_symbol(value, field_name=field_name)
    exchange = str(ticker_exchange or "auto").strip().upper()
    if not exchange:
        exchange = "AUTO"
    if exchange not in _ANALYSIS_TICKER_EXCHANGES:
        raise ValueError("ticker_exchange must be one of auto, SH, SZ, or BJ")

    from diverge.dataflows.cn_market_utils import (
        CN_TICKER_RE,
        parse_and_normalize_cn_ticker,
    )

    if exchange != "AUTO":
        match = CN_TICKER_RE.match(ticker)
        if not match:
            raise ValueError("ticker_exchange can only be used with 6-digit CN tickers")
        embedded_exchange = match.group("prefix") or match.group("suffix")
        if embedded_exchange and embedded_exchange.upper() != exchange:
            raise ValueError("ticker exchange does not match the selected exchange")
        if exchange == "BJ":
            raise ValueError(_UNSUPPORTED_BJ_ANALYSIS_MESSAGE)
        return f"{match.group('code')}.{exchange}"

    try:
        parsed = parse_and_normalize_cn_ticker(ticker)
    except ValueError:
        return ticker
    if parsed["exchange"] == "BJ":
        raise ValueError(_UNSUPPORTED_BJ_ANALYSIS_MESSAGE)
    return parsed["tushare"]
