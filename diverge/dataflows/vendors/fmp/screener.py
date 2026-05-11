from __future__ import annotations

from typing import Any

from .common import _make_api_request, require_non_empty


def fetch_ratios_ttm_bulk() -> list[dict[str, Any]]:
    payload = require_non_empty(
        _make_api_request("/stable/ratios-ttm-bulk"),
        context="FMP ratios TTM bulk",
    )
    return payload if isinstance(payload, list) else [payload]


def fetch_key_metrics_ttm_bulk() -> list[dict[str, Any]]:
    payload = require_non_empty(
        _make_api_request("/stable/key-metrics-ttm-bulk"),
        context="FMP key metrics TTM bulk",
    )
    return payload if isinstance(payload, list) else [payload]


def fetch_profile_bulk(*, part: int = 0) -> list[dict[str, Any]]:
    payload = require_non_empty(
        _make_api_request("/stable/profile-bulk", {"part": part}),
        context=f"FMP profile bulk part {part}",
    )
    return payload if isinstance(payload, list) else [payload]
