from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from diverge.common.json_io import write_json_atomic
from diverge.opportunity.radar import plan_radar_run_id, run_opportunity_radar
from diverge.opportunity.storage import opportunity_runs_dir
from web.backend import app_config, auth, opportunity_models, storage
from web.backend.runtime import task_lifecycle, task_store

KIND = "opportunity"
_tasks: dict[str, "OpportunityTask"] = {}
_lock = threading.Lock()


@dataclass
class OpportunityTask:
    id: str
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
        return self.__dict__.copy()


def _utc_iso() -> str:
    return task_lifecycle.utc_iso()


def _event(status: str, message: str) -> dict[str, Any]:
    return task_lifecycle.progress_event(
        message,
        status=status,
        stage_status={"Radar": status},
        agent_status={},
        current_agent="opportunity_radar",
    )


def _state_dir() -> Path:
    return app_config.OPPORTUNITY_TASKS_DIR / "active"


def _task_path(task_id: str) -> Path:
    return _state_dir() / task_id / "task.json"


def _from_payload(payload: dict[str, Any]) -> OpportunityTask:
    return OpportunityTask(
        **{
            key: value
            for key, value in payload.items()
            if key in OpportunityTask.__dataclass_fields__
        }
    )


def save_task(task: OpportunityTask) -> None:
    task_lifecycle.upsert_job_record(
        kind=KIND,
        task=task,
        request_payload=task.request_payload,
        result_summary=task.result,
    )
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().save_task(KIND, task.id, task.to_dict())
        return
    with _lock:
        _tasks[task.id] = task
    if task.status in task_store.TERMINAL_STATUSES:
        return
    write_json_atomic(_task_path(task.id), task.to_dict())


def get_task(task_id: str) -> OpportunityTask:
    if task_store.redis_task_backend_enabled():
        payload = task_store.get_task_store().get_task(KIND, task_id)
        if payload is None:
            raise HTTPException(
                status_code=404, detail=f"Opportunity task '{task_id}' not found"
            )
        task = _from_payload(payload)
        task.queue_position = task_store.get_task_store().queue_position(KIND, task_id)
        task.progress_events = task_store.get_task_store().list_events(KIND, task_id)
        return task
    with _lock:
        task = _tasks.get(task_id)
    if task is None:
        path = _task_path(task_id)
        if path.is_file():
            task = _from_payload(json.loads(path.read_text(encoding="utf-8")))
    if task is None:
        raise HTTPException(
            status_code=404, detail=f"Opportunity task '{task_id}' not found"
        )
    return task


def list_tasks() -> list[OpportunityTask]:
    if task_store.redis_task_backend_enabled():
        return [
            _from_payload(payload)
            for payload in task_store.get_task_store().list_tasks(KIND)
        ]
    with _lock:
        return sorted(
            _tasks.values(), key=lambda task: task.created_at or "", reverse=True
        )


def _append(task: OpportunityTask, progress: dict[str, Any]) -> None:
    task.latest_progress = progress
    task.progress_events.append(progress)
    save_task(task)
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().append_event(KIND, task.id, progress)


def run_opportunity_task(task_id: str) -> None:
    task = get_task(task_id)
    task.status = "running"
    task.started_at = task.started_at or _utc_iso()
    _append(task, _event("running", "Opportunity Radar is running."))
    try:
        result = run_opportunity_radar(
            task.request_payload,
            owner_user_id=task.owner_user_id,
            tenant_id=task.tenant_id,
            project_root=app_config.PROJECT_ROOT,
        )
        meta_path = (
            Path(result["run_dir"]) / "run_meta.json" if result.get("run_dir") else None
        )
        if auth.auth_enabled() and meta_path is not None and meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            with auth.db_session() as db:
                opportunity_models.upsert_opportunity_run(
                    db,
                    run_id=str(meta.get("run_id")),
                    tenant_id=task.tenant_id,
                    owner_user_id=task.owner_user_id,
                    market=str(meta.get("market") or "cn"),
                    trade_date=str(meta.get("trade_date") or ""),
                    config_hash=str(meta.get("config_hash") or ""),
                    revision=int(meta.get("revision") or 1),
                    status=str(
                        meta.get("status") or result.get("status") or "completed"
                    ),
                    candidate_count=int(meta.get("candidate_count") or 0),
                    generated_at=str(meta.get("generated_at") or _utc_iso()),
                    storage_path=str(result.get("run_dir") or ""),
                    artifact_manifest=meta.get("artifact_manifest") or {},
                )
        task = get_task(task_id)
        task.status = "completed"
        task.finished_at = _utc_iso()
        task.result = result
        _append(task, _event("completed", "Opportunity Radar completed."))
        if storage.os.environ.get(
            "STORAGE_BACKEND", "local"
        ).strip().lower() != "local" and result.get("run_dir"):
            storage.upload_directory(
                Path(result["run_dir"]), f"opportunity/runs/{result['run_id']}"
            )
    except Exception as exc:
        task = get_task(task_id)
        task.status = "failed"
        task.finished_at = _utc_iso()
        task.error = str(exc)
        _append(task, _event("failed", "Opportunity Radar failed."))
        raise


def get_progress_events(task_id: str, cursor: int = 0) -> list[dict[str, Any]]:
    events = get_task(task_id).progress_events
    return events[max(int(cursor), 0) :]


def _cancel_requested_progress(task: OpportunityTask) -> dict[str, Any]:
    return _event("running", "Opportunity Radar cancellation requested.")


def _canceled_progress(task: OpportunityTask) -> dict[str, Any]:
    return _event("canceled", "Opportunity Radar canceled.")


def cancel_opportunity_task(task_id: str) -> str:
    task = get_task(task_id)
    if task.status in task_store.TERMINAL_STATUSES:
        return "already_terminal"
    return task_lifecycle.apply_cancel_transition(
        kind=KIND,
        task_id=task_id,
        task=task,
        now_iso=_utc_iso(),
        cancel_requested_progress=_cancel_requested_progress,
        canceled_progress=_canceled_progress,
        save_task=save_task,
    )


def _tenant_scoped_payload(
    request_payload: dict[str, Any], tenant_id: str | None
) -> dict[str, Any]:
    payload = dict(request_payload)
    if tenant_id is not None and not payload.get("tenant_id"):
        payload["tenant_id"] = tenant_id
    return payload


def _tasks_for_idempotency() -> list[OpportunityTask]:
    if task_store.redis_task_backend_enabled():
        return [
            _from_payload(payload)
            for payload in task_store.get_task_store().list_tasks(KIND)
        ]
    with _lock:
        return list(_tasks.values())


def _matching_active_task(
    *, planned_run_id: str, request_payload: dict[str, Any], tenant_id: str | None
) -> OpportunityTask | None:
    for existing in _tasks_for_idempotency():
        if existing.request_payload.get("force"):
            continue
        existing_run_id, _, _, _, _ = plan_radar_run_id(existing.request_payload)
        if (
            existing_run_id == planned_run_id
            and existing.status in task_store.ACTIVE_STATUSES
            and existing.tenant_id == tenant_id
        ):
            return existing
    return None


def _cached_run_matches_tenant(run_meta: Path, tenant_id: str | None) -> bool:
    if not run_meta.is_file():
        return False
    if tenant_id is None:
        return True
    try:
        payload = json.loads(run_meta.read_text(encoding="utf-8"))
    except Exception:
        return False
    return payload.get("tenant_id") in {None, tenant_id}


def create_opportunity_task(
    *,
    request_payload: dict[str, Any],
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    request_payload = _tenant_scoped_payload(request_payload, tenant_id)
    planned_run_id, _, _, _, _ = plan_radar_run_id(request_payload)
    if not request_payload.get("force"):
        run_meta = (
            opportunity_runs_dir(app_config.PROJECT_ROOT)
            / planned_run_id
            / "run_meta.json"
        )
        if _cached_run_matches_tenant(run_meta, tenant_id):
            return {
                "task_id": "",
                "run_id": planned_run_id,
                "status": "completed",
                "cached": True,
            }
        existing = _matching_active_task(
            planned_run_id=planned_run_id,
            request_payload=request_payload,
            tenant_id=tenant_id,
        )
        if existing is not None:
            return {
                "task_id": existing.id,
                "run_id": planned_run_id,
                "status": existing.status,
                "cached": False,
            }
    task_id = uuid.uuid4().hex
    now = _utc_iso()
    task = OpportunityTask(
        id=task_id,
        request_payload=request_payload,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        created_at=now,
    )
    if task_store.redis_task_backend_enabled():
        task_lifecycle.enqueue_task(
            kind=KIND,
            task_id=task_id,
            task=task,
            progress=_event("queued", "Opportunity Radar task queued."),
            save_task=save_task,
            queued_at=now,
        )
        return {"task_id": task_id, "run_id": planned_run_id, "status": "queued"}
    with _lock:
        _tasks[task_id] = task
    save_task(task)
    threading.Thread(target=run_opportunity_task, args=(task_id,), daemon=True).start()
    return {"task_id": task_id, "run_id": planned_run_id, "status": "pending"}


def restore_persisted_opportunity_tasks() -> None:
    if task_store.redis_task_backend_enabled():
        task_store.get_task_store().recover_processing(KIND)
