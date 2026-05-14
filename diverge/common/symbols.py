from __future__ import annotations

import re
from pathlib import Path
from typing import Any


CN_TICKER_RE = re.compile(
    r"^(?:(?P<prefix>SH|SZ|BJ))?(?P<code>\d{6})(?:\.(?P<suffix>SH|SZ|BJ))?$",
    re.IGNORECASE,
)
US_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")

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


def infer_cn_exchange(code: str) -> str:
    if code.startswith(("600", "601", "603", "605", "688", "689")):
        return "SH"
    if code.startswith(("000", "001", "002", "003", "300", "301", "302")):
        return "SZ"
    if code.startswith(
        (
            "430",
            "440",
            "830",
            "831",
            "832",
            "833",
            "834",
            "835",
            "836",
            "837",
            "838",
            "839",
            "870",
            "871",
            "872",
            "873",
            "874",
            "875",
            "876",
            "877",
            "878",
            "879",
            "920",
        )
    ):
        return "BJ"
    if code.startswith(("4", "8")):
        return "BJ"
    raise ValueError(f"Unable to infer exchange for ticker '{code}'")


def parse_and_normalize_cn_ticker(symbol: str) -> dict[str, str]:
    value = symbol.strip().upper()
    match = CN_TICKER_RE.match(value)
    if not match:
        raise ValueError(f"Unsupported CN ticker format: '{symbol}'")

    code = match.group("code")
    prefix = match.group("prefix")
    suffix = match.group("suffix")

    if prefix and suffix and prefix != suffix:
        raise ValueError(f"Ticker prefix/suffix mismatch: '{symbol}'")

    exchange = prefix or suffix or infer_cn_exchange(code)
    yfinance_exchange = "SS" if exchange == "SH" else exchange

    return {
        "raw": code,
        "exchange": exchange,
        "akshare": code,
        "akshare_prefixed": f"{exchange.lower()}{code}",
        "akshare_em": f"{exchange}{code}",
        "tushare": f"{code}.{exchange}",
        "yfinance": f"{code}.{yfinance_exchange}",
    }


def detect_market(symbol: str) -> str:
    value = symbol.strip().upper()
    if CN_TICKER_RE.match(value):
        return "cn"
    if US_TICKER_RE.match(value):
        return "us"
    return "unknown"


def resolve_symbol_market(symbol: str, market: str | None = None) -> str:
    normalized_market = str(market or "").strip().lower()
    if normalized_market in {"cn", "china", "sh", "sz", "sse", "szse"}:
        return "cn"
    if normalized_market in {"us", "usa", "nasdaq", "nyse", "amex"}:
        return "us"

    detected_market = detect_market(str(symbol).strip())
    return detected_market if detected_market in {"cn", "us"} else "us"


def normalize_symbol_for_vendor(symbol: str, market: str, vendor: str) -> str:
    if market != "cn":
        return symbol

    parsed = parse_and_normalize_cn_ticker(symbol)
    if vendor == "akshare":
        return parsed["akshare"]
    if vendor == "tushare":
        return parsed["tushare"]
    if vendor == "yfinance":
        return parsed["yfinance"]
    return symbol


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
