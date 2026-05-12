from __future__ import annotations

import time
import uuid
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from web.backend.runtime import task_store
from web.backend.runtime.task_logging import (
    current_worker_id,
    log_task_event,
    task_process_fields,
)

TASK_KINDS = task_store.TASK_KINDS
logger = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _scheduler_lock(store) -> Iterator[bool]:
    client = getattr(store, "client", None)
    prefix = getattr(store, "prefix", "diverge")
    if client is None:
        yield True
        return

    token = uuid.uuid4().hex
    lock_key = f"{prefix}:scheduler:lock"
    acquired = bool(client.set(lock_key, token, nx=True, px=5000))
    try:
        yield acquired
    finally:
        if acquired:
            try:
                client.eval(
                    "if redis.call('GET', KEYS[1]) == ARGV[1] "
                    "then return redis.call('DEL', KEYS[1]) else return 0 end",
                    1,
                    lock_key,
                    token,
                )
            except Exception:
                pass


def promote_due_tasks(
    store=None, *, now_ts: float | None = None
) -> list[tuple[str, str]]:
    resolved_store = store or task_store.get_task_store()
    current_ts = time.time() if now_ts is None else now_ts
    promoted: list[tuple[str, str]] = []
    for kind in TASK_KINDS:
        for task_id in resolved_store.promote_due_delayed(kind, current_ts):
            payload = resolved_store.get_task(kind, task_id)
            if payload is None or payload.get("status") in task_store.TERMINAL_STATUSES:
                resolved_store.remove_task_refs(kind, task_id)
                continue
            payload["status"] = "queued"
            payload["queued_at"] = _utc_iso()
            payload["blocked_reason"] = None
            payload["blocked_vendor"] = None
            payload["blocked_until"] = None
            resolved_store.save_task(kind, task_id, payload, enqueue=True)
            resolved_store.append_event(
                kind,
                task_id,
                {
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "status": "queued",
                    "stage_status": {},
                    "agent_status": {},
                    "current_agent": None,
                    "message": "Task returned to the execution queue.",
                },
            )
            log_task_event(
                logger,
                "task_queue_promoted",
                kind=kind,
                task_id=task_id,
                task=payload,
            )
            promoted.append((kind, task_id))
    return promoted


def claim_next_task(*, timeout: int = 5) -> tuple[str, str] | None:
    if not task_store.redis_task_backend_enabled():
        return None
    store = task_store.get_task_store()
    promote_due_tasks(store)

    with _scheduler_lock(store) as acquired:
        if not acquired:
            if timeout > 0:
                time.sleep(min(timeout, 1))
            return None
        return _claim_next_locked(store)


def _claim_next_locked(store) -> tuple[str, str] | None:
    global_running_limit = task_store.get_global_running_limit()
    running_total = store.count_running()
    if running_total >= global_running_limit:
        return None

    slots_remaining = global_running_limit - running_total
    analysis_running = store.count_running("analysis")
    candidates = {
        kind: candidate
        for kind in TASK_KINDS
        if (candidate := _first_eligible_task(store, kind)) is not None
    }
    if not candidates:
        return None
    analysis_candidate = candidates.get("analysis")
    if (
        slots_remaining <= 1
        and analysis_running == 0
        and analysis_candidate is not None
    ):
        return _mark_claimed(store, "analysis", analysis_candidate)
    kind, task_id = min(
        candidates.items(),
        key=lambda item: _task_sort_key(store, item[0], item[1]),
    )
    return _mark_claimed(store, kind, task_id)


def claim_next_kind(kind: str, *, timeout: int = 5) -> str | None:
    if kind not in TASK_KINDS or not task_store.redis_task_backend_enabled():
        return None
    store = task_store.get_task_store()
    promote_due_tasks(store)

    with _scheduler_lock(store) as acquired:
        if not acquired:
            if timeout > 0:
                time.sleep(min(timeout, 1))
            return None
        if store.count_running() >= task_store.get_global_running_limit():
            return None
        if kind != "analysis":
            slots_remaining = (
                task_store.get_global_running_limit() - store.count_running()
            )
            analysis_candidate = _first_eligible_task(store, "analysis")
            if (
                slots_remaining <= 1
                and store.count_running("analysis") == 0
                and analysis_candidate is not None
            ):
                return None
        candidate = _first_eligible_task(store, kind)
        if candidate is None:
            return None
        claimed = _mark_claimed(store, kind, candidate)
        return claimed[1] if claimed is not None else None


def _first_eligible_task(store, kind: str) -> str | None:
    user_running_limit = task_store.get_user_running_limit()
    for task_id in store.queue_ids(kind):
        payload = store.get_task(kind, task_id)
        if payload is None or payload.get("status") in task_store.TERMINAL_STATUSES:
            store.remove_task_refs(kind, task_id)
            continue
        if payload.get("status") not in task_store.QUEUED_STATUSES:
            continue
        owner_user_id = payload.get("owner_user_id")
        if store.count_running_by_owner(owner_user_id) >= user_running_limit:
            continue
        return task_id
    return None


def _task_sort_key(store, kind: str, task_id: str | None) -> tuple[str, str, str]:
    if task_id is None:
        return ("9999-12-31T23:59:59+00:00", kind, "")
    payload = store.get_task(kind, task_id) or {}
    timestamp = (
        payload.get("queued_at")
        or payload.get("created_at")
        or payload.get("created")
        or "9999-12-31T23:59:59+00:00"
    )
    return (str(timestamp), kind, task_id)


def _mark_claimed(store, kind: str, task_id: str) -> tuple[str, str] | None:
    if not store.claim_ready(kind, task_id):
        return None
    payload = store.get_task(kind, task_id)
    if payload is None:
        store.ack(kind, task_id)
        return None
    now_iso = _utc_iso()
    payload["status"] = "running"
    payload["started_at"] = now_iso
    payload["worker_claimed_at"] = int(time.time())
    payload["worker_id"] = current_worker_id()
    payload["queue_position"] = None
    store.save_task(kind, task_id, payload, enqueue=False)
    store.append_event(
        kind,
        task_id,
        {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "status": "running",
            "stage_status": {},
            "agent_status": {},
            "current_agent": None,
            "message": "Task started.",
        },
    )
    _upsert_claimed_job_record(kind, task_id, payload, now_iso)
    log_task_event(
        logger,
        "task_queue_claimed",
        kind=kind,
        task_id=task_id,
        task=payload,
    )
    return kind, task_id


def _upsert_claimed_job_record(
    kind: str,
    task_id: str,
    payload: dict,
    started_at: str,
) -> None:
    from web.backend import job_records

    job_records.upsert_job_record(
        kind=kind,
        task_id=task_id,
        status="running",
        request_payload=payload.get("request_payload"),
        owner_user_id=payload.get("owner_user_id"),
        tenant_id=payload.get("tenant_id"),
        created_at=payload.get("created_at"),
        queued_at=payload.get("queued_at"),
        started_at=started_at,
        heartbeat_at=started_at,
        worker_id=task_process_fields()["worker_id"],
    )
