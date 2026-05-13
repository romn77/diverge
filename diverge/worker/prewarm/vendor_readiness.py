from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any


async def _run_blocking(function: Callable[..., Any], *args: Any) -> Any:
    return await asyncio.to_thread(function, *args)


async def check_vendor_ready(market: str, trading_day: str) -> bool:
    from web.backend.runtime import data_sync_tasks, screener_prewarm

    payload = screener_prewarm.build_ohlcv_sync_payload(market, trading_day)
    try:
        await _run_blocking(data_sync_tasks.ensure_ohlcv_vendor_ready, payload)
    except data_sync_tasks.VendorDataNotReadyError:
        return False
    return True
