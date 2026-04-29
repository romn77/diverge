from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from diverge.dataflows import vendor_usage
from diverge.screener.pipeline import run_screen
from diverge.screener.schema import ScreenRunConfig
from web.backend import app_config, storage
from web.backend.runtime import task_store
from web.backend.services import screeners as screener_service

SCREENER_STAGES = ["Universe", "History", "Features", "Filters", "Ranking", "Export"]
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
            "canceled_at": self.canceled_at,
        }


screener_tasks: dict[str, ScreenerTask] = {}
screener_tasks_lock = threading.Lock()


def count_active_tasks() -> int:
    if task_store.redis_task_backend_enabled():
        return task_store.get_task_store().count_active("screener")
    with screener_tasks_lock:
        return sum(
            1 for task in screener_tasks.values() if task.status in task_store.ACTIVE_STATUSES
        )


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def active_screener_tasks_dir() -> Path:
    return app_config.SCREENER_TASKS_DIR / app_config.ACTIVE_TASKS_DIRNAME


def screener_task_snapshot_path(task_id: str) -> Path:
    return active_screener_tasks_dir() / task_id / "task.json"


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


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
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().save_task("screener", task_id, task.to_dict())
        return
    snapshot = task.to_dict()
    if snapshot["status"] in app_config.TERMINAL_TASK_STATUSES:
        delete_screener_task_snapshot(task_id)
        return
    _write_json_atomic(screener_task_snapshot_path(task_id), snapshot)


def get_screener_task(task_id: str) -> ScreenerTask:
    if task_store.redis_task_backend_enabled():
        payload = task_store.get_task_store().get_task("screener", task_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Screener task '{task_id}' not found")
        task = screener_task_from_payload(payload)
        task.queue_position = task_store.get_task_store().queue_position("screener", task_id)
        task.progress_events = task_store.get_task_store().list_events("screener", task_id)
        return task
    with screener_tasks_lock:
        task = screener_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Screener task '{task_id}' not found")
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
    if task_store.redis_task_backend_enabled():
        task = get_screener_task(task_id)
        task.latest_progress = progress
        task.progress_events.append(progress)
        task_store.get_task_store().save_task("screener", task_id, task.to_dict())
        task_store.get_task_store().append_event("screener", task_id, progress)
        return
    with screener_tasks_lock:
        task = screener_tasks[task_id]
        task.latest_progress = progress
        task.progress_events.append(progress)
    persist_screener_task_snapshot(task_id)


def set_screener_task_status(task_id: str, status: str, error: Optional[str] = None) -> None:
    if task_store.redis_task_backend_enabled():
        task = get_screener_task(task_id)
        task.status = status
        if status == "running" and task.started_at is None:
            task.started_at = _utc_iso()
        if status in task_store.TERMINAL_STATUSES:
            task.finished_at = _utc_iso()
        if error is not None:
            task.error = error
        task_store.get_task_store().save_task("screener", task_id, task.to_dict())
        return
    with screener_tasks_lock:
        task = screener_tasks[task_id]
        task.status = status
        if status == "running" and task.started_at is None:
            task.started_at = _utc_iso()
        if status in task_store.TERMINAL_STATUSES:
            task.finished_at = _utc_iso()
        if error is not None:
            task.error = error
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
    if status == "completed":
        stage_status = {key: "completed" for key in SCREENER_STAGES}
    if status == "failed" and stage not in SCREENER_STAGES:
        stage_status = {key: "not_started" for key in SCREENER_STAGES}

    detail = message or f"{stage} {current}/{total}"
    if symbol:
        detail = f"{detail} {symbol}"

    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "status": status,
        "stage_status": stage_status,
        "agent_status": {},
        "current_agent": symbol,
        "message": detail,
    }


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
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "status": "failed",
        "stage_status": stage_status,
        "agent_status": latest_progress.get("agent_status") or {},
        "current_agent": latest_progress.get("current_agent"),
        "message": f"System: {error}",
    }


def build_screener_waiting_for_quota_progress(
    task: ScreenerTask,
    exc: vendor_usage.QuotaWaitRequired,
) -> dict:
    latest_progress = task.latest_progress or {}
    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
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


def _blocked_until_timestamp(blocked_until: str | None) -> float:
    if not blocked_until:
        return datetime.now(timezone.utc).timestamp() + 3600
    try:
        parsed = datetime.fromisoformat(blocked_until)
    except ValueError:
        return datetime.now(timezone.utc).timestamp() + 3600
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def wait_screener_for_quota(task_id: str, exc: vendor_usage.QuotaWaitRequired) -> None:
    current_task = get_screener_task(task_id)
    current_task.status = "waiting_for_quota"
    current_task.blocked_reason = exc.reason
    current_task.blocked_vendor = exc.vendor
    current_task.blocked_until = exc.blocked_until
    waiting_progress = build_screener_waiting_for_quota_progress(current_task, exc)
    current_task.latest_progress = waiting_progress
    current_task.progress_events.append(waiting_progress)
    save_screener_task(current_task)
    if task_store.redis_task_backend_enabled():
        store = task_store.get_task_store()
        store.delay("screener", task_id, _blocked_until_timestamp(exc.blocked_until))
        store.append_event("screener", task_id, waiting_progress)


def restore_persisted_screener_tasks() -> None:
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().recover_processing("screener")
        for task in list_screener_tasks():
            if task.status == "running":
                task.status = "failed"
                task.error = app_config.RECOVERED_TASK_ERROR
                task.latest_progress = build_screener_failure_progress(
                    task,
                    app_config.RECOVERED_TASK_ERROR,
                )
                task.progress_events.append(task.latest_progress)
                save_screener_task(task)
                task_store.get_task_store().append_event(
                    "screener",
                    task.id,
                    task.latest_progress,
                )
                task_store.get_task_store().ack("screener", task.id)
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

        task.status = "failed"
        task.error = app_config.RECOVERED_TASK_ERROR
        task.latest_progress = build_screener_failure_progress(
            task,
            app_config.RECOVERED_TASK_ERROR,
        )
        task.progress_events = [task.latest_progress]

        with screener_tasks_lock:
            screener_tasks[task.id] = task

        delete_screener_task_snapshot(task.id)


def start_screener_task_thread(task_id: str) -> threading.Thread:
    thread = threading.Thread(target=run_screener_task, args=(task_id,), daemon=True)
    thread.start()
    return thread


def _fail_screener_task(task_id: str, error: str) -> None:
    current_task = get_screener_task(task_id)
    current_task.status = "failed"
    current_task.finished_at = _utc_iso()
    current_task.error = error
    failure_progress = build_screener_failure_progress(current_task, error)
    current_task.latest_progress = failure_progress
    current_task.progress_events.append(failure_progress)
    save_screener_task(current_task)
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().append_event("screener", task_id, failure_progress)
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

    try:

        def progress_callback(
            stage: str,
            current: int,
            total: int,
            symbol: str | None = None,
            *,
            status: str | None = None,
            detail: str | None = None,
        ) -> None:
            normalized_stage = stage.capitalize()
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

        current_task = get_screener_task(task_id)
        with vendor_usage.data_source_usage_context("screener"):
            result = run_screen(
                ScreenRunConfig(**current_task.config_payload),
                progress_callback=progress_callback,
            )
        if storage_backend_is_remote():
            storage.upload_directory(Path(result.run_dir), f"screener/runs/{Path(result.run_dir).name}")

        current_task = get_screener_task(task_id)
        candidate = screener_service.run_screener(current_task, result)
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
    except vendor_usage.QuotaWaitRequired as exc:
        if task_store.redis_task_backend_enabled():
            wait_screener_for_quota(task_id, exc)
            return
        _fail_screener_task(task_id, str(exc))
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
        task.status = "queued"
        task.queued_at = now_iso
        task_store.get_task_store().save_task(
            "screener",
            task_id,
            task.to_dict(),
            enqueue=True,
        )
        task_store.get_task_store().append_event(
            "screener",
            task_id,
            build_screener_progress(
                status="queued",
                stage="Universe",
                current=0,
                total=1,
                message="Screener task queued.",
            ),
        )
        return {"task_id": task_id, "status": "queued"}

    with screener_tasks_lock:
        screener_tasks[task_id] = task
    persist_screener_task_snapshot(task_id)
    start_screener_task_thread(task_id)
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
        task_store.get_task_store().save_task("screener", task_id, task.to_dict())
        task_store.get_task_store().append_event("screener", task_id, progress)
    else:
        with screener_tasks_lock:
            screener_tasks[task_id] = task
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
            str(payload["tenant_id"]).strip()
            if payload.get("tenant_id")
            else None
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
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().save_task("screener", task.id, task.to_dict())
        return
    with screener_tasks_lock:
        screener_tasks[task.id] = task


def claim_next_screener_task(*, timeout: int = 5) -> str | None:
    if not task_store.redis_task_backend_enabled():
        return None
    from web.backend.runtime import task_scheduler

    return task_scheduler.claim_next_kind("screener", timeout=timeout)


def cancel_screener_task(task_id: str) -> None:
    task = get_screener_task(task_id)
    if task.status not in {"pending", "queued", "waiting_for_quota"}:
        raise HTTPException(status_code=409, detail="Only queued or waiting screener tasks can be canceled.")
    now_iso = _utc_iso()
    task.status = "canceled"
    task.canceled_at = now_iso
    task.finished_at = now_iso
    save_screener_task(task)
    if task_store.redis_task_backend_enabled():
        store = task_store.get_task_store()
        store.remove_task_refs("screener", task_id)
        store.append_event(
            "screener",
            task_id,
            build_screener_progress(
                status="canceled",
                stage="Universe",
                current=0,
                total=1,
                message="Screener task canceled.",
            ),
        )


def storage_backend_is_remote() -> bool:
    return os.environ.get("STORAGE_BACKEND", "local").strip().lower() != "local"
