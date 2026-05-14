from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from web.backend.runtime import task_lifecycle, task_store

KIND = "journal_review"


def _utcnow() -> datetime:
    return task_lifecycle.utc_now()


def _utc_iso() -> str:
    return _utcnow().isoformat()


def _event(status: str, message: str) -> dict[str, Any]:
    return task_lifecycle.progress_event(
        message,
        status=status,
        stage_status={},
        agent_status={},
        current_agent="trade_journal_review",
    )


def _save_task(payload: dict[str, Any]) -> None:
    store = task_store.get_task_store()
    store.save_task(KIND, str(payload["id"]), payload)
    task_lifecycle.upsert_job_record(
        kind=KIND,
        task=payload,
        request_payload=payload.get("request_payload"),
        result_summary=payload.get("result"),
        heartbeat_at=payload.get("updated_at"),
        heartbeat_when_running=False,
    )


def create_auto_review_task(
    record: dict,
    review_types: list[str],
    *,
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
) -> str:
    task_id = f"journal_review_{uuid.uuid4().hex[:12]}"
    now = _utc_iso()
    progress = _event(
        "pending", "Trade journal AI review queued from trade submission."
    )
    payload = {
        "id": task_id,
        "kind": KIND,
        "owner_user_id": owner_user_id,
        "tenant_id": tenant_id,
        "request_payload": {
            "trigger": "trade_submit",
            "trade_id": record.get("trade_id"),
            "ticker": record.get("ticker"),
            "review_types": review_types,
        },
        "status": "pending",
        "latest_progress": progress,
        "progress_events": [progress],
        "result": None,
        "error": None,
        "created_at": now,
        "queued_at": now,
        "started_at": None,
        "finished_at": None,
        "updated_at": now,
    }
    store = task_store.get_task_store()
    _save_task(payload)
    store.append_event(KIND, task_id, progress)
    return task_id


def mark_running(task_id: str, message: str) -> None:
    task = get_task(task_id)
    if task is None:
        return
    now = _utc_iso()
    progress = _event("running", message)
    task["status"] = "running"
    task["started_at"] = task.get("started_at") or now
    task["updated_at"] = now
    task["latest_progress"] = progress
    task.setdefault("progress_events", []).append(progress)
    _save_task(task)
    task_store.get_task_store().append_event(KIND, task_id, progress)


def complete_task(task_id: str, result: dict[str, Any], message: str) -> None:
    task = get_task(task_id)
    if task is None:
        return
    now = _utc_iso()
    progress = _event("completed", message)
    task["status"] = "completed"
    task["result"] = result
    task["error"] = None
    task["finished_at"] = now
    task["updated_at"] = now
    task["latest_progress"] = progress
    task.setdefault("progress_events", []).append(progress)
    _save_task(task)
    task_store.get_task_store().append_event(KIND, task_id, progress)


def fail_task(task_id: str, error: str, message: str | None = None) -> None:
    task = get_task(task_id)
    if task is None:
        return
    now = _utc_iso()
    progress = _event("failed", message or error)
    task["status"] = "failed"
    task["error"] = error
    task["finished_at"] = now
    task["updated_at"] = now
    task["latest_progress"] = progress
    task.setdefault("progress_events", []).append(progress)
    _save_task(task)
    task_store.get_task_store().append_event(KIND, task_id, progress)


def get_task(task_id: str) -> dict[str, Any] | None:
    payload = task_store.get_task_store().get_task(KIND, task_id)
    if payload is None:
        return None
    events = task_store.get_task_store().list_events(KIND, task_id)
    if events:
        payload["progress_events"] = events
    return payload


def list_tasks() -> list[dict[str, Any]]:
    store = task_store.get_task_store()
    tasks: list[dict[str, Any]] = []
    for payload in store.list_tasks(KIND):
        task_id = str(payload.get("id"))
        events = store.list_events(KIND, task_id)
        if events:
            payload["progress_events"] = events
        tasks.append(payload)
    return sorted(
        tasks,
        key=lambda task: str(task.get("updated_at") or task.get("created_at") or ""),
        reverse=True,
    )
