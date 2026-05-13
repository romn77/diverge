from __future__ import annotations

from collections.abc import Callable, MutableMapping
from datetime import datetime, timezone
from typing import Any, Iterable

from web.backend import job_records
from web.backend.runtime import task_store
from web.backend.runtime.task_logging import current_worker_id


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    return utc_now().isoformat()


def event_timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def blocked_until_timestamp(blocked_until: str | None) -> float:
    if not blocked_until:
        return utc_now().timestamp() + 3600
    try:
        parsed = datetime.fromisoformat(blocked_until)
    except ValueError:
        return utc_now().timestamp() + 3600
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def progress_event(
    message: str,
    *,
    status: str | None = None,
    stage_status: dict[str, Any] | None = None,
    agent_status: dict[str, Any] | None = None,
    current_agent: Any | None = None,
    include_current_agent: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "timestamp": event_timestamp(),
        "message": message,
        **extra,
    }
    if status is not None:
        event["status"] = status
    if stage_status is not None:
        event["stage_status"] = stage_status
    if agent_status is not None:
        event["agent_status"] = agent_status
    if current_agent is not None or include_current_agent:
        event["current_agent"] = current_agent
    return event


def queued_progress(message: str, **extra: Any) -> dict[str, Any]:
    return progress_event(message, status="queued", **extra)


def apply_status_transition(
    task: Any,
    status: str,
    *,
    terminal_statuses: Iterable[str],
    error: str | None = None,
    now_iso: str | None = None,
) -> None:
    timestamp = now_iso or utc_iso()
    task.status = status
    if status == "running" and getattr(task, "started_at", None) is None:
        task.started_at = timestamp
    if status in set(terminal_statuses):
        task.finished_at = timestamp
    if error is not None:
        task.error = error


def append_progress_event(
    *,
    kind: str,
    task_id: str,
    progress: dict[str, Any],
    get_task: Callable[[str], Any],
    local_tasks: MutableMapping[str, Any],
    local_lock: Any,
    save_redis_task: Callable[[Any], None],
    save_local_task: Callable[[Any], None] | None = None,
) -> Any:
    if task_store.redis_task_backend_enabled():
        task = get_task(task_id)
        task.latest_progress = progress
        task.progress_events.append(progress)
        save_redis_task(task)
        task_store.get_task_store().append_event(kind, task_id, progress)
        return task

    with local_lock:
        task = local_tasks[task_id]
        task.latest_progress = progress
        task.progress_events.append(progress)
    if save_local_task is not None:
        save_local_task(task)
    return task


def apply_cancel_transition(
    *,
    kind: str,
    task_id: str,
    task: Any,
    now_iso: str,
    cancel_requested_progress: Callable[[Any], dict[str, Any]],
    canceled_progress: Callable[[Any], dict[str, Any]],
    save_task: Callable[[Any], None],
    clear_error: bool = False,
    clear_result: bool = False,
) -> str:
    if getattr(task, "status", None) == "running":
        if not getattr(task, "cancel_requested_at", None):
            task.cancel_requested_at = now_iso
            task.latest_progress = cancel_requested_progress(task)
            task.progress_events.append(task.latest_progress)
        save_task(task)
        if task_store.redis_task_backend_enabled():
            task_store.get_task_store().append_event(
                kind,
                task_id,
                task.latest_progress,
            )
        return "requested"

    task.status = "canceled"
    task.cancel_requested_at = getattr(task, "cancel_requested_at", None) or now_iso
    task.canceled_at = now_iso
    task.finished_at = now_iso
    if clear_error:
        task.error = None
    if clear_result:
        task.result = None
    task.latest_progress = canceled_progress(task)
    task.progress_events.append(task.latest_progress)
    save_task(task)
    if task_store.redis_task_backend_enabled():
        store = task_store.get_task_store()
        store.remove_task_refs(kind, task_id)
        store.append_event(kind, task_id, task.latest_progress)
    return "canceled"


def apply_quota_wait_transition(
    *,
    kind: str,
    task_id: str,
    task: Any,
    reason: str,
    vendor: str,
    blocked_until: str | None,
    build_progress: Callable[[Any], dict[str, Any]],
    save_task: Callable[[Any], None],
) -> Any:
    task.status = "waiting_for_quota"
    task.blocked_reason = reason
    task.blocked_vendor = vendor
    task.blocked_until = blocked_until
    waiting_progress = build_progress(task)
    task.latest_progress = waiting_progress
    task.progress_events.append(waiting_progress)
    save_task(task)
    if task_store.redis_task_backend_enabled():
        store = task_store.get_task_store()
        store.delay(kind, task_id, blocked_until_timestamp(blocked_until))
        store.append_event(kind, task_id, waiting_progress)
    return task


def _field(source: Any, name: str) -> Any:
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


def upsert_job_record(
    *,
    kind: str,
    task: Any,
    task_id: str | None = None,
    status: str | None = None,
    request_payload: dict[str, Any] | None = None,
    result_summary: dict[str, Any] | None = None,
    error: str | None = None,
    heartbeat_at: str | None = None,
    worker_id: str | None = None,
    heartbeat_when_running: bool = True,
) -> None:
    resolved_status = status or str(_field(task, "status"))
    resolved_heartbeat = heartbeat_at
    resolved_worker_id = worker_id
    if heartbeat_when_running and resolved_status == "running":
        resolved_heartbeat = resolved_heartbeat or utc_iso()
        resolved_worker_id = resolved_worker_id or current_worker_id()

    job_records.upsert_job_record(
        kind=kind,
        task_id=task_id or str(_field(task, "id")),
        status=resolved_status,
        request_payload=request_payload
        if request_payload is not None
        else _field(task, "request_payload"),
        result_summary=result_summary
        if result_summary is not None
        else _field(task, "result"),
        error=error if error is not None else _field(task, "error"),
        owner_user_id=_field(task, "owner_user_id"),
        tenant_id=_field(task, "tenant_id"),
        created_at=_field(task, "created_at"),
        queued_at=_field(task, "queued_at"),
        started_at=_field(task, "started_at"),
        finished_at=_field(task, "finished_at"),
        heartbeat_at=resolved_heartbeat,
        worker_id=resolved_worker_id,
    )
