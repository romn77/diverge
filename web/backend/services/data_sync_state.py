from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from web.backend.runtime import task_lifecycle


@dataclass
class DataSyncTask:
    id: str
    sync_type: str
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
    cancel_requested_at: str | None = None
    canceled_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sync_type": self.sync_type,
            "request_payload": self.request_payload,
            "owner_user_id": self.owner_user_id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "latest_progress": self.latest_progress,
            "progress_events": self.progress_events,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "queue_position": self.queue_position,
            "cancel_requested_at": self.cancel_requested_at,
            "canceled_at": self.canceled_at,
        }


def timestamp() -> str:
    return task_lifecycle.event_timestamp()


def progress_event(message: str, **extra: Any) -> dict[str, Any]:
    return task_lifecycle.progress_event(message, **extra)


def recovered_progress(task: DataSyncTask, recovered_error: str) -> dict[str, Any]:
    return progress_event(
        f"{task.sync_type} sync failed: {recovered_error}",
        status="failed",
    )


def cancel_requested_progress(task: DataSyncTask) -> dict[str, Any]:
    return progress_event(
        (
            f"{task.sync_type} sync termination requested. "
            "Work will stop at the next safe step."
        ),
        status="running",
    )


def canceled_progress(task: DataSyncTask) -> dict[str, Any]:
    return progress_event(
        f"{task.sync_type} sync canceled by request.",
        status="canceled",
    )


def data_sync_task_from_payload(payload: dict[str, Any]) -> DataSyncTask:
    return DataSyncTask(
        id=str(payload["id"]),
        sync_type=str(payload["sync_type"]),
        request_payload=dict(payload.get("request_payload") or {}),
        owner_user_id=payload.get("owner_user_id"),
        tenant_id=payload.get("tenant_id"),
        status=str(payload.get("status") or "pending"),
        latest_progress=payload.get("latest_progress"),
        progress_events=list(payload.get("progress_events") or []),
        result=payload.get("result"),
        error=payload.get("error"),
        created_at=payload.get("created_at"),
        queued_at=payload.get("queued_at"),
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        queue_position=payload.get("queue_position"),
        cancel_requested_at=payload.get("cancel_requested_at"),
        canceled_at=payload.get("canceled_at"),
    )
