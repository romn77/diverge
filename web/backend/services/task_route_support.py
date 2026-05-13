from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from web.backend import app_config
from web.backend.runtime import analysis_tasks, screener_tasks, task_store


def serialize_sse_event(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def enforce_task_submission_capacity(current_user: Any) -> None:
    if not task_store.redis_task_backend_enabled():
        if (
            analysis_tasks.count_active_tasks() + screener_tasks.count_active_tasks()
            >= task_store.get_queue_limit()
        ):
            raise HTTPException(
                status_code=409,
                detail="Task queue is full. Wait for the active tasks to finish.",
            )
        return

    store = task_store.get_task_store()
    global_active = store.count_active("analysis") + store.count_active("screener")
    if global_active >= task_store.get_global_pending_limit():
        raise HTTPException(
            status_code=409,
            detail="Global task queue is full. Wait for queued work to finish.",
        )
    if current_user is None:
        return
    user_limit = task_store.get_user_pending_limit(getattr(current_user, "role", None))
    if store.count_active_by_owner(current_user.id) >= user_limit:
        raise HTTPException(
            status_code=409,
            detail=(
                f"User task queue is full ({user_limit} queued, waiting, or running tasks). "
                "Cancel queued work or wait for tasks to finish."
            ),
        )


async def stream_task_progress(
    *,
    request: Request,
    get_task: Callable[[], Any],
    get_progress_events: Callable[[int], list[dict[str, Any]]],
    start_cursor: int = 0,
    poll_seconds: float = 0.25,
) -> StreamingResponse:
    async def event_generator():
        cursor = max(start_cursor, 0)

        while True:
            if await request.is_disconnected():
                break

            try:
                task = get_task()
            except HTTPException:
                break
            pending_events = get_progress_events(cursor)
            task_status = task.status

            for event in pending_events:
                cursor += 1
                yield serialize_sse_event(event)

            if task_status in app_config.TERMINAL_TASK_STATUSES and not pending_events:
                break

            await asyncio.sleep(poll_seconds)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
