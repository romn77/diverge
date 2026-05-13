from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from web.backend.services import task_route_support


def test_enforce_task_submission_capacity_counts_local_analysis_and_screener(
    monkeypatch,
):
    monkeypatch.setattr(
        task_route_support.task_store,
        "redis_task_backend_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        task_route_support.analysis_tasks,
        "count_active_tasks",
        lambda: 1,
    )
    monkeypatch.setattr(
        task_route_support.screener_tasks,
        "count_active_tasks",
        lambda: 1,
    )
    monkeypatch.setattr(task_route_support.task_store, "get_queue_limit", lambda: 2)

    with pytest.raises(HTTPException) as exc_info:
        task_route_support.enforce_task_submission_capacity(None)

    assert exc_info.value.status_code == 409
    assert "Task queue is full" in exc_info.value.detail


def test_enforce_task_submission_capacity_applies_redis_user_limit(monkeypatch):
    store = SimpleNamespace(
        count_active=lambda kind: 0,
        count_active_by_owner=lambda owner_user_id: 3,
    )
    current_user = SimpleNamespace(id="user-1", role="viewer")
    monkeypatch.setattr(
        task_route_support.task_store,
        "redis_task_backend_enabled",
        lambda: True,
    )
    monkeypatch.setattr(task_route_support.task_store, "get_task_store", lambda: store)
    monkeypatch.setattr(
        task_route_support.task_store,
        "get_global_pending_limit",
        lambda: 10,
    )
    monkeypatch.setattr(
        task_route_support.task_store,
        "get_user_pending_limit",
        lambda role: 3,
    )

    with pytest.raises(HTTPException) as exc_info:
        task_route_support.enforce_task_submission_capacity(current_user)

    assert exc_info.value.status_code == 409
    assert "User task queue is full" in exc_info.value.detail


def test_stream_task_progress_replays_from_cursor_until_terminal():
    class RequestStub:
        async def is_disconnected(self):
            return False

    events = [
        {"status": "running", "message": "old"},
        {"status": "completed", "message": "new"},
    ]

    async def render() -> str:
        response = await task_route_support.stream_task_progress(
            request=RequestStub(),
            get_task=lambda: SimpleNamespace(status="completed"),
            get_progress_events=lambda cursor: events[cursor:],
            start_cursor=1,
            poll_seconds=0,
        )
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    body = asyncio.run(render())

    assert "new" in body
    assert "old" not in body
