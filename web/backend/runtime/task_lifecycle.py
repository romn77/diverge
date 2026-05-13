from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    return utc_now().isoformat()


def event_timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


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
