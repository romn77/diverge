from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

from web.backend.runtime import task_lifecycle, task_store
from web.backend.services import backtests

KIND = "backtest"
_tasks: dict[str, "BacktestTask"] = {}
_lock = threading.Lock()


@dataclass
class BacktestTask:
    id: str
    request_payload: dict[str, Any]
    owner_user_id: str | None = None
    tenant_id: str | None = None
    status: str = "pending"
    latest_progress: dict[str, Any] | None = None
    progress_events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str | None = None
    queued_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    queue_position: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _utc_iso() -> str:
    return task_lifecycle.utc_iso()


def _event(status: str, message: str) -> dict[str, Any]:
    return task_lifecycle.progress_event(
        message,
        status=status,
        stage_status={"Backtest": status},
        agent_status={},
        current_agent="backtest_snapshot",
    )


def _from_payload(payload: dict[str, Any]) -> BacktestTask:
    return BacktestTask(
        **{
            key: value
            for key, value in payload.items()
            if key in BacktestTask.__dataclass_fields__
        }
    )


def save_task(task: BacktestTask) -> None:
    task_lifecycle.upsert_job_record(
        kind=KIND,
        task=task,
        request_payload=task.request_payload,
        result_summary=task.result,
    )
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().save_task(KIND, task.id, task.to_dict())
        return
    with _lock:
        _tasks[task.id] = task


def get_task(task_id: str) -> BacktestTask:
    if task_store.redis_task_backend_enabled():
        payload = task_store.get_task_store().get_task(KIND, task_id)
        if payload is None:
            raise HTTPException(
                status_code=404, detail=f"Backtest task '{task_id}' not found"
            )
        task = _from_payload(payload)
        task.queue_position = task_store.get_task_store().queue_position(KIND, task_id)
        task.progress_events = task_store.get_task_store().list_events(KIND, task_id)
        return task
    with _lock:
        task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=404, detail=f"Backtest task '{task_id}' not found"
        )
    return task


def list_tasks() -> list[BacktestTask]:
    if task_store.redis_task_backend_enabled():
        return [
            _from_payload(payload)
            for payload in task_store.get_task_store().list_tasks(KIND)
        ]
    with _lock:
        return list(_tasks.values())


def _append(task: BacktestTask, progress: dict[str, Any]) -> None:
    task.latest_progress = progress
    task.progress_events.append(progress)
    save_task(task)
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().append_event(KIND, task.id, progress)


def run_backtest_task(task_id: str) -> None:
    task = get_task(task_id)
    task.status = "running"
    task.started_at = task.started_at or _utc_iso()
    _append(task, _event("running", "Backtest Snapshot is running."))
    try:
        result = backtests.run_snapshot(task.request_payload, run_id=task_id)
        task = get_task(task_id)
        task.status = "completed"
        task.finished_at = _utc_iso()
        task.result = {
            "run_id": task_id,
            "status": result.get("status"),
            "sample_size": result.get("sample_size"),
        }
        _append(task, _event("completed", "Backtest Snapshot completed."))
    except Exception as exc:
        task = get_task(task_id)
        task.status = "failed"
        task.finished_at = _utc_iso()
        task.error = str(exc)
        _append(task, _event("failed", "Backtest Snapshot failed."))
        raise


def create_backtest_task(
    *,
    request_payload: dict[str, Any],
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    task_id = f"bt_{uuid.uuid4().hex[:16]}"
    now = _utc_iso()
    task = BacktestTask(
        id=task_id,
        request_payload=request_payload,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        created_at=now,
    )
    if task_store.redis_task_backend_enabled():
        task_lifecycle.enqueue_task(
            kind=KIND,
            task_id=task_id,
            task=task,
            progress=_event("queued", "Backtest task queued."),
            save_task=save_task,
            queued_at=now,
        )
        return {"task_id": task_id, "run_id": task_id, "status": "queued"}
    with _lock:
        _tasks[task_id] = task
    save_task(task)
    threading.Thread(target=run_backtest_task, args=(task_id,), daemon=True).start()
    return {"task_id": task_id, "run_id": task_id, "status": "pending"}


def restore_persisted_backtest_tasks() -> None:
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().recover_processing(KIND)
