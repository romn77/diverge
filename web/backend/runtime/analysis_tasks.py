from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import uuid
import inspect
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from diverge.common.json_io import write_json_atomic
from diverge.dataflows import vendor_usage
from diverge.decision_card.builder import (
    build_decision_card,
    build_fallback_decision_card,
)
from diverge.decision_card.delta import (
    build_decision_delta,
    find_previous_decision_card,
    save_decision_delta,
)
from diverge.decision_card.storage import save_decision_card
from diverge.research.search.evidence import build_search_evidence_artifact
from diverge.research.search.session import search_sessions
from diverge.runner import (
    AnalysisProgress,
    AnalysisRequest,
    run_analysis_streaming,
    save_report_to_disk,
)
from web.backend import access, app_config, auth, report_metadata, storage
from web.backend.runtime import task_lifecycle, task_store
from web.backend.runtime.task_logging import (
    log_task_event,
    processing_stage,
    task_error_fields,
)

logger = logging.getLogger(__name__)
GENERIC_ANALYSIS_TASK_ERROR = "Analysis task failed. Check backend logs for details."


@dataclass
class Task:
    id: str
    request: AnalysisRequest
    owner_user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    report_visibility: str = report_metadata.REPORT_VISIBILITY_PRIVATE
    status: str = "pending"
    latest_progress: Optional[dict] = None
    progress_events: list[dict] = field(default_factory=list)
    report_id: Optional[str] = None
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
            "ticker": self.request.ticker,
            "analysis_date": self.request.analysis_date,
            "analysts": list(self.request.analysts),
            "request_payload": asdict(self.request),
            "owner_user_id": self.owner_user_id,
            "tenant_id": self.tenant_id,
            "report_visibility": self.report_visibility,
            "status": self.status,
            "latest_progress": self.latest_progress,
            "report_id": self.report_id,
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


tasks: dict[str, Task] = {}
tasks_lock = threading.Lock()


def count_active_tasks() -> int:
    if task_store.redis_task_backend_enabled():
        return task_store.get_task_store().count_active("analysis")
    with tasks_lock:
        return sum(
            1 for task in tasks.values() if task.status in task_store.ACTIVE_STATUSES
        )


def _utc_iso() -> str:
    return task_lifecycle.utc_iso()


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
        raise ValueError(
            "Report output directory must remain inside the reports root"
        ) from exc
    return report_dir


def _local_previous_report_dirs(task: Task, current_report_id: str) -> list[Path]:
    if not app_config.REPORTS_DIR.is_dir():
        return []

    if auth.auth_enabled() and task.owner_user_id:
        try:
            with auth.db_session() as db:
                user = db.get(auth.User, task.owner_user_id)
                owner_scope = access.owner_scope_for_user(user)
                records = report_metadata.list_report_runs(
                    db,
                    tenant_id=task.tenant_id,
                    owner_user_id=owner_scope,
                    include_workspace=owner_scope is not None,
                )
        except Exception:
            logger.exception(
                "Failed to list previous report metadata for decision delta."
            )
            return []

        report_dirs = []
        for record in records:
            if record.id == current_report_id:
                continue
            report_dir = app_config.REPORTS_DIR / record.storage_path
            if report_dir.is_dir():
                report_dirs.append(report_dir)
        return report_dirs

    return [
        path
        for path in app_config.REPORTS_DIR.iterdir()
        if path.is_dir()
        and not path.name.startswith(".")
        and path.name != current_report_id
    ]


def _write_decision_delta_if_available(
    *,
    task: Task,
    current_report_id: str,
    current_report_dir: Path,
    decision_card,
) -> None:
    try:
        previous_card = find_previous_decision_card(
            current_card=decision_card,
            candidate_report_dirs=_local_previous_report_dirs(task, current_report_id),
            current_report_id=current_report_id,
        )
        if previous_card is None:
            return
        delta = build_decision_delta(
            current_card=decision_card,
            previous_card=previous_card,
            current_report_id=current_report_id,
            output_language=task.request.output_language,
        )
        save_decision_delta(delta, current_report_dir)
    except Exception:
        logger.exception("Failed to build decision delta for %s", current_report_id)


def write_search_evidence_artifact(task_id: str, report_dir: Path) -> Path | None:
    session = search_sessions.get(task_id)
    if session is None:
        return None
    artifact = build_search_evidence_artifact(session)
    if artifact is None:
        return None
    artifact_path = report_dir / "artifacts" / "search_evidence.json"
    write_json_atomic(artifact_path, artifact)
    return artifact_path


def delete_task_snapshot(task_id: str) -> None:
    snapshot_path = task_snapshot_path(task_id)
    with suppress(FileNotFoundError):
        snapshot_path.unlink()

    for directory in (
        snapshot_path.parent,
        active_tasks_dir(),
        active_tasks_dir().parent,
    ):
        with suppress(OSError):
            directory.rmdir()


def persist_task_snapshot(task_id: str) -> None:
    task = get_task(task_id)
    _upsert_analysis_job_record(task)
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().save_task("analysis", task_id, task.to_dict())
        return
    snapshot = task.to_dict()
    if snapshot["status"] in app_config.TERMINAL_TASK_STATUSES:
        delete_task_snapshot(task_id)
        return
    write_json_atomic(task_snapshot_path(task_id), snapshot)


def task_from_snapshot(payload: dict) -> Task:
    request_payload = payload.get("request_payload")
    if not isinstance(request_payload, dict):
        raise ValueError("Persisted task snapshot is missing request_payload")

    status = str(payload.get("status") or "pending")
    if task_store.redis_task_backend_enabled() and status == "pending":
        status = "queued"
    return Task(
        id=str(payload["id"]),
        request=AnalysisRequest(**request_payload),
        owner_user_id=payload.get("owner_user_id"),
        tenant_id=payload.get("tenant_id"),
        report_visibility=str(
            payload.get(
                "report_visibility",
                report_metadata.REPORT_VISIBILITY_PRIVATE,
            )
        ),
        status=status,
        latest_progress=payload.get("latest_progress"),
        report_id=payload.get("report_id"),
        error=payload.get("error"),
        progress_events=list(payload.get("progress_events") or []),
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


def get_task(task_id: str) -> Task:
    if task_store.redis_task_backend_enabled():
        payload = task_store.get_task_store().get_task("analysis", task_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        task = task_from_snapshot(payload)
        task.queue_position = task_store.get_task_store().queue_position(
            "analysis", task_id
        )
        task.progress_events = task_store.get_task_store().list_events(
            "analysis", task_id
        )
        return task
    with tasks_lock:
        task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


def delete_failed_task(task_id: str) -> None:
    task = get_task(task_id)
    if task.status != "failed":
        raise HTTPException(
            status_code=409,
            detail="Only failed tasks can be deleted.",
        )

    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().delete_task("analysis", task_id)
        return

    with tasks_lock:
        tasks.pop(task_id, None)
    delete_task_snapshot(task_id)


def append_progress(task_id: str, progress: AnalysisProgress) -> None:
    event_payload = progress.to_dict()
    task = task_lifecycle.append_progress_event(
        kind="analysis",
        task_id=task_id,
        progress=event_payload,
        get_task=get_task,
        local_tasks=tasks,
        local_lock=tasks_lock,
        save_redis_task=save_task,
        save_local_task=lambda task: persist_task_snapshot(task.id),
    )
    log_task_event(
        logger,
        "task_progress",
        kind="analysis",
        task_id=task_id,
        task=task,
        status=event_payload.get("status"),
        stage=processing_stage(event_payload),
        current_agent=event_payload.get("current_agent"),
    )


def set_task_status(task_id: str, status: str, error: Optional[str] = None) -> None:
    if task_store.redis_task_backend_enabled():
        task = get_task(task_id)
        task_lifecycle.apply_status_transition(
            task,
            status,
            terminal_statuses=task_store.TERMINAL_STATUSES,
            error=error,
        )
        _upsert_analysis_job_record(task)
        task_store.get_task_store().save_task("analysis", task_id, task.to_dict())
        return
    with tasks_lock:
        task = tasks[task_id]
        task_lifecycle.apply_status_transition(
            task,
            status,
            terminal_statuses=task_store.TERMINAL_STATUSES,
            error=error,
        )
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
        timestamp=task_lifecycle.event_timestamp(),
        status="failed",
        stage_status=latest_progress["stage_status"],
        agent_status=latest_progress["agent_status"],
        current_agent=latest_progress["current_agent"],
        message=f"System: {error}",
    )
    return failure_progress.to_dict()


def build_waiting_for_quota_progress(
    task: Task, exc: vendor_usage.QuotaWaitRequired
) -> dict:
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
    return {
        "timestamp": task_lifecycle.event_timestamp(),
        "status": "waiting_for_quota",
        "stage_status": latest_progress["stage_status"],
        "agent_status": latest_progress["agent_status"],
        "current_agent": latest_progress["current_agent"],
        "message": (
            f"Waiting for {exc.vendor} quota"
            + (f" until {exc.blocked_until}" if exc.blocked_until else "")
            + "."
        ),
    }


def _analysis_progress_template(task: Task) -> dict:
    return task.latest_progress or {
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


def build_canceled_progress(task: Task, message: str | None = None) -> dict:
    latest_progress = _analysis_progress_template(task)
    return AnalysisProgress(
        timestamp=task_lifecycle.event_timestamp(),
        status="canceled",
        stage_status=latest_progress["stage_status"],
        agent_status=latest_progress["agent_status"],
        current_agent=latest_progress["current_agent"],
        message=message or "System: Task canceled by request.",
    ).to_dict()


def build_cancel_requested_progress(task: Task) -> dict:
    latest_progress = _analysis_progress_template(task)
    return AnalysisProgress(
        timestamp=task_lifecycle.event_timestamp(),
        status="running",
        stage_status=latest_progress["stage_status"],
        agent_status=latest_progress["agent_status"],
        current_agent=latest_progress["current_agent"],
        message="System: Termination requested. Work will stop at the next safe step.",
    ).to_dict()


def check_task_canceled(task_id: str) -> None:
    if get_task(task_id).cancel_requested_at:
        raise task_store.TaskCanceled("Analysis task canceled by request.")


def _mark_task_canceled(task_id: str, temp_dir: Path | None = None) -> None:
    if temp_dir is not None and temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    current_task = get_task(task_id)
    task_lifecycle.apply_canceled_completion_transition(
        kind="analysis",
        task_id=task_id,
        task=current_task,
        canceled_progress=build_canceled_progress,
        save_task=save_task,
    )
    log_task_event(
        logger,
        "task_canceled",
        kind="analysis",
        task_id=task_id,
        task=current_task,
    )
    persist_task_snapshot(task_id)


def wait_for_quota(task_id: str, exc: vendor_usage.QuotaWaitRequired) -> None:
    current_task = get_task(task_id)
    task_lifecycle.apply_quota_wait_transition(
        kind="analysis",
        task_id=task_id,
        task=current_task,
        reason=exc.reason,
        vendor=exc.vendor,
        blocked_until=exc.blocked_until,
        build_progress=lambda task: build_waiting_for_quota_progress(task, exc),
        save_task=save_task,
    )


def restore_persisted_active_tasks() -> None:
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().recover_processing("analysis")
        for task in list_tasks():
            if task.status == "running":
                task_lifecycle.apply_recovered_failure_transition(
                    kind="analysis",
                    task=task,
                    error=app_config.RECOVERED_TASK_ERROR,
                    build_progress=lambda task: build_failure_progress(
                        task, app_config.RECOVERED_TASK_ERROR
                    ),
                    save_task=save_task,
                    append_redis_event=True,
                    ack_redis_processing=True,
                )
        return
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

        task_lifecycle.apply_recovered_failure_transition(
            kind="analysis",
            task=task,
            error=app_config.RECOVERED_TASK_ERROR,
            build_progress=lambda task: build_failure_progress(
                task, app_config.RECOVERED_TASK_ERROR
            ),
            replace_progress_events=True,
        )

        with tasks_lock:
            tasks[task.id] = task

        delete_task_snapshot(task.id)


def start_task_thread(task_id: str) -> threading.Thread:
    thread = threading.Thread(target=run_task, args=(task_id,), daemon=True)
    thread.start()
    return thread


def _fail_task(task_id: str, error: str) -> None:
    current_task = get_task(task_id)
    task_lifecycle.apply_failure_transition(
        kind="analysis",
        task=current_task,
        error=error,
        build_progress=lambda task: build_failure_progress(task, error),
        save_task=save_task,
        append_redis_event=True,
    )
    log_task_event(
        logger,
        "task_failed",
        kind="analysis",
        task_id=task_id,
        task=current_task,
        **task_error_fields(error),
    )
    persist_task_snapshot(task_id)


def run_task(task_id: str) -> None:
    task = get_task(task_id)
    temp_dir = app_config.tmp_reports_dir() / task_id

    set_task_status(task_id, "running")
    log_task_event(
        logger,
        "task_started",
        kind="analysis",
        task_id=task_id,
        task=get_task(task_id),
        ticker=task.request.ticker,
        analysis_date=task.request.analysis_date,
    )

    try:
        check_task_canceled(task_id)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        check_task_canceled(task_id)

        visible_ids = access.visible_trade_ids_for_task(task)
        with vendor_usage.data_source_usage_context("analysis"):
            stream_kwargs = {
                "reports_dir": app_config.REPORTS_DIR,
                "visible_trade_ids": visible_ids,
            }
            if (
                "analysis_run_id"
                in inspect.signature(run_analysis_streaming).parameters
            ):
                stream_kwargs["analysis_run_id"] = task_id
            progress_stream = run_analysis_streaming(
                task.request,
                temp_dir,
                **stream_kwargs,
            )
            final_state = None
            while True:
                try:
                    progress = next(progress_stream)
                except StopIteration as stop:
                    final_state = stop.value
                    break

                append_progress(task_id, progress)
                check_task_canceled(task_id)

        check_task_canceled(task_id)
        if final_state is None:
            raise RuntimeError("Analysis did not return a final state")

        timestamp = datetime.now().strftime("%H%M%S")
        report_id = (
            f"{task.request.ticker}_"
            f"{str(task.request.analysis_date).replace('-', '')}_{timestamp}"
        )
        check_task_canceled(task_id)
        save_report_to_disk(final_state, task.request.ticker, temp_dir)
        check_task_canceled(task_id)
        write_search_evidence_artifact(task_id, temp_dir)
        try:
            decision_card = build_decision_card(
                final_state=final_state,
                symbol=task.request.ticker,
                report_id=report_id,
                analysis_date=str(task.request.analysis_date),
                output_language=task.request.output_language,
            )
            save_decision_card(decision_card, temp_dir)
            _write_decision_delta_if_available(
                task=task,
                current_report_id=report_id,
                current_report_dir=temp_dir,
                decision_card=decision_card,
            )
        except Exception as exc:
            logger.exception("Failed to build decision card for %s", report_id)
            fallback_card = build_fallback_decision_card(
                symbol=task.request.ticker,
                report_id=report_id,
                analysis_date=str(task.request.analysis_date),
                raw_signal=(
                    final_state.get("final_trade_decision")
                    if isinstance(final_state.get("final_trade_decision"), str)
                    else None
                ),
                error=str(exc),
                output_language=task.request.output_language,
            )
            save_decision_card(fallback_card, temp_dir)
        check_task_canceled(task_id)
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
                    tenant_id=task.tenant_id,
                    visibility=task.report_visibility,
                    ticker=str(metadata_payload["ticker"] or task.request.ticker),
                    generated_at=metadata_payload["generated_at"],
                    storage_path=str(metadata_payload["storage_path"] or report_id),
                    file_entries=file_entries,
                )

        if storage_backend_is_remote():
            storage.upload_directory(final_report_dir, f"reports/{report_id}")

        current_task = get_task(task_id)
        current_task.status = "completed"
        current_task.finished_at = _utc_iso()
        current_task.report_id = report_id
        if current_task.latest_progress is not None:
            current_task.latest_progress["status"] = "completed"
        save_task(current_task)
        persist_task_snapshot(task_id)
        log_task_event(
            logger,
            "task_completed",
            kind="analysis",
            task_id=task_id,
            task=current_task,
            report_id=report_id,
        )
    except vendor_usage.QuotaWaitRequired as exc:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        if task_store.redis_task_backend_enabled():
            wait_for_quota(task_id, exc)
            log_task_event(
                logger,
                "task_waiting_for_quota",
                kind="analysis",
                task_id=task_id,
                task=get_task(task_id),
                blocked_reason=exc.reason,
                blocked_vendor=exc.vendor,
                blocked_until=exc.blocked_until,
            )
            return
        _fail_task(task_id, str(exc))
    except task_store.TaskCanceled:
        _mark_task_canceled(task_id, temp_dir)
    except Exception:  # pragma: no cover
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        logger.exception("analysis task failed task_id=%s", task_id)
        _fail_task(task_id, GENERIC_ANALYSIS_TASK_ERROR)
    finally:
        search_sessions.pop(task_id)


def create_task(
    analysis_request: AnalysisRequest,
    *,
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
    report_visibility: str = report_metadata.REPORT_VISIBILITY_PRIVATE,
) -> dict:
    task_id = uuid.uuid4().hex
    now_iso = _utc_iso()
    task = Task(
        id=task_id,
        request=analysis_request,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        report_visibility=report_visibility,
        created_at=now_iso,
    )

    if task_store.redis_task_backend_enabled():
        task.status = "queued"
        task.queued_at = now_iso
        save_task(task)
        task_store.get_task_store().enqueue("analysis", task_id)
        task_store.get_task_store().append_event(
            "analysis",
            task_id,
            task_lifecycle.queued_progress(
                "Task queued.",
                stage_status={
                    "Analysts": "not_started",
                    "Research": "not_started",
                    "Trading": "not_started",
                    "Risk": "not_started",
                    "Portfolio": "not_started",
                },
                agent_status={},
                include_current_agent=True,
            ),
        )
        log_task_event(
            logger,
            "task_queued",
            kind="analysis",
            task_id=task_id,
            task=task,
            ticker=analysis_request.ticker,
            analysis_date=analysis_request.analysis_date,
        )
        return {"task_id": task_id, "status": "queued"}

    with tasks_lock:
        tasks[task_id] = task
    persist_task_snapshot(task_id)
    start_task_thread(task_id)
    log_task_event(
        logger,
        "task_submitted",
        kind="analysis",
        task_id=task_id,
        task=task,
        ticker=analysis_request.ticker,
        analysis_date=analysis_request.analysis_date,
    )
    return {"task_id": task_id, "status": "pending"}


def resolve_owner_user_id(request) -> str | None:
    return access.resolve_task_owner_user_id(request)


def list_tasks() -> list[Task]:
    if task_store.redis_task_backend_enabled():
        store = task_store.get_task_store()
        result = []
        for payload in store.list_tasks("analysis"):
            task = task_from_snapshot(payload)
            task.queue_position = store.queue_position("analysis", task.id)
            result.append(task)
        return result
    with tasks_lock:
        return list(tasks.values())


def get_progress_events(task_id: str, start: int = 0) -> list[dict]:
    if task_store.redis_task_backend_enabled():
        return task_store.get_task_store().list_events("analysis", task_id, start)
    with tasks_lock:
        task = tasks.get(task_id)
        if task is None:
            return []
        return task.progress_events[start:]


def save_task(task: Task) -> None:
    _upsert_analysis_job_record(task)
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().save_task("analysis", task.id, task.to_dict())
        return
    with tasks_lock:
        tasks[task.id] = task


def _upsert_analysis_job_record(task: Task) -> None:
    task_lifecycle.upsert_job_record(
        kind="analysis",
        task=task,
        request_payload=task.to_dict().get("request_payload"),
        result_summary={"report_id": task.report_id} if task.report_id else None,
    )


def claim_next_task(*, timeout: int = 5) -> str | None:
    if not task_store.redis_task_backend_enabled():
        return None
    from web.backend.runtime import task_scheduler

    return task_scheduler.claim_next_kind("analysis", timeout=timeout)


def cancel_task(task_id: str) -> None:
    task = get_task(task_id)
    if task.status in task_store.TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409, detail="Finished tasks cannot be canceled."
        )
    transition = task_lifecycle.apply_cancel_transition(
        kind="analysis",
        task_id=task_id,
        task=task,
        now_iso=_utc_iso(),
        cancel_requested_progress=build_cancel_requested_progress,
        canceled_progress=lambda task: build_canceled_progress(
            task, "System: Task canceled."
        ),
        save_task=save_task,
    )
    if transition == "requested":
        log_task_event(
            logger,
            "task_cancel_requested",
            kind="analysis",
            task_id=task_id,
            task=task,
        )
        return

    log_task_event(
        logger,
        "task_canceled",
        kind="analysis",
        task_id=task_id,
        task=task,
    )


def storage_backend_is_remote() -> bool:
    return os.environ.get("STORAGE_BACKEND", "local").strip().lower() != "local"
