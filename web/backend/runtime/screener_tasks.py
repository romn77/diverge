from __future__ import annotations

import json
import threading
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from tradingagents.screener.pipeline import run_screen
from tradingagents.screener.schema import ScreenRunConfig
from web.backend import app_config
from web.backend.services import screeners as screener_service

SCREENER_STAGES = ["Universe", "History", "Features", "Filters", "Ranking", "Export"]


@dataclass
class ScreenerTask:
    id: str
    request_payload: dict
    config_payload: dict
    owner_user_id: Optional[str] = None
    status: str = "pending"
    latest_progress: Optional[dict] = None
    progress_events: list[dict] = field(default_factory=list)
    run_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "request_payload": self.request_payload,
            "config_payload": self.config_payload,
            "owner_user_id": self.owner_user_id,
            "status": self.status,
            "latest_progress": self.latest_progress,
            "progress_events": self.progress_events,
            "run_id": self.run_id,
            "error": self.error,
        }


screener_tasks: dict[str, ScreenerTask] = {}
screener_tasks_lock = threading.Lock()


def count_active_tasks() -> int:
    with screener_tasks_lock:
        return sum(
            1 for task in screener_tasks.values() if task.status in {"pending", "running"}
        )


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
    snapshot = task.to_dict()
    if snapshot["status"] in app_config.TERMINAL_TASK_STATUSES:
        delete_screener_task_snapshot(task_id)
        return
    _write_json_atomic(screener_task_snapshot_path(task_id), snapshot)


def get_screener_task(task_id: str) -> ScreenerTask:
    with screener_tasks_lock:
        task = screener_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Screener task '{task_id}' not found")
    return task


def append_screener_progress(task_id: str, progress: dict) -> None:
    with screener_tasks_lock:
        task = screener_tasks[task_id]
        task.latest_progress = progress
        task.progress_events.append(progress)
    persist_screener_task_snapshot(task_id)


def set_screener_task_status(task_id: str, status: str, error: Optional[str] = None) -> None:
    with screener_tasks_lock:
        task = screener_tasks[task_id]
        task.status = status
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


def restore_persisted_screener_tasks() -> None:
    active_dir = active_screener_tasks_dir()
    if not active_dir.is_dir():
        return

    for snapshot_path in sorted(active_dir.glob("*/task.json")):
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            task = ScreenerTask(
                id=str(payload["id"]),
                request_payload=dict(payload.get("request_payload") or {}),
                config_payload=dict(payload.get("config_payload") or {}),
                owner_user_id=(
                    str(payload["owner_user_id"]).strip()
                    if payload.get("owner_user_id")
                    else None
                ),
                status=str(payload.get("status") or "pending"),
                latest_progress=payload.get("latest_progress"),
                progress_events=list(payload.get("progress_events") or []),
                run_id=payload.get("run_id"),
                error=payload.get("error"),
            )
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
        result = run_screen(
            ScreenRunConfig(**current_task.config_payload),
            progress_callback=progress_callback,
        )

        current_task = get_screener_task(task_id)
        screener_service.record_screener_run_metadata(current_task, result)

        with screener_tasks_lock:
            current_task = screener_tasks[task_id]
            current_task.status = "completed"
            current_task.run_id = Path(result.run_dir).name
            current_task.latest_progress = build_screener_progress(
                status="completed",
                stage="Export",
                current=1,
                total=1,
                message=f"Export 1/1 {current_task.run_id}",
            )
            current_task.progress_events.append(current_task.latest_progress)
        persist_screener_task_snapshot(task_id)
    except Exception as exc:  # pragma: no cover
        with screener_tasks_lock:
            current_task = screener_tasks[task_id]
            current_task.status = "failed"
            current_task.error = str(exc)
            failure_progress = build_screener_failure_progress(current_task, str(exc))
            current_task.latest_progress = failure_progress
            current_task.progress_events.append(failure_progress)
        persist_screener_task_snapshot(task_id)


def create_screener_task(
    *,
    request_payload: dict,
    config_payload: dict,
    owner_user_id: str | None = None,
) -> dict:
    task_id = uuid.uuid4().hex
    task = ScreenerTask(
        id=task_id,
        request_payload=request_payload,
        config_payload=config_payload,
        owner_user_id=owner_user_id,
    )

    with screener_tasks_lock:
        screener_tasks[task_id] = task

    persist_screener_task_snapshot(task_id)
    start_screener_task_thread(task_id)
    return {"task_id": task_id, "status": "pending"}
