from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from diverge.dataflows.cn_market_utils import (
    CN_TICKER_RE,
    US_TICKER_RE,
    parse_and_normalize_cn_ticker,
)
from diverge.ticker_symbols import normalize_ticker_symbol


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CN_MANIFEST = PROJECT_ROOT / "diverge" / "data" / "cn_manifest.csv"
DEFAULT_US_MANIFEST = PROJECT_ROOT / "diverge" / "data" / "us_manifest.csv"
SUPPORTED_MARKETS = {"cn", "us", "unknown"}
SUPPORTED_ASSET_TYPES = {"equity", "etf", "unknown"}

_CN_ETF_PREFIXES = (
    "159",
    "510",
    "511",
    "512",
    "513",
    "515",
    "516",
    "517",
    "518",
    "588",
)
_COMMON_US_ETFS = {
    "DIA",
    "IWM",
    "QQQ",
    "SPY",
    "VOO",
    "VTI",
    "XLK",
    "XLF",
    "XLE",
}


def resolve_symbol(
    symbol: Any,
    *,
    manual_market: str | None = None,
    manual_exchange: str | None = None,
    manual_asset_type: str | None = None,
    cn_manifest_path: str | Path | None = None,
    us_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    raw_symbol = str(symbol).strip().upper() if symbol is not None else ""
    if not raw_symbol:
        raise ValueError("symbol is required")
    if _has_path_characters(raw_symbol):
        raise ValueError("symbol contains unsupported path characters")

    rule_resolution = _resolve_without_manual(
        raw_symbol,
        cn_manifest_path=cn_manifest_path,
        us_manifest_path=us_manifest_path,
    )

    if manual_market is None and manual_exchange is None and manual_asset_type is None:
        return rule_resolution

    return _manual_resolution(
        raw_symbol,
        rule_resolution,
        manual_market=manual_market,
        manual_exchange=manual_exchange,
        manual_asset_type=manual_asset_type,
    )


def _resolve_without_manual(
    raw_symbol: str,
    *,
    cn_manifest_path: str | Path | None,
    us_manifest_path: str | Path | None,
) -> dict[str, Any]:
    normalized_input = raw_symbol.upper()
    manifest_match = _find_manifest_match(
        normalized_input,
        cn_manifest_path=cn_manifest_path,
        us_manifest_path=us_manifest_path,
    )
    if manifest_match is not None:
        return manifest_match

    cn_resolution = _resolve_cn_rule(normalized_input)
    if cn_resolution is not None:
        return cn_resolution

    if US_TICKER_RE.match(normalized_input):
        return _base_resolution(
            raw_symbol=raw_symbol,
            canonical_symbol=normalize_ticker_symbol(normalized_input),
            market="us",
            exchange=None,
            asset_type=_infer_us_asset_type(normalized_input),
            confidence="medium",
            source="rule",
        )

    return _unknown_resolution(
        raw_symbol, ["Unable to resolve symbol as CN/US equity or ETF."]
    )


def _find_manifest_match(
    raw_symbol: str,
    *,
    cn_manifest_path: str | Path | None,
    us_manifest_path: str | Path | None,
) -> dict[str, Any] | None:
    normalized_candidates = _manifest_candidates(raw_symbol)
    for market, path in (
        ("cn", Path(cn_manifest_path) if cn_manifest_path else DEFAULT_CN_MANIFEST),
        ("us", Path(us_manifest_path) if us_manifest_path else DEFAULT_US_MANIFEST),
    ):
        rows = _load_manifest(path)
        for candidate in normalized_candidates:
            row = rows.get(candidate)
            if row is None:
                continue
            symbol = normalize_ticker_symbol(row["symbol"])
            exchange = _normalize_exchange(row.get("exchange"), market)
            return _base_resolution(
                raw_symbol=raw_symbol,
                canonical_symbol=symbol,
                market=market,
                exchange=exchange,
                asset_type=_infer_manifest_asset_type(row, market),
                confidence="high",
                source="manifest",
            )
    return None


def _manifest_candidates(raw_symbol: str) -> list[str]:
    candidates = {raw_symbol}
    try:
        parsed = parse_and_normalize_cn_ticker(raw_symbol)
    except ValueError:
        pass
    else:
        candidates.add(parsed["tushare"])
        candidates.add(parsed["raw"])
    return sorted(candidates)


@lru_cache(maxsize=8)
def _load_manifest(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            rows[symbol] = {str(key): str(value or "") for key, value in row.items()}
    return rows


def _resolve_cn_rule(raw_symbol: str) -> dict[str, Any] | None:
    if not CN_TICKER_RE.match(raw_symbol):
        if re.fullmatch(r"\d{4,5}", raw_symbol):
            return _unknown_resolution(
                raw_symbol,
                ["Input may be an unsupported non-CN/US symbol."],
            )
        return None
    try:
        parsed = parse_and_normalize_cn_ticker(raw_symbol)
    except ValueError as exc:
        return _unknown_resolution(raw_symbol, [str(exc)])
    exchange = parsed["exchange"]
    if exchange == "BJ":
        return _unknown_resolution(
            raw_symbol,
            ["BJ exchange tickers are outside the first CN/US resolver scope."],
        )
    return _base_resolution(
        raw_symbol=raw_symbol,
        canonical_symbol=normalize_ticker_symbol(parsed["tushare"]),
        market="cn",
        exchange=exchange,
        asset_type=_infer_cn_asset_type(parsed["raw"]),
        confidence="high",
        source="rule",
    )


def _manual_resolution(
    raw_symbol: str,
    rule_resolution: dict[str, Any],
    *,
    manual_market: str | None,
    manual_exchange: str | None,
    manual_asset_type: str | None,
) -> dict[str, Any]:
    market = _normalize_market(
        manual_market or rule_resolution.get("market") or "unknown"
    )
    exchange = _normalize_exchange(
        manual_exchange
        if manual_exchange is not None
        else rule_resolution.get("exchange"),
        market,
    )
    asset_type = _normalize_asset_type(
        manual_asset_type or rule_resolution.get("asset_type") or "unknown"
    )
    canonical_symbol = _manual_canonical_symbol(
        raw_symbol, market, exchange, rule_resolution
    )
    warnings = ["Market was manually overridden."]
    if rule_resolution.get("market") not in {
        None,
        "unknown",
    } and market != rule_resolution.get("market"):
        warnings.append("Manual override conflicts with rule-based market detection.")
    return _base_resolution(
        raw_symbol=raw_symbol,
        canonical_symbol=canonical_symbol,
        market=market,
        exchange=exchange,
        asset_type=asset_type,
        confidence="manual",
        source="manual",
        warnings=warnings,
    )


def _manual_canonical_symbol(
    raw_symbol: str,
    market: str,
    exchange: str | None,
    rule_resolution: dict[str, Any],
) -> str:
    if market == rule_resolution.get("market") and rule_resolution.get(
        "canonical_symbol"
    ):
        return normalize_ticker_symbol(rule_resolution["canonical_symbol"])
    if market == "cn" and exchange in {"SH", "SZ"}:
        try:
            parsed = parse_and_normalize_cn_ticker(raw_symbol)
        except ValueError:
            pass
        else:
            return normalize_ticker_symbol(f"{parsed['raw']}.{exchange}")
    return normalize_ticker_symbol(raw_symbol)


def _unknown_resolution(raw_symbol: str, warnings: list[str]) -> dict[str, Any]:
    return _base_resolution(
        raw_symbol=raw_symbol,
        canonical_symbol=normalize_ticker_symbol(raw_symbol),
        market="unknown",
        exchange=None,
        asset_type="unknown",
        confidence="low",
        source="unknown",
        warnings=warnings,
    )


def _base_resolution(
    *,
    raw_symbol: str,
    canonical_symbol: str,
    market: str,
    exchange: str | None,
    asset_type: str,
    confidence: str,
    source: str,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    canonical = normalize_ticker_symbol(canonical_symbol)
    return {
        "raw_symbol": raw_symbol,
        "canonical_symbol": canonical,
        "display_symbol": canonical,
        "market": _normalize_market(market),
        "exchange": exchange,
        "asset_type": _normalize_asset_type(asset_type),
        "confidence": confidence,
        "source": source,
        "warnings": list(warnings or []),
    }


def _infer_manifest_asset_type(row: dict[str, str], market: str) -> str:
    symbol = str(row.get("symbol") or "").upper()
    sector = str(row.get("sector") or "").lower()
    name = str(row.get("name") or "").lower()
    if "etf" in sector or "etf" in name:
        return "etf"
    if market == "cn" and _cn_symbol_code(symbol).startswith(_CN_ETF_PREFIXES):
        return "etf"
    if market == "us" and symbol in _COMMON_US_ETFS:
        return "etf"
    return "equity"


def _infer_cn_asset_type(code: str) -> str:
    return "etf" if code.startswith(_CN_ETF_PREFIXES) else "equity"


def _infer_us_asset_type(symbol: str) -> str:
    return "etf" if symbol in _COMMON_US_ETFS else "equity"


def _cn_symbol_code(symbol: str) -> str:
    match = re.search(r"(\d{6})", symbol)
    return match.group(1) if match else symbol


def _normalize_market(value: Any) -> str:
    market = str(value or "").strip().lower()
    if market in {"china", "sh", "sz", "sse", "szse"}:
        market = "cn"
    if market in {"usa", "nasdaq", "nyse", "amex"}:
        market = "us"
    if market not in SUPPORTED_MARKETS:
        raise ValueError("market must be one of cn, us, or unknown")
    return market


def _normalize_asset_type(value: Any) -> str:
    asset_type = str(value or "").strip().lower() or "unknown"
    if asset_type not in SUPPORTED_ASSET_TYPES:
        asset_type = "unknown"
    return asset_type


def _normalize_exchange(value: Any, market: str) -> str | None:
    exchange = str(value or "").strip().upper()
    if not exchange:
        return None
    if market == "cn":
        if exchange in {"SSE", "SH"}:
            return "SH"
        if exchange in {"SZSE", "SZ"}:
            return "SZ"
    return exchange


def _has_path_characters(value: str) -> bool:
    return Path(value).is_absolute() or "/" in value or "\\" in value or ".." in value
