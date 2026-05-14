from __future__ import annotations

import json
import logging
import shutil
import threading
import uuid
import inspect
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from diverge.common.json_io import write_json_atomic
from diverge.dataflows import vendor_usage
from diverge.decision_card.builder import (
    build_decision_card,
    build_fallback_decision_card,
)
from diverge.decision_card.storage import save_decision_card
from diverge.research.search.session import search_sessions
from diverge.runner import (
    AnalysisProgress,
    AnalysisRequest,
    run_analysis_streaming,
    save_report_to_disk,
)
from web.backend import access, app_config, report_metadata, storage
from web.backend.runtime import task_lifecycle, task_store
from web.backend.runtime.task_logging import (
    log_task_event,
    processing_stage,
    task_error_fields,
)
from web.backend.services.config import hydrate_provider_credentials
from web.backend.services import report_publication

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
    return report_publication.report_output_dir(report_id)


def write_search_evidence_artifact(task_id: str, report_dir: Path) -> Path | None:
    return report_publication.write_search_evidence_artifact(task_id, report_dir)


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


def _analysis_request_constructor_payload(request_payload: dict) -> dict:
    signature = inspect.signature(AnalysisRequest)
    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    ):
        return dict(request_payload)

    accepted_parameters = {
        name
        for name, parameter in signature.parameters.items()
        if parameter.kind
        in {
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
    }
    return {
        key: value
        for key, value in request_payload.items()
        if key in accepted_parameters
    }


def task_from_snapshot(payload: dict) -> Task:
    request_payload = payload.get("request_payload")
    if not isinstance(request_payload, dict):
        raise ValueError("Persisted task snapshot is missing request_payload")

    status = str(payload.get("status") or "pending")
    if task_store.redis_task_backend_enabled() and status == "pending":
        status = "queued"
    return Task(
        id=str(payload["id"]),
        request=AnalysisRequest(
            **_analysis_request_constructor_payload(request_payload)
        ),
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
        hydrate_provider_credentials(task.request.llm_provider)
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

        check_task_canceled(task_id)
        publication = report_publication.publish_analysis_report(
            report_publication.ReportPublicationRequest(
                task_id=task_id,
                request=task.request,
                final_state=final_state,
                temp_dir=temp_dir,
                owner_user_id=task.owner_user_id,
                tenant_id=task.tenant_id,
                report_visibility=task.report_visibility,
            ),
            adapters=report_publication.ReportPublicationAdapters(
                save_report_to_disk=save_report_to_disk,
                build_decision_card=build_decision_card,
                build_fallback_decision_card=build_fallback_decision_card,
                save_decision_card=save_decision_card,
                write_search_evidence=write_search_evidence_artifact,
                storage_backend_is_remote=storage_backend_is_remote,
                upload_directory=storage.upload_directory,
                check_canceled=lambda: check_task_canceled(task_id),
            ),
        )
        report_id = publication.report_id

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
        task_lifecycle.enqueue_task(
            kind="analysis",
            task_id=task_id,
            task=task,
            progress=task_lifecycle.queued_progress(
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
            save_task=save_task,
            queued_at=now_iso,
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
    return report_publication.storage_backend_is_remote()
