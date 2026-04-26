from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from web.backend.runtime import task_store

TASK_KINDS = ("analysis", "screener")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _scheduler_lock(store) -> Iterator[bool]:
    client = getattr(store, "client", None)
    prefix = getattr(store, "prefix", "tradingagents")
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


def promote_due_tasks(store=None, *, now_ts: float | None = None) -> list[tuple[str, str]]:
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
    analysis_candidate = _first_eligible_task(store, "analysis")
    screener_candidate = _first_eligible_task(store, "screener")
    if analysis_candidate is None and screener_candidate is None:
        return None
    if analysis_candidate is not None and screener_candidate is None:
        return _mark_claimed(store, "analysis", analysis_candidate)
    if screener_candidate is not None and analysis_candidate is None:
        return _mark_claimed(store, "screener", screener_candidate)
    if slots_remaining <= 1 and analysis_running == 0:
        return _mark_claimed(store, "analysis", analysis_candidate)
    if _task_sort_key(store, "analysis", analysis_candidate) <= _task_sort_key(
        store, "screener", screener_candidate
    ):
        return _mark_claimed(store, "analysis", analysis_candidate)
    return _mark_claimed(store, "screener", screener_candidate)


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
        if kind == "screener":
            slots_remaining = task_store.get_global_running_limit() - store.count_running()
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
    return kind, task_id
