from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from diverge.common.json_io import write_json_atomic
from diverge.market_brief.builder import MarketBriefBuildRequest, build_market_brief
from web.backend import app_config, auth, report_metadata
from web.backend.runtime import task_lifecycle, task_store
from web.backend.runtime.task_logging import log_task_event, task_error_fields
from web.backend.services import market_briefs as market_brief_service

logger = logging.getLogger(__name__)
GENERIC_MARKET_BRIEF_TASK_ERROR = (
    "Market brief task failed. Check backend logs for details."
)


@dataclass
class MarketBriefTask:
    id: str
    request_payload: dict[str, Any]
    owner_user_id: str | None = None
    tenant_id: str | None = None
    status: str = "pending"
    latest_progress: dict[str, Any] | None = None
    progress_events: list[dict[str, Any]] = field(default_factory=list)
    report_id: str | None = None
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
            "request_payload": self.request_payload,
            "owner_user_id": self.owner_user_id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "latest_progress": self.latest_progress,
            "progress_events": self.progress_events,
            "report_id": self.report_id,
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


market_brief_tasks: dict[str, MarketBriefTask] = {}
market_brief_tasks_lock = threading.Lock()


def _utc_iso() -> str:
    return task_lifecycle.utc_iso()


def _state_dir() -> Path:
    return app_config.SCREENER_STATE_DIR / "market_brief_tasks"


def _task_path(task_id: str) -> Path:
    return _state_dir() / f"{task_id}.json"


def _progress(
    message: str,
    *,
    status: str,
    stage: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return task_lifecycle.progress_event(
        message,
        status=status,
        stage_status={},
        agent_status={},
        current_agent=stage,
        include_current_agent=True,
        **extra,
    )


def _save_task(task: MarketBriefTask) -> None:
    task_lifecycle.upsert_job_record(
        kind="market_brief",
        task=task,
        request_payload=task.request_payload,
        result_summary=task.result,
    )
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().save_task("market_brief", task.id, task.to_dict())
        return
    with market_brief_tasks_lock:
        market_brief_tasks[task.id] = task
    if task.status in app_config.TERMINAL_TASK_STATUSES:
        delete_market_brief_task_snapshot(task.id)
        return
    write_json_atomic(_task_path(task.id), task.to_dict())


def persist_market_brief_task_snapshot(task_id: str) -> None:
    _save_task(get_market_brief_task(task_id))


def delete_market_brief_task_snapshot(task_id: str) -> None:
    snapshot_path = _task_path(task_id)
    with suppress(FileNotFoundError):
        snapshot_path.unlink()
    for directory in (snapshot_path.parent, snapshot_path.parent.parent):
        with suppress(OSError):
            directory.rmdir()


def market_brief_task_from_payload(payload: dict[str, Any]) -> MarketBriefTask:
    status = str(payload.get("status") or "pending")
    if task_store.redis_task_backend_enabled() and status == "pending":
        status = "queued"
    return MarketBriefTask(
        id=str(payload["id"]),
        request_payload=dict(payload.get("request_payload") or {}),
        owner_user_id=(
            str(payload["owner_user_id"]).strip()
            if payload.get("owner_user_id")
            else None
        ),
        tenant_id=(
            str(payload["tenant_id"]).strip() if payload.get("tenant_id") else None
        ),
        status=status,
        latest_progress=payload.get("latest_progress"),
        progress_events=list(payload.get("progress_events") or []),
        report_id=payload.get("report_id"),
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


def get_market_brief_task(task_id: str) -> MarketBriefTask:
    if task_store.redis_task_backend_enabled():
        store = task_store.get_task_store()
        payload = store.get_task("market_brief", task_id)
        if payload is None:
            raise HTTPException(
                status_code=404, detail=f"Market brief task '{task_id}' not found"
            )
        task = market_brief_task_from_payload(payload)
        task.queue_position = store.queue_position("market_brief", task.id)
        task.progress_events = store.list_events("market_brief", task.id)
        return task

    with market_brief_tasks_lock:
        task = market_brief_tasks.get(task_id)
    if task is not None:
        return task
    path = _task_path(task_id)
    if path.is_file():
        return market_brief_task_from_payload(
            json.loads(path.read_text(encoding="utf-8"))
        )
    raise HTTPException(
        status_code=404, detail=f"Market brief task '{task_id}' not found"
    )


def list_market_brief_tasks() -> list[MarketBriefTask]:
    if task_store.redis_task_backend_enabled():
        store = task_store.get_task_store()
        tasks = []
        for payload in store.list_tasks("market_brief"):
            task = market_brief_task_from_payload(payload)
            task.queue_position = store.queue_position("market_brief", task.id)
            tasks.append(task)
        return sorted(tasks, key=lambda task: task.created_at or "", reverse=True)

    with market_brief_tasks_lock:
        tasks = list(market_brief_tasks.values())
    for path in sorted(_state_dir().glob("*.json")) if _state_dir().is_dir() else []:
        if any(task.id == path.stem for task in tasks):
            continue
        try:
            tasks.append(
                market_brief_task_from_payload(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            )
        except Exception:
            continue
    return sorted(tasks, key=lambda task: task.created_at or "", reverse=True)


def get_market_brief_progress_events(
    task_id: str, start: int = 0
) -> list[dict[str, Any]]:
    if task_store.redis_task_backend_enabled():
        return task_store.get_task_store().list_events("market_brief", task_id, start)
    with market_brief_tasks_lock:
        task = market_brief_tasks.get(task_id)
        if task is None:
            return []
        return task.progress_events[start:]


def _append_progress(
    task_id: str,
    message: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    **extra: Any,
) -> None:
    task = get_market_brief_task(task_id)
    progress = _progress(
        message,
        status=status or task.status,
        stage=stage,
        **extra,
    )
    updated_task = task_lifecycle.append_progress_event(
        kind="market_brief",
        task_id=task_id,
        progress=progress,
        get_task=get_market_brief_task,
        local_tasks=market_brief_tasks,
        local_lock=market_brief_tasks_lock,
        save_redis_task=_save_task,
        save_local_task=_save_task,
    )
    log_task_event(
        logger,
        "task_progress",
        kind="market_brief",
        task_id=task_id,
        task=updated_task,
        message=message,
        stage=stage,
    )


def check_market_brief_task_canceled(task_id: str) -> None:
    if get_market_brief_task(task_id).cancel_requested_at:
        raise task_store.TaskCanceled("Market brief task canceled by request.")


def _failure_progress(task: MarketBriefTask) -> dict[str, Any]:
    return _progress(
        task.error or GENERIC_MARKET_BRIEF_TASK_ERROR,
        status="failed",
        stage="failed",
    )


def _cancel_requested_progress(task: MarketBriefTask) -> dict[str, Any]:
    return _progress(
        "Market brief cancellation requested.",
        status=task.status,
        stage="cancel",
    )


def _canceled_progress(_: MarketBriefTask) -> dict[str, Any]:
    return _progress(
        "Market brief task canceled.",
        status="canceled",
        stage="canceled",
    )


def _mark_market_brief_task_canceled(task_id: str) -> None:
    task = get_market_brief_task(task_id)
    task_lifecycle.apply_canceled_completion_transition(
        kind="market_brief",
        task_id=task_id,
        task=task,
        canceled_progress=_canceled_progress,
        save_task=_save_task,
        clear_result=True,
    )
    log_task_event(
        logger,
        "task_canceled",
        kind="market_brief",
        task_id=task_id,
        task=task,
    )


def _fail_market_brief_task(task_id: str, error: str) -> None:
    task = get_market_brief_task(task_id)
    task_lifecycle.apply_failure_transition(
        kind="market_brief",
        task=task,
        error=error,
        build_progress=_failure_progress,
        save_task=_save_task,
        append_redis_event=True,
    )
    log_task_event(
        logger,
        "task_failed",
        kind="market_brief",
        task_id=task_id,
        task=task,
        **task_error_fields(error),
    )


def _report_visibility(payload: dict[str, Any]) -> str:
    value = str(payload.get("report_visibility") or "").strip().lower()
    if value in report_metadata.VALID_REPORT_VISIBILITIES:
        return value
    return report_metadata.REPORT_VISIBILITY_WORKSPACE


def run_market_brief_task(task_id: str) -> None:
    task = get_market_brief_task(task_id)
    task.status = "running"
    task.started_at = _utc_iso()
    _save_task(task)
    log_task_event(
        logger,
        "task_started",
        kind="market_brief",
        task_id=task_id,
        task=task,
    )
    try:
        check_market_brief_task_canceled(task_id)
        _append_progress(task_id, "Collecting market calendar.", stage="calendar")
        payload = dict(task.request_payload)
        build_request = MarketBriefBuildRequest(
            markets=payload.get("markets"),
            output_language=str(payload.get("output_language") or "zh-CN"),
            trigger=str(payload.get("trigger") or "manual"),
            slot=payload.get("slot"),
            automation_key=payload.get("automation_key"),
            scheduler_provider=payload.get("scheduler_provider"),
        )
        _append_progress(
            task_id, "Collecting market data and sources.", stage="sources"
        )
        brief = build_market_brief(build_request)
        check_market_brief_task_canceled(task_id)
        _append_progress(task_id, "Saving market brief report.", stage="storage")
        result = market_brief_service.publish_market_brief(
            brief,
            owner_user_id=task.owner_user_id,
            tenant_id=task.tenant_id,
            report_visibility=_report_visibility(payload),
        )
        check_market_brief_task_canceled(task_id)

        task = get_market_brief_task(task_id)
        task.status = "completed"
        task.finished_at = _utc_iso()
        task.report_id = str(result["report_id"])
        task.result = result
        task.latest_progress = _progress(
            "Market brief completed.",
            status="completed",
            stage="completed",
            report_id=task.report_id,
        )
        task.progress_events.append(task.latest_progress)
        _save_task(task)
        if task_store.redis_task_backend_enabled():
            task_store.get_task_store().append_event(
                "market_brief",
                task_id,
                task.latest_progress,
            )
        log_task_event(
            logger,
            "task_completed",
            kind="market_brief",
            task_id=task_id,
            task=task,
            report_id=task.report_id,
        )
    except task_store.TaskCanceled:
        _mark_market_brief_task_canceled(task_id)
    except Exception:
        logger.exception("market brief task failed task_id=%s", task_id)
        _fail_market_brief_task(task_id, GENERIC_MARKET_BRIEF_TASK_ERROR)


def start_market_brief_task_thread(task_id: str) -> threading.Thread:
    thread = threading.Thread(
        target=run_market_brief_task, args=(task_id,), daemon=True
    )
    thread.start()
    return thread


def create_market_brief_task(
    *,
    request_payload: dict[str, Any],
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, str]:
    resolved_task_id = task_id or uuid.uuid4().hex
    now_iso = _utc_iso()
    task = MarketBriefTask(
        id=resolved_task_id,
        request_payload=dict(request_payload),
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        created_at=now_iso,
    )
    if task_store.redis_task_backend_enabled():
        task_lifecycle.enqueue_task(
            kind="market_brief",
            task_id=resolved_task_id,
            task=task,
            progress=task_lifecycle.queued_progress(
                "Market brief task queued.",
                stage_status={},
                agent_status={},
                include_current_agent=True,
            ),
            save_task=_save_task,
            queued_at=now_iso,
        )
        log_task_event(
            logger,
            "task_queued",
            kind="market_brief",
            task_id=resolved_task_id,
            task=task,
            markets=",".join(
                str(market) for market in request_payload.get("markets", [])
            ),
        )
        return {"task_id": resolved_task_id, "status": "queued"}

    _save_task(task)
    start_market_brief_task_thread(resolved_task_id)
    log_task_event(
        logger,
        "task_submitted",
        kind="market_brief",
        task_id=resolved_task_id,
        task=task,
    )
    return {"task_id": resolved_task_id, "status": task.status}


def restore_persisted_market_brief_tasks() -> None:
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().recover_processing("market_brief")
        for task in list_market_brief_tasks():
            if task.status == "running":
                task_lifecycle.apply_recovered_failure_transition(
                    kind="market_brief",
                    task=task,
                    error=app_config.RECOVERED_TASK_ERROR,
                    build_progress=_failure_progress,
                    save_task=_save_task,
                    append_redis_event=True,
                    ack_redis_processing=True,
                )
        return

    if not _state_dir().is_dir():
        return
    for path in sorted(_state_dir().glob("*.json")):
        try:
            task = market_brief_task_from_payload(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except Exception:
            continue
        if task.status in app_config.TERMINAL_TASK_STATUSES:
            delete_market_brief_task_snapshot(task.id)
            continue
        task_lifecycle.apply_recovered_failure_transition(
            kind="market_brief",
            task=task,
            error=app_config.RECOVERED_TASK_ERROR,
            build_progress=_failure_progress,
            replace_progress_events=True,
        )
        with market_brief_tasks_lock:
            market_brief_tasks[task.id] = task
        delete_market_brief_task_snapshot(task.id)


def cancel_market_brief_task(task_id: str) -> None:
    task = get_market_brief_task(task_id)
    if task.status in task_store.TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Finished market brief tasks cannot be canceled.",
        )
    transition = task_lifecycle.apply_cancel_transition(
        kind="market_brief",
        task_id=task_id,
        task=task,
        now_iso=_utc_iso(),
        cancel_requested_progress=_cancel_requested_progress,
        canceled_progress=_canceled_progress,
        save_task=_save_task,
        clear_error=True,
        clear_result=True,
    )
    if transition == "requested":
        log_task_event(
            logger,
            "task_cancel_requested",
            kind="market_brief",
            task_id=task_id,
            task=task,
        )
        return
    log_task_event(
        logger,
        "task_canceled",
        kind="market_brief",
        task_id=task_id,
        task=task,
    )


def resolve_automation_owner() -> tuple[str | None, str | None]:
    if not auth.auth_enabled():
        return None, None
    configured_owner = os.environ.get("MARKET_BRIEF_OWNER_USER_ID", "").strip()
    try:
        with auth.db_session() as db:
            if configured_owner:
                owner = auth.get_user_by_id(db, configured_owner)
                return owner.id, owner.tenant_id
            settings = auth.get_auth_settings()
            if settings.bootstrap_admin_email:
                owner = auth.get_user_by_email(db, settings.bootstrap_admin_email)
                if owner is not None:
                    return owner.id, owner.tenant_id
            owner = db.scalar(
                select(auth.User)
                .where(
                    auth.User.role == auth.UserRole.ADMIN.value,
                    auth.User.status == auth.UserStatus.ACTIVE.value,
                )
                .order_by(auth.User.created_at.asc(), auth.User.email.asc())
            )
            if owner is not None:
                return owner.id, owner.tenant_id
    except Exception:
        logger.warning(
            "Unable to resolve market brief automation owner.", exc_info=True
        )
    return None, None
