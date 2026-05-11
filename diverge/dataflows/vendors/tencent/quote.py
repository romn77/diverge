from __future__ import annotations

import re
import time
from typing import Any

import requests

from ...vendor_errors import VendorDataEmptyError, VendorRetryableError


TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="
TENCENT_TIMEOUT_SECONDS = 10
DEFAULT_TENCENT_BATCH_SIZE = 60
DEFAULT_TENCENT_REQUEST_INTERVAL_SECONDS = 0.12


def us_symbol_to_tencent_code(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized:
        return ""
    if normalized.startswith("US"):
        return normalized
    suffix = ".N" if normalized.endswith(".N") else ".OQ"
    base = normalized.removesuffix(".OQ").removesuffix(".N")
    return f"us{base}{suffix}"


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _request_quote_batch(codes: list[str]) -> str:
    try:
        response = requests.get(
            f"{TENCENT_QUOTE_URL}{','.join(codes)}",
            timeout=TENCENT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise VendorRetryableError(f"Tencent quote request failed: {exc}") from exc
    text = response.text.strip()
    if not text:
        raise VendorDataEmptyError("Tencent quote response is empty")
    return text


def fetch_us_quote_rows(
    symbols: list[str] | tuple[str, ...],
    *,
    batch_size: int = DEFAULT_TENCENT_BATCH_SIZE,
    request_interval_seconds: float = DEFAULT_TENCENT_REQUEST_INTERVAL_SECONDS,
) -> list[dict[str, Any]]:
    normalized_symbols = [
        str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()
    ]
    codes = [us_symbol_to_tencent_code(symbol) for symbol in normalized_symbols]
    rows: list[dict[str, Any]] = []
    for index, code_batch in enumerate(_chunks(codes, max(int(batch_size), 1))):
        if index > 0 and request_interval_seconds > 0:
            time.sleep(request_interval_seconds)
        rows.extend(parse_quote_response(_request_quote_batch(code_batch)))
    return rows


def _safe_float(value: Any) -> float | None:
    try:
        text = str(value).strip()
        if not text or text == "-":
            return None
        return float(text.replace(",", ""))
    except (TypeError, ValueError):
        return None


def _parse_amount(value: Any) -> float | None:
    text = str(value).strip().upper().replace(",", "")
    if not text or text == "-":
        return None
    multiplier = 1.0
    if text.endswith("B"):
        multiplier = 1_000_000_000
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.endswith("K"):
        multiplier = 1_000
        text = text[:-1]
    parsed = _safe_float(text)
    return parsed * multiplier if parsed is not None else None


def _first_float(parts: list[str], indexes: tuple[int, ...]) -> float | None:
    for index in indexes:
        if index < len(parts):
            parsed = _safe_float(parts[index])
            if parsed is not None:
                return parsed
    return None


def _first_amount(parts: list[str], indexes: tuple[int, ...]) -> float | None:
    for index in indexes:
        if index < len(parts):
            parsed = _parse_amount(parts[index])
            if parsed is not None:
                return parsed
    return None


def parse_quote_response(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_symbol, raw_payload in re.findall(r'v_([^=]+)="([^"]*)"', text):
        parts = raw_payload.split("~")
        if len(parts) < 4:
            continue
        symbol = raw_symbol.removeprefix("us").upper()
        symbol = symbol.removesuffix(".OQ").removesuffix(".N")
        name_candidates = [parts[index] for index in (1, 2) if index < len(parts)]
        name = next((item for item in name_candidates if item and item != symbol), "")
        price = _first_float(parts, (3, 4, 5))
        prev_close = _first_float(parts, (4, 5, 30, 31))
        change_pct = _first_float(parts, (6, 32, 33))
        if change_pct is not None and abs(change_pct) >= 1:
            change_pct /= 100
        volume = _first_float(parts, (10, 36, 37))
        market_cap = _first_amount(parts, (45, 46, 47, 48))
        pe_ttm = _first_float(parts, (39, 40, 41))
        pb = _first_float(parts, (46, 47, 48, 49))
        row = {
            "symbol": symbol,
            "market": "us",
            "source": "tencent",
            "name": name,
            "currency": "USD",
            "price": price,
            "prev_close": prev_close,
            "change_pct": change_pct,
            "volume": volume,
            "market_cap": market_cap,
            "pe_ttm": pe_ttm,
            "pb": pb,
        }
        rows.append(row)
    return rows
