from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import patch

import httpx


async def _inline_run_sync(func, *args, **kwargs):
    kwargs.pop("abandon_on_cancel", None)
    kwargs.pop("cancellable", None)
    kwargs.pop("limiter", None)
    return func(*args)


@asynccontextmanager
async def app_client(app):
    transport = httpx.ASGITransport(app=app)
    with patch("anyio.to_thread.run_sync", side_effect=_inline_run_sync):
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                yield client
