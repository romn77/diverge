from __future__ import annotations

import json
import logging
import os
import socket
from datetime import datetime, timezone
from typing import Any


_MAX_VALUE_LENGTH = 500
_WORKER_ID: str | None = None


def current_worker_id() -> str:
    configured = os.environ.get("WORKER_ID")
    if configured and configured.strip():
        return configured.strip()

    global _WORKER_ID
    if _WORKER_ID is None:
        _WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
    return _WORKER_ID


def task_process_fields() -> dict[str, str]:
    return {"worker_id": current_worker_id()}


def _task_value(task: Any, field_name: str) -> Any:
    if task is None:
        return None
    if isinstance(task, dict):
        return task.get(field_name)
    return getattr(task, field_name, None)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return (
            value.astimezone(timezone.utc)
            if value.tzinfo
            else value.replace(tzinfo=timezone.utc)
        )
    candidate = str(value)
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def elapsed_seconds(started_at: Any, finished_at: Any | None = None) -> float | None:
    started = _parse_datetime(started_at)
    if started is None:
        return None
    finished = _parse_datetime(finished_at) or datetime.now(timezone.utc)
    return round(max((finished - started).total_seconds(), 0.0), 3)


def queue_wait_seconds(created_at: Any, started_at: Any | None = None) -> float | None:
    created = _parse_datetime(created_at)
    if created is None:
        return None
    started = _parse_datetime(started_at) or datetime.now(timezone.utc)
    return round(max((started - created).total_seconds(), 0.0), 3)


def processing_stage(progress: dict[str, Any] | None) -> str | None:
    if not isinstance(progress, dict):
        return None
    stage_status = progress.get("stage_status")
    if not isinstance(stage_status, dict):
        return None
    for stage, status in stage_status.items():
        if status == "processing":
            return str(stage)
    return None


def task_error_fields(error: Any) -> dict[str, str]:
    if error is None:
        return {}
    if isinstance(error, BaseException):
        error_type = error.__class__.__name__
        message = str(error)
    else:
        error_type = "Error"
        message = str(error)
    return {"error_type": error_type, "error": _truncate(message, limit=240)}


def log_task_event(
    logger: logging.Logger,
    event: str,
    *,
    kind: str,
    task_id: str,
    task: Any = None,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "event": event,
        "kind": kind,
        "task_id": task_id,
        "worker_id": fields.pop("worker_id", current_worker_id()),
    }
    for field_name in (
        "status",
        "owner_user_id",
        "tenant_id",
        "queue_position",
        "blocked_vendor",
        "blocked_until",
    ):
        value = _task_value(task, field_name)
        if value is not None:
            payload[field_name] = value

    started_at = _task_value(task, "started_at")
    finished_at = _task_value(task, "finished_at")
    if "elapsed_seconds" not in fields:
        fields["elapsed_seconds"] = elapsed_seconds(started_at, finished_at)
    if "queue_wait_seconds" not in fields:
        fields["queue_wait_seconds"] = queue_wait_seconds(
            _task_value(task, "created_at"),
            started_at,
        )

    payload.update({key: value for key, value in fields.items() if value is not None})
    logger.log(level, "task_event %s", _format_fields(payload))


def _format_fields(fields: dict[str, Any]) -> str:
    return " ".join(
        f"{key}={_encode_value(value)}"
        for key, value in sorted(fields.items())
        if value is not None
    )


def _encode_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    elif isinstance(value, set):
        value = json.dumps(sorted(str(item) for item in value), separators=(",", ":"))
    else:
        value = str(value)
    return json.dumps(_truncate(value), ensure_ascii=False)


def _truncate(value: str, *, limit: int = _MAX_VALUE_LENGTH) -> str:
    compact = value.replace("\n", "\\n").replace("\r", "\\r")
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."
