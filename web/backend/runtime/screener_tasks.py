from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from diverge.common.json_io import write_json_atomic
from diverge.dataflows import vendor_usage
from diverge.screener.pipeline import run_screen
from diverge.screener.schema import ScreenRunConfig
from web.backend import app_config, audit, auth, storage
from web.backend.runtime import task_lifecycle, task_store
from web.backend.runtime.task_logging import (
    log_task_event,
    processing_stage,
    task_error_fields,
)
from web.backend.services import screeners as screener_service

SCREENER_STAGES = ["Features", "Filters", "Ranking", "Export"]
GENERIC_SCREENER_TASK_ERROR = "Screener task failed. Check backend logs for details."
logger = logging.getLogger(__name__)


@dataclass
class ScreenerTask:
    id: str
    request_payload: dict
    config_payload: dict
    owner_user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    status: str = "pending"
    latest_progress: Optional[dict] = None
    progress_events: list[dict] = field(default_factory=list)
    run_id: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    queued_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    queue_position: Optional[int] = None
    blocked_reason: Optional[str] = None
    blocked_vendor: Optional[str] = None
    blocked_until: Optional[str] = None
    cancel_requested_at: Optional[str] = None
    canceled_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "request_payload": self.request_payload,
            "config_payload": self.config_payload,
            "owner_user_id": self.owner_user_id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "latest_progress": self.latest_progress,
            "progress_events": self.progress_events,
            "run_id": self.run_id,
            "error": self.error,
            "created_at": self.created_at,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "queue_position": self.queue_position,
            "blocked_reason": self.blocked_reason,
            "blocked_vendor": self.blocked_vendor,
            "blocked_until": self.blocked_until,
            "cancel_requested_at": self.cancel_requested_at,
            "canceled_at": self.canceled_at,
        }


screener_tasks: dict[str, ScreenerTask] = {}
screener_tasks_lock = threading.Lock()


def count_active_tasks() -> int:
    if task_store.redis_task_backend_enabled():
        return task_store.get_task_store().count_active("screener")
    with screener_tasks_lock:
        return sum(
            1
            for task in screener_tasks.values()
            if task.status in task_store.ACTIVE_STATUSES
        )


def _utc_iso() -> str:
    return task_lifecycle.utc_iso()


def _record_screener_pruned_audit_event(task: ScreenerTask, run_dir: Path) -> None:
    if task.owner_user_id is None or task.tenant_id is None or not auth.auth_enabled():
        return
    run_meta_path = run_dir / "run_meta.json"
    if not run_meta_path.is_file():
        return
    try:
        run_meta = json.loads(run_meta_path.read_text(encoding="utf-8"))
    except Exception:
        return
    pruned_count = int(run_meta.get("pruned_symbol_count") or 0)
    if pruned_count <= 0:
        return
    artifact_paths = run_meta.get("artifact_paths") or {}
    try:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=task.tenant_id,
                actor_user_id=task.owner_user_id,
                action="screener.universe.pruned",
                resource_type="screener_task",
                resource_id=task.id,
                metadata={
                    "run_id": run_dir.name,
                    "as_of_date": run_meta.get("as_of_date"),
                    "pruned_symbol_count": pruned_count,
                    "filtered_count_by_reason": run_meta.get(
                        "filtered_count_by_reason"
                    ),
                    "pruned_symbols_path": artifact_paths.get("pruned_symbols"),
                },
            )
    except Exception:
        return


def active_screener_tasks_dir() -> Path:
    return app_config.SCREENER_TASKS_DIR / app_config.ACTIVE_TASKS_DIRNAME


def screener_task_snapshot_path(task_id: str) -> Path:
    return active_screener_tasks_dir() / task_id / "task.json"


def delete_screener_task_snapshot(task_id: str) -> None:
    snapshot_path = screener_task_snapshot_path(task_id)
    with suppress(FileNotFoundError):
        snapshot_path.unlink()

    for directory in (
        snapshot_path.parent,
        active_screener_tasks_dir(),
        active_screener_tasks_dir().parent,
    ):
        with suppress(OSError):
            directory.rmdir()


def persist_screener_task_snapshot(task_id: str) -> None:
    task = get_screener_task(task_id)
    _upsert_screener_job_record(task)
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().save_task("screener", task_id, task.to_dict())
        return
    snapshot = task.to_dict()
    if snapshot["status"] in app_config.TERMINAL_TASK_STATUSES:
        delete_screener_task_snapshot(task_id)
        return
    write_json_atomic(screener_task_snapshot_path(task_id), snapshot)


def get_screener_task(task_id: str) -> ScreenerTask:
    if task_store.redis_task_backend_enabled():
        payload = task_store.get_task_store().get_task("screener", task_id)
        if payload is None:
            raise HTTPException(
                status_code=404, detail=f"Screener task '{task_id}' not found"
            )
        task = screener_task_from_payload(payload)
        task.queue_position = task_store.get_task_store().queue_position(
            "screener", task_id
        )
        task.progress_events = task_store.get_task_store().list_events(
            "screener", task_id
        )
        return task
    with screener_tasks_lock:
        task = screener_tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=404, detail=f"Screener task '{task_id}' not found"
        )
    return task


def delete_failed_screener_task(task_id: str) -> None:
    task = get_screener_task(task_id)
    if task.status != "failed":
        raise HTTPException(
            status_code=409,
            detail="Only failed screener tasks can be deleted.",
        )

    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().delete_task("screener", task_id)
        return

    with screener_tasks_lock:
        screener_tasks.pop(task_id, None)
    delete_screener_task_snapshot(task_id)


def append_screener_progress(task_id: str, progress: dict) -> None:
    task = task_lifecycle.append_progress_event(
        kind="screener",
        task_id=task_id,
        progress=progress,
        get_task=get_screener_task,
        local_tasks=screener_tasks,
        local_lock=screener_tasks_lock,
        save_redis_task=save_screener_task,
        save_local_task=lambda task: persist_screener_task_snapshot(task.id),
    )
    log_task_event(
        logger,
        "task_progress",
        kind="screener",
        task_id=task_id,
        task=task,
        status=progress.get("status"),
        stage=processing_stage(progress),
        current_agent=progress.get("current_agent"),
        message=progress.get("message"),
    )


def set_screener_task_status(
    task_id: str, status: str, error: Optional[str] = None
) -> None:
    if task_store.redis_task_backend_enabled():
        task = get_screener_task(task_id)
        task_lifecycle.apply_status_transition(
            task,
            status,
            terminal_statuses=task_store.TERMINAL_STATUSES,
            error=error,
        )
        _upsert_screener_job_record(task)
        task_store.get_task_store().save_task("screener", task_id, task.to_dict())
        return
    with screener_tasks_lock:
        task = screener_tasks[task_id]
        task_lifecycle.apply_status_transition(
            task,
            status,
            terminal_statuses=task_store.TERMINAL_STATUSES,
            error=error,
        )
    persist_screener_task_snapshot(task_id)


def build_screener_progress(
    *,
    status: str,
    stage: str,
    current: int,
    total: int,
    symbol: str | None = None,
    message: str | None = None,
) -> dict:
    stage = normalize_screener_stage(stage)
    if stage in SCREENER_STAGES:
        stage_status = {
            key: (
                "processing"
                if key == stage
                else "completed"
                if SCREENER_STAGES.index(key) < SCREENER_STAGES.index(stage)
                else "not_started"
            )
            for key in SCREENER_STAGES
        }
    else:
        stage_status = {key: "not_started" for key in SCREENER_STAGES}
    if status == "completed":
        stage_status = {key: "completed" for key in SCREENER_STAGES}
    if status in {"queued", "canceled"}:
        stage_status = {key: "not_started" for key in SCREENER_STAGES}
    if status == "failed" and stage not in SCREENER_STAGES:
        stage_status = {key: "not_started" for key in SCREENER_STAGES}

    detail = message or f"{stage} {current}/{total}"
    if symbol:
        detail = f"{detail} {symbol}"

    return {
        "timestamp": task_lifecycle.event_timestamp(),
        "status": status,
        "stage_status": stage_status,
        "agent_status": {},
        "current_agent": symbol,
        "message": detail,
    }


def normalize_screener_stage(stage: str) -> str:
    normalized = str(stage or "").strip().lower()
    if normalized == "features":
        return "Features"
    if normalized == "filters":
        return "Filters"
    if normalized == "ranking":
        return "Ranking"
    if normalized == "export":
        return "Export"
    return str(stage or "")


def build_screener_failure_progress(task: ScreenerTask, error: str) -> dict:
    latest_progress = task.latest_progress or {}
    latest_stage_status = latest_progress.get("stage_status") or {}
    stage_status = {
        key: (
            "not_started"
            if latest_stage_status.get(key) == "processing"
            else latest_stage_status.get(key, "not_started")
        )
        for key in SCREENER_STAGES
    }

    return {
        "timestamp": task_lifecycle.event_timestamp(),
        "status": "failed",
        "stage_status": stage_status,
        "agent_status": latest_progress.get("agent_status") or {},
        "current_agent": latest_progress.get("current_agent"),
        "message": f"System: {error}",
    }


def build_screener_canceled_progress(
    task: ScreenerTask, message: str | None = None
) -> dict:
    latest_progress = task.latest_progress or {}
    latest_stage_status = latest_progress.get("stage_status") or {}
    stage_status = {
        key: (
            "not_started"
            if latest_stage_status.get(key) == "processing"
            else latest_stage_status.get(key, "not_started")
        )
        for key in SCREENER_STAGES
    }
    return {
        "timestamp": task_lifecycle.event_timestamp(),
        "status": "canceled",
        "stage_status": stage_status,
        "agent_status": latest_progress.get("agent_status") or {},
        "current_agent": latest_progress.get("current_agent"),
        "message": message or "Screener task canceled by request.",
    }


def build_screener_cancel_requested_progress(task: ScreenerTask) -> dict:
    latest_progress = task.latest_progress or {}
    return {
        "timestamp": task_lifecycle.event_timestamp(),
        "status": "running",
        "stage_status": latest_progress.get("stage_status")
        or {key: "not_started" for key in SCREENER_STAGES},
        "agent_status": latest_progress.get("agent_status") or {},
        "current_agent": latest_progress.get("current_agent"),
        "message": "Termination requested. Work will stop at the next safe step.",
    }


def check_screener_task_canceled(task_id: str) -> None:
    if get_screener_task(task_id).cancel_requested_at:
        raise task_store.TaskCanceled("Screener task canceled by request.")


def _mark_screener_task_canceled(task_id: str) -> None:
    current_task = get_screener_task(task_id)
    task_lifecycle.apply_canceled_completion_transition(
        kind="screener",
        task_id=task_id,
        task=current_task,
        canceled_progress=build_screener_canceled_progress,
        save_task=save_screener_task,
    )
    log_task_event(
        logger,
        "task_canceled",
        kind="screener",
        task_id=task_id,
        task=current_task,
    )
    persist_screener_task_snapshot(task_id)


def format_screener_http_error(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("message")
        if message:
            return str(message)
        code = detail.get("code")
        if code:
            return str(code)
    return str(detail)


def build_screener_waiting_for_quota_progress(
    task: ScreenerTask,
    exc: vendor_usage.QuotaWaitRequired,
) -> dict:
    latest_progress = task.latest_progress or {}
    return {
        "timestamp": task_lifecycle.event_timestamp(),
        "status": "waiting_for_quota",
        "stage_status": latest_progress.get("stage_status")
        or {key: "not_started" for key in SCREENER_STAGES},
        "agent_status": latest_progress.get("agent_status") or {},
        "current_agent": latest_progress.get("current_agent"),
        "message": (
            f"Waiting for {exc.vendor} quota"
            + (f" until {exc.blocked_until}" if exc.blocked_until else "")
            + "."
        ),
    }


def wait_screener_for_quota(task_id: str, exc: vendor_usage.QuotaWaitRequired) -> None:
    current_task = get_screener_task(task_id)
    task_lifecycle.apply_quota_wait_transition(
        kind="screener",
        task_id=task_id,
        task=current_task,
        reason=exc.reason,
        vendor=exc.vendor,
        blocked_until=exc.blocked_until,
        build_progress=lambda task: build_screener_waiting_for_quota_progress(
            task, exc
        ),
        save_task=save_screener_task,
    )
    log_task_event(
        logger,
        "task_waiting_for_quota",
        kind="screener",
        task_id=task_id,
        task=current_task,
        blocked_reason=exc.reason,
        blocked_vendor=exc.vendor,
        blocked_until=exc.blocked_until,
    )


def restore_persisted_screener_tasks() -> None:
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().recover_processing("screener")
        for task in list_screener_tasks():
            if task.status == "running":
                task_lifecycle.apply_recovered_failure_transition(
                    kind="screener",
                    task=task,
                    error=app_config.RECOVERED_TASK_ERROR,
                    build_progress=lambda task: build_screener_failure_progress(
                        task,
                        app_config.RECOVERED_TASK_ERROR,
                    ),
                    save_task=save_screener_task,
                    append_redis_event=True,
                    ack_redis_processing=True,
                )
        return
    active_dir = active_screener_tasks_dir()
    if not active_dir.is_dir():
        return

    for snapshot_path in sorted(active_dir.glob("*/task.json")):
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            task = screener_task_from_payload(payload)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            delete_screener_task_snapshot(snapshot_path.parent.name)
            continue

        if task.status in app_config.TERMINAL_TASK_STATUSES:
            delete_screener_task_snapshot(task.id)
            continue

        task_lifecycle.apply_recovered_failure_transition(
            kind="screener",
            task=task,
            error=app_config.RECOVERED_TASK_ERROR,
            build_progress=lambda task: build_screener_failure_progress(
                task,
                app_config.RECOVERED_TASK_ERROR,
            ),
            replace_progress_events=True,
        )

        with screener_tasks_lock:
            screener_tasks[task.id] = task

        delete_screener_task_snapshot(task.id)


def start_screener_task_thread(task_id: str) -> threading.Thread:
    thread = threading.Thread(target=run_screener_task, args=(task_id,), daemon=True)
    thread.start()
    return thread


def _fail_screener_task(task_id: str, error: str) -> None:
    current_task = get_screener_task(task_id)
    task_lifecycle.apply_failure_transition(
        kind="screener",
        task=current_task,
        error=error,
        build_progress=lambda task: build_screener_failure_progress(task, error),
        save_task=save_screener_task,
        append_redis_event=True,
    )
    log_task_event(
        logger,
        "task_failed",
        kind="screener",
        task_id=task_id,
        task=current_task,
        **task_error_fields(error),
    )
    current_task = get_screener_task(task_id)
    screener_service.persist_screener_run(
        current_task,
        error_summary=error,
        source_run_id=current_task.id,
    )
    persist_screener_task_snapshot(task_id)


def run_screener_task(task_id: str) -> None:
    get_screener_task(task_id)
    set_screener_task_status(task_id, "running")
    log_task_event(
        logger,
        "task_started",
        kind="screener",
        task_id=task_id,
        task=get_screener_task(task_id),
    )

    try:
        check_screener_task_canceled(task_id)

        def progress_callback(
            stage: str,
            current: int,
            total: int,
            symbol: str | None = None,
            *,
            status: str | None = None,
            detail: str | None = None,
        ) -> None:
            normalized_stage = normalize_screener_stage(stage)
            if normalized_stage not in SCREENER_STAGES:
                return
            message = f"{normalized_stage} {current}/{total}"
            if symbol:
                message = f"{message} {symbol}"
            if status:
                message = f"{message} [{status}]"
            if detail:
                message = f"{message} {detail}"
            progress = build_screener_progress(
                status="running",
                stage=normalized_stage,
                current=current,
                total=total,
                symbol=symbol,
                message=message,
            )
            append_screener_progress(task_id, progress)
            check_screener_task_canceled(task_id)

        current_task = get_screener_task(task_id)
        config = ScreenRunConfig(**current_task.config_payload)
        preflight_progress = build_screener_progress(
            status="running",
            stage="Features",
            current=0,
            total=1,
            message="Checking cached screener data.",
        )
        append_screener_progress(task_id, preflight_progress)
        check_screener_task_canceled(task_id)
        screener_service.ensure_screener_cache_coverage(config)
        check_screener_task_canceled(task_id)
        with vendor_usage.data_source_usage_context("screener"):
            result = run_screen(
                config,
                progress_callback=progress_callback,
            )
        check_screener_task_canceled(task_id)
        _record_screener_pruned_audit_event(current_task, Path(result.run_dir))
        if storage_backend_is_remote():
            check_screener_task_canceled(task_id)
            storage.upload_directory(
                Path(result.run_dir), f"screener/runs/{Path(result.run_dir).name}"
            )

        check_screener_task_canceled(task_id)
        current_task = get_screener_task(task_id)
        candidate = screener_service.run_screener(current_task, result)
        check_screener_task_canceled(task_id)
        screener_service.persist_screener_run(current_task, candidate)

        current_task = get_screener_task(task_id)
        current_task.status = "completed"
        current_task.finished_at = _utc_iso()
        current_task.run_id = Path(result.run_dir).name
        current_task.latest_progress = build_screener_progress(
            status="completed",
            stage="Export",
            current=1,
            total=1,
            message=f"Export 1/1 {current_task.run_id}",
        )
        current_task.progress_events.append(current_task.latest_progress)
        save_screener_task(current_task)
        if task_store.redis_task_backend_enabled():
            task_store.get_task_store().append_event(
                "screener",
                task_id,
                current_task.latest_progress,
            )
        persist_screener_task_snapshot(task_id)
        log_task_event(
            logger,
            "task_completed",
            kind="screener",
            task_id=task_id,
            task=current_task,
            run_id=current_task.run_id,
        )
    except vendor_usage.QuotaWaitRequired as exc:
        if task_store.redis_task_backend_enabled():
            wait_screener_for_quota(task_id, exc)
            return
        _fail_screener_task(task_id, str(exc))
    except HTTPException as exc:
        _fail_screener_task(task_id, format_screener_http_error(exc))
    except task_store.TaskCanceled:
        _mark_screener_task_canceled(task_id)
    except Exception:  # pragma: no cover
        logger.exception("screener task failed task_id=%s", task_id)
        _fail_screener_task(task_id, GENERIC_SCREENER_TASK_ERROR)


def create_screener_task(
    *,
    request_payload: dict,
    config_payload: dict,
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
) -> dict:
    task_id = uuid.uuid4().hex
    now_iso = _utc_iso()
    task = ScreenerTask(
        id=task_id,
        request_payload=request_payload,
        config_payload=config_payload,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        created_at=now_iso,
    )

    if task_store.redis_task_backend_enabled():
        task_lifecycle.enqueue_task(
            kind="screener",
            task_id=task_id,
            task=task,
            progress=task_lifecycle.queued_progress(
                "Screener task queued.",
                stage_status={key: "not_started" for key in SCREENER_STAGES},
                agent_status={},
                include_current_agent=True,
            ),
            save_task=save_screener_task,
            queued_at=now_iso,
        )
        log_task_event(
            logger,
            "task_queued",
            kind="screener",
            task_id=task_id,
            task=task,
            markets=",".join(
                str(market) for market in request_payload.get("markets", [])
            ),
            as_of_date=request_payload.get("as_of_date"),
        )
        return {"task_id": task_id, "status": "queued"}

    with screener_tasks_lock:
        screener_tasks[task_id] = task
    persist_screener_task_snapshot(task_id)
    start_screener_task_thread(task_id)
    log_task_event(
        logger,
        "task_submitted",
        kind="screener",
        task_id=task_id,
        task=task,
        markets=",".join(str(market) for market in request_payload.get("markets", [])),
        as_of_date=request_payload.get("as_of_date"),
    )
    return {"task_id": task_id, "status": "pending"}


def create_cached_screener_task(
    *,
    request_payload: dict,
    config_payload: dict,
    run_id: str,
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
) -> dict:
    task_id = uuid.uuid4().hex
    now_iso = _utc_iso()
    progress = build_screener_progress(
        status="completed",
        stage="Export",
        current=1,
        total=1,
        message=f"Cache hit 1/1 {run_id}",
    )
    task = ScreenerTask(
        id=task_id,
        request_payload=request_payload,
        config_payload=config_payload,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        status="completed",
        latest_progress=progress,
        progress_events=[progress],
        run_id=run_id,
        created_at=now_iso,
        started_at=now_iso,
        finished_at=now_iso,
    )

    if task_store.redis_task_backend_enabled():
        save_screener_task(task)
        task_store.get_task_store().append_event("screener", task_id, progress)
    else:
        with screener_tasks_lock:
            screener_tasks[task_id] = task
        _upsert_screener_job_record(task)
    return {
        "task_id": task_id,
        "status": "completed",
        "run_id": run_id,
        "cached": True,
    }


def screener_task_from_payload(payload: dict) -> ScreenerTask:
    status = str(payload.get("status") or "pending")
    if task_store.redis_task_backend_enabled() and status == "pending":
        status = "queued"
    return ScreenerTask(
        id=str(payload["id"]),
        request_payload=dict(payload.get("request_payload") or {}),
        config_payload=dict(payload.get("config_payload") or {}),
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
        run_id=payload.get("run_id"),
        error=payload.get("error"),
        created_at=payload.get("created_at"),
        queued_at=payload.get("queued_at"),
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        queue_position=payload.get("queue_position"),
        blocked_reason=payload.get("blocked_reason"),
        blocked_vendor=payload.get("blocked_vendor"),
        blocked_until=payload.get("blocked_until"),
        cancel_requested_at=payload.get("cancel_requested_at"),
        canceled_at=payload.get("canceled_at"),
    )


def list_screener_tasks() -> list[ScreenerTask]:
    if task_store.redis_task_backend_enabled():
        store = task_store.get_task_store()
        result = []
        for payload in store.list_tasks("screener"):
            task = screener_task_from_payload(payload)
            task.queue_position = store.queue_position("screener", task.id)
            result.append(task)
        return result
    with screener_tasks_lock:
        return list(screener_tasks.values())


def get_screener_progress_events(task_id: str, start: int = 0) -> list[dict]:
    if task_store.redis_task_backend_enabled():
        return task_store.get_task_store().list_events("screener", task_id, start)
    with screener_tasks_lock:
        task = screener_tasks.get(task_id)
        if task is None:
            return []
        return task.progress_events[start:]


def save_screener_task(task: ScreenerTask) -> None:
    _upsert_screener_job_record(task)
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().save_task("screener", task.id, task.to_dict())
        return
    with screener_tasks_lock:
        screener_tasks[task.id] = task


def _upsert_screener_job_record(task: ScreenerTask) -> None:
    task_lifecycle.upsert_job_record(
        kind="screener",
        task=task,
        request_payload=task.request_payload,
        result_summary={"run_id": task.run_id} if task.run_id else None,
    )


def claim_next_screener_task(*, timeout: int = 5) -> str | None:
    if not task_store.redis_task_backend_enabled():
        return None
    from web.backend.runtime import task_scheduler

    return task_scheduler.claim_next_kind("screener", timeout=timeout)


def cancel_screener_task(task_id: str) -> None:
    task = get_screener_task(task_id)
    if task.status in task_store.TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Finished screener tasks cannot be canceled.",
        )
    transition = task_lifecycle.apply_cancel_transition(
        kind="screener",
        task_id=task_id,
        task=task,
        now_iso=_utc_iso(),
        cancel_requested_progress=build_screener_cancel_requested_progress,
        canceled_progress=lambda task: build_screener_canceled_progress(
            task, "Screener task canceled."
        ),
        save_task=save_screener_task,
    )
    if transition == "requested":
        log_task_event(
            logger,
            "task_cancel_requested",
            kind="screener",
            task_id=task_id,
            task=task,
        )
        return

    log_task_event(
        logger,
        "task_canceled",
        kind="screener",
        task_id=task_id,
        task=task,
    )


def storage_backend_is_remote() -> bool:
    return os.environ.get("STORAGE_BACKEND", "local").strip().lower() != "local"
