from __future__ import annotations

import json
import shutil
import threading
import uuid
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from tradingagents.runner import (
    AnalysisProgress,
    AnalysisRequest,
    run_analysis_streaming,
    save_report_to_disk,
)
from web.backend import access, app_config, auth, report_metadata


@dataclass
class Task:
    id: str
    request: AnalysisRequest
    owner_user_id: Optional[str] = None
    status: str = "pending"
    latest_progress: Optional[dict] = None
    progress_events: list[dict] = field(default_factory=list)
    report_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticker": self.request.ticker,
            "analysis_date": self.request.analysis_date,
            "analysts": list(self.request.analysts),
            "request_payload": asdict(self.request),
            "owner_user_id": self.owner_user_id,
            "status": self.status,
            "latest_progress": self.latest_progress,
            "report_id": self.report_id,
            "error": self.error,
        }


tasks: dict[str, Task] = {}
tasks_lock = threading.Lock()


def count_active_tasks() -> int:
    with tasks_lock:
        return sum(1 for task in tasks.values() if task.status in {"pending", "running"})


def active_tasks_dir() -> Path:
    return (
        app_config.REPORTS_DIR
        / app_config.TASKS_STATE_DIRNAME
        / app_config.ACTIVE_TASKS_DIRNAME
    )


def task_snapshot_path(task_id: str) -> Path:
    return active_tasks_dir() / task_id / "task.json"


def report_output_dir(report_id: str) -> Path:
    reports_root = app_config.REPORTS_DIR.resolve()
    report_dir = (app_config.REPORTS_DIR / report_id).resolve()
    try:
        report_dir.relative_to(reports_root)
    except ValueError as exc:
        raise ValueError("Report output directory must remain inside the reports root") from exc
    return report_dir


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def delete_task_snapshot(task_id: str) -> None:
    snapshot_path = task_snapshot_path(task_id)
    with suppress(FileNotFoundError):
        snapshot_path.unlink()

    for directory in (snapshot_path.parent, active_tasks_dir(), active_tasks_dir().parent):
        with suppress(OSError):
            directory.rmdir()


def persist_task_snapshot(task_id: str) -> None:
    task = get_task(task_id)
    snapshot = task.to_dict()
    if snapshot["status"] in app_config.TERMINAL_TASK_STATUSES:
        delete_task_snapshot(task_id)
        return
    _write_json_atomic(task_snapshot_path(task_id), snapshot)


def task_from_snapshot(payload: dict) -> Task:
    request_payload = payload.get("request_payload")
    if not isinstance(request_payload, dict):
        raise ValueError("Persisted task snapshot is missing request_payload")

    return Task(
        id=str(payload["id"]),
        request=AnalysisRequest(**request_payload),
        owner_user_id=payload.get("owner_user_id"),
        status=str(payload.get("status") or "pending"),
        latest_progress=payload.get("latest_progress"),
        report_id=payload.get("report_id"),
        error=payload.get("error"),
    )


def get_task(task_id: str) -> Task:
    with tasks_lock:
        task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


def append_progress(task_id: str, progress: AnalysisProgress) -> None:
    event_payload = progress.to_dict()
    with tasks_lock:
        task = tasks[task_id]
        task.latest_progress = event_payload
        task.progress_events.append(event_payload)
    persist_task_snapshot(task_id)


def set_task_status(task_id: str, status: str, error: Optional[str] = None) -> None:
    with tasks_lock:
        task = tasks[task_id]
        task.status = status
        if error is not None:
            task.error = error
    persist_task_snapshot(task_id)


def build_failure_progress(task: Task, error: str) -> dict:
    latest_progress = task.latest_progress or {
        "stage_status": {
            "Analysts": "not_started",
            "Research": "not_started",
            "Trading": "not_started",
            "Risk": "not_started",
            "Portfolio": "not_started",
        },
        "agent_status": {},
        "current_agent": None,
    }
    failure_progress = AnalysisProgress(
        timestamp=datetime.now().strftime("%H:%M:%S"),
        status="failed",
        stage_status=latest_progress["stage_status"],
        agent_status=latest_progress["agent_status"],
        current_agent=latest_progress["current_agent"],
        message=f"System: {error}",
    )
    return failure_progress.to_dict()


def restore_persisted_active_tasks() -> None:
    active_dir = active_tasks_dir()
    if not active_dir.is_dir():
        return

    for snapshot_path in sorted(active_dir.glob("*/task.json")):
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            task = task_from_snapshot(payload)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            delete_task_snapshot(snapshot_path.parent.name)
            continue

        if task.status in app_config.TERMINAL_TASK_STATUSES:
            delete_task_snapshot(task.id)
            continue

        task.status = "failed"
        task.error = app_config.RECOVERED_TASK_ERROR
        failure_progress = build_failure_progress(task, app_config.RECOVERED_TASK_ERROR)
        task.latest_progress = failure_progress
        task.progress_events = [failure_progress]

        with tasks_lock:
            tasks[task.id] = task

        delete_task_snapshot(task.id)


def start_task_thread(task_id: str) -> threading.Thread:
    thread = threading.Thread(target=run_task, args=(task_id,), daemon=True)
    thread.start()
    return thread


def run_task(task_id: str) -> None:
    task = get_task(task_id)
    temp_dir = app_config.tmp_reports_dir() / task_id

    set_task_status(task_id, "running")

    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        visible_ids = access.visible_trade_ids_for_task(task)
        progress_stream = run_analysis_streaming(
            task.request,
            temp_dir,
            reports_dir=app_config.REPORTS_DIR,
            visible_trade_ids=visible_ids,
        )
        final_state = None
        while True:
            try:
                progress = next(progress_stream)
            except StopIteration as stop:
                final_state = stop.value
                break

            append_progress(task_id, progress)

        if final_state is None:
            raise RuntimeError("Analysis did not return a final state")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_id = f"{task.request.ticker}_{timestamp}"
        save_report_to_disk(final_state, task.request.ticker, temp_dir)
        app_config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        final_report_dir = report_output_dir(report_id)
        temp_dir.replace(final_report_dir)
        if auth.auth_enabled() and task.owner_user_id:
            metadata_payload = report_metadata.build_report_metadata(
                final_report_dir,
                report_id=report_id,
            )
            file_entries = report_metadata.build_report_file_index(final_report_dir)
            with auth.db_session() as db:
                report_metadata.upsert_report_run(
                    db,
                    report_id=report_id,
                    owner_user_id=task.owner_user_id,
                    visibility=report_metadata.REPORT_VISIBILITY_PRIVATE,
                    ticker=str(metadata_payload["ticker"] or task.request.ticker),
                    generated_at=metadata_payload["generated_at"],
                    storage_path=str(metadata_payload["storage_path"] or report_id),
                    file_entries=file_entries,
                )

        with tasks_lock:
            current_task = tasks[task_id]
            current_task.status = "completed"
            current_task.report_id = report_id
            if current_task.latest_progress is not None:
                current_task.latest_progress["status"] = "completed"
        persist_task_snapshot(task_id)
    except Exception as exc:  # pragma: no cover
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

        with tasks_lock:
            current_task = tasks[task_id]
            current_task.status = "failed"
            current_task.error = str(exc)
            failure_progress = build_failure_progress(current_task, str(exc))
            current_task.latest_progress = failure_progress
            current_task.progress_events.append(failure_progress)
        persist_task_snapshot(task_id)


def create_task(analysis_request: AnalysisRequest, *, owner_user_id: str | None = None) -> dict:
    task_id = uuid.uuid4().hex
    task = Task(
        id=task_id,
        request=analysis_request,
        owner_user_id=owner_user_id,
    )

    with tasks_lock:
        tasks[task_id] = task

    persist_task_snapshot(task_id)
    start_task_thread(task_id)
    return {"task_id": task_id, "status": "pending"}


def resolve_owner_user_id(request) -> str | None:
    return access.resolve_task_owner_user_id(request)
