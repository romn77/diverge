from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from diverge.worker.prewarm import backend_adapter


async def _run_blocking(function: Callable[..., Any], *args: Any) -> Any:
    return await asyncio.to_thread(function, *args)


async def check_vendor_ready(market: str, trading_day: str) -> bool:
    try:
        await _run_blocking(
            backend_adapter.ensure_ohlcv_vendor_ready,
            market,
            trading_day,
        )
    except backend_adapter.VendorNotReady:
        return False
    return True
