"""Common cross-domain utilities for Diverge."""

from .dates import (
    days_before_iso_date,
    days_before_or_original,
    iso_date_part,
    offset_iso_date,
    parse_iso_date,
    require_iso_date,
    today_iso,
)
from .fields import normalize_optional_number, normalize_optional_text, require_text
from .json_io import read_json_file, write_json_atomic
from .market_calendar import resolve_market_trading_date
from .symbols import (
    detect_market,
    normalize_analysis_ticker_symbol,
    normalize_ticker_symbol,
    resolve_symbol_market,
)

__all__ = [
    "detect_market",
    "days_before_iso_date",
    "days_before_or_original",
    "iso_date_part",
    "normalize_analysis_ticker_symbol",
    "normalize_optional_number",
    "normalize_optional_text",
    "normalize_ticker_symbol",
    "offset_iso_date",
    "parse_iso_date",
    "read_json_file",
    "require_iso_date",
    "require_text",
    "resolve_market_trading_date",
    "resolve_symbol_market",
    "today_iso",
    "write_json_atomic",
]
