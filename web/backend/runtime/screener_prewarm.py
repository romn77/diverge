from __future__ import annotations

from typing import Any

from web.backend.runtime import data_sync_tasks
from web.backend.services import screener_prewarm_payloads


def _resolve_screener_data_sources() -> dict[str, object]:
    return screener_prewarm_payloads.resolve_screener_data_sources()


def default_screener_prewarm_payload(market: str, as_of_date: str) -> dict[str, Any]:
    return screener_prewarm_payloads.default_screener_prewarm_payload(
        market,
        as_of_date,
    )


def _payload_for_market(
    raw_payload: dict[str, Any], market: str, as_of_date: str
) -> dict[str, Any]:
    return screener_prewarm_payloads._payload_for_market(
        raw_payload,
        market,
        as_of_date,
    )


def collect_screener_prewarm_payloads(
    market: str, as_of_date: str
) -> list[dict[str, Any]]:
    return screener_prewarm_payloads.collect_screener_prewarm_payloads(
        market,
        as_of_date,
    )


def build_screener_config_payload(request_payload: dict[str, Any]) -> dict[str, Any]:
    return screener_prewarm_payloads.build_screener_config_payload(request_payload)


def build_ohlcv_sync_payload(market: str, as_of_date: str) -> dict[str, Any]:
    return screener_prewarm_payloads.build_ohlcv_sync_payload(market, as_of_date)


def build_fundamental_sync_payload(
    market: str,
    as_of_date: str,
    *,
    symbols: list[str],
) -> dict[str, Any]:
    return screener_prewarm_payloads.build_fundamental_sync_payload(
        market,
        as_of_date,
        symbols=symbols,
    )


def run_fundamental_prewarm_sync(
    market: str,
    as_of_date: str,
    *,
    ohlcv_payload: dict[str, Any],
) -> dict[str, Any]:
    symbols_by_market = data_sync_tasks.resolve_universe_symbols(ohlcv_payload)
    symbols = symbols_by_market.get(market, [])
    if not symbols:
        return {
            "market": market,
            "as_of_date": as_of_date,
            "status": "skipped",
            "reason": "no_universe_symbols",
        }
    payload = build_fundamental_sync_payload(market, as_of_date, symbols=symbols)
    return data_sync_tasks.run_fundamental_sync_payload(payload)
