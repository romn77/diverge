from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from web.backend.runtime import task_lifecycle


class LockProbe:
    def __init__(self):
        self.locked = False
        self.entered = False

    def __enter__(self):
        self.entered = True
        self.locked = True

    def __exit__(self, exc_type, exc, tb):
        self.locked = False


def test_progress_event_can_preserve_explicit_current_agent_none():
    event = task_lifecycle.progress_event(
        "Task queued.",
        status="queued",
        stage_status={"Analysts": "not_started"},
        agent_status={},
        current_agent=None,
        include_current_agent=True,
    )

    assert event["status"] == "queued"
    assert event["message"] == "Task queued."
    assert event["current_agent"] is None
    assert event["timestamp"]


def test_apply_status_transition_sets_running_and_terminal_timestamps():
    task = SimpleNamespace(
        status="pending",
        started_at=None,
        finished_at=None,
        error=None,
    )

    task_lifecycle.apply_status_transition(
        task,
        "running",
        terminal_statuses={"completed", "failed"},
        now_iso="2026-05-13T01:02:03+00:00",
    )
    assert task.status == "running"
    assert task.started_at == "2026-05-13T01:02:03+00:00"
    assert task.finished_at is None

    task_lifecycle.apply_status_transition(
        task,
        "failed",
        terminal_statuses={"completed", "failed"},
        error="boom",
        now_iso="2026-05-13T01:03:03+00:00",
    )
    assert task.status == "failed"
    assert task.started_at == "2026-05-13T01:02:03+00:00"
    assert task.finished_at == "2026-05-13T01:03:03+00:00"
    assert task.error == "boom"


def test_append_progress_event_updates_local_task_and_persists_after_lock(monkeypatch):
    monkeypatch.setattr(
        task_lifecycle.task_store,
        "redis_task_backend_enabled",
        lambda: False,
    )
    lock = LockProbe()
    progress = {"message": "halfway", "status": "running"}
    task = SimpleNamespace(latest_progress=None, progress_events=[])
    local_tasks = {"task-1": task}
    persisted = {}

    returned = task_lifecycle.append_progress_event(
        kind="analysis",
        task_id="task-1",
        progress=progress,
        get_task=lambda task_id: None,
        local_tasks=local_tasks,
        local_lock=lock,
        save_redis_task=lambda task: None,
        save_local_task=lambda saved_task: persisted.update(
            task=saved_task,
            latest_progress=saved_task.latest_progress,
            lock_was_released=not lock.locked,
        ),
    )

    assert returned is task
    assert lock.entered
    assert task.latest_progress == progress
    assert task.progress_events == [progress]
    assert persisted == {
        "task": task,
        "latest_progress": progress,
        "lock_was_released": True,
    }


def test_append_progress_event_saves_redis_task_and_replay_event(monkeypatch):
    monkeypatch.setattr(
        task_lifecycle.task_store,
        "redis_task_backend_enabled",
        lambda: True,
    )
    progress = {"message": "tick", "status": "running"}
    task = SimpleNamespace(latest_progress=None, progress_events=[])
    saved = {}
    appended = {}
    store = SimpleNamespace(
        append_event=lambda kind, task_id, payload: appended.update(
            kind=kind,
            task_id=task_id,
            payload=payload,
        )
    )
    monkeypatch.setattr(task_lifecycle.task_store, "get_task_store", lambda: store)

    returned = task_lifecycle.append_progress_event(
        kind="screener",
        task_id="task-2",
        progress=progress,
        get_task=lambda task_id: task,
        local_tasks={},
        local_lock=LockProbe(),
        save_redis_task=lambda saved_task: saved.update(task=saved_task),
    )

    assert returned is task
    assert task.latest_progress == progress
    assert task.progress_events == [progress]
    assert saved == {"task": task}
    assert appended == {
        "kind": "screener",
        "task_id": "task-2",
        "payload": progress,
    }


def test_apply_cancel_transition_requests_cancel_for_running_task(monkeypatch):
    monkeypatch.setattr(
        task_lifecycle.task_store,
        "redis_task_backend_enabled",
        lambda: False,
    )
    task = SimpleNamespace(
        status="running",
        cancel_requested_at=None,
        canceled_at=None,
        finished_at=None,
        latest_progress=None,
        progress_events=[],
    )
    saved = {}

    transition = task_lifecycle.apply_cancel_transition(
        kind="analysis",
        task_id="task-1",
        task=task,
        now_iso="2026-05-13T01:02:03+00:00",
        cancel_requested_progress=lambda task: {
            "status": "running",
            "message": "cancel requested",
        },
        canceled_progress=lambda task: {"status": "canceled"},
        save_task=lambda saved_task: saved.update(task=saved_task),
    )

    assert transition == "requested"
    assert task.status == "running"
    assert task.cancel_requested_at == "2026-05-13T01:02:03+00:00"
    assert task.canceled_at is None
    assert task.finished_at is None
    assert task.latest_progress == {
        "status": "running",
        "message": "cancel requested",
    }
    assert task.progress_events == [task.latest_progress]
    assert saved == {"task": task}


def test_apply_cancel_transition_cancels_queued_task_and_removes_redis_refs(
    monkeypatch,
):
    monkeypatch.setattr(
        task_lifecycle.task_store,
        "redis_task_backend_enabled",
        lambda: True,
    )
    task = SimpleNamespace(
        status="queued",
        cancel_requested_at=None,
        canceled_at=None,
        finished_at=None,
        latest_progress=None,
        progress_events=[],
        error="old error",
        result={"old": True},
    )
    saved = {}
    removed = {}
    appended = {}
    store = SimpleNamespace(
        remove_task_refs=lambda kind, task_id: removed.update(
            kind=kind,
            task_id=task_id,
        ),
        append_event=lambda kind, task_id, payload: appended.update(
            kind=kind,
            task_id=task_id,
            payload=payload,
        ),
    )
    monkeypatch.setattr(task_lifecycle.task_store, "get_task_store", lambda: store)

    transition = task_lifecycle.apply_cancel_transition(
        kind="data_sync",
        task_id="task-3",
        task=task,
        now_iso="2026-05-13T01:02:03+00:00",
        cancel_requested_progress=lambda task: {"status": "running"},
        canceled_progress=lambda task: {
            "status": "canceled",
            "message": "canceled",
        },
        save_task=lambda saved_task: saved.update(task=saved_task),
        clear_error=True,
        clear_result=True,
    )

    assert transition == "canceled"
    assert task.status == "canceled"
    assert task.cancel_requested_at == "2026-05-13T01:02:03+00:00"
    assert task.canceled_at == "2026-05-13T01:02:03+00:00"
    assert task.finished_at == "2026-05-13T01:02:03+00:00"
    assert task.error is None
    assert task.result is None
    assert task.latest_progress == {"status": "canceled", "message": "canceled"}
    assert task.progress_events == [task.latest_progress]
    assert saved == {"task": task}
    assert removed == {"kind": "data_sync", "task_id": "task-3"}
    assert appended == {
        "kind": "data_sync",
        "task_id": "task-3",
        "payload": task.latest_progress,
    }


def test_apply_canceled_completion_transition_saves_and_replays_event(monkeypatch):
    monkeypatch.setattr(
        task_lifecycle.task_store,
        "redis_task_backend_enabled",
        lambda: True,
    )
    task = SimpleNamespace(
        status="running",
        canceled_at=None,
        finished_at=None,
        error="old error",
        result={"old": True},
        latest_progress=None,
        progress_events=[],
    )
    saved = {}
    appended = {}
    store = SimpleNamespace(
        append_event=lambda kind, task_id, payload: appended.update(
            kind=kind,
            task_id=task_id,
            payload=payload,
        )
    )
    monkeypatch.setattr(task_lifecycle.task_store, "get_task_store", lambda: store)

    progress = task_lifecycle.apply_canceled_completion_transition(
        kind="data_sync",
        task_id="task-3b",
        task=task,
        canceled_progress=lambda canceled_task: {
            "status": canceled_task.status,
            "finished_at": canceled_task.finished_at,
        },
        save_task=lambda saved_task: saved.update(task=saved_task),
        now_iso="2026-05-13T01:02:03+00:00",
        clear_result=True,
    )

    assert progress == {
        "status": "canceled",
        "finished_at": "2026-05-13T01:02:03+00:00",
    }
    assert task.status == "canceled"
    assert task.canceled_at == "2026-05-13T01:02:03+00:00"
    assert task.finished_at == "2026-05-13T01:02:03+00:00"
    assert task.error is None
    assert task.result is None
    assert task.latest_progress == progress
    assert task.progress_events == [progress]
    assert saved == {"task": task}
    assert appended == {
        "kind": "data_sync",
        "task_id": "task-3b",
        "payload": progress,
    }


def test_blocked_until_timestamp_handles_missing_and_naive_values(monkeypatch):
    monkeypatch.setattr(
        task_lifecycle,
        "utc_now",
        lambda: datetime(2026, 5, 13, 1, 2, 3, tzinfo=timezone.utc),
    )

    assert task_lifecycle.blocked_until_timestamp(None) == (
        datetime(2026, 5, 13, 2, 2, 3, tzinfo=timezone.utc).timestamp()
    )
    assert task_lifecycle.blocked_until_timestamp("2026-05-13T01:02:03") == (
        datetime(2026, 5, 13, 1, 2, 3, tzinfo=timezone.utc).timestamp()
    )
    assert task_lifecycle.blocked_until_timestamp("not-a-date") == (
        datetime(2026, 5, 13, 2, 2, 3, tzinfo=timezone.utc).timestamp()
    )


def test_apply_quota_wait_transition_sets_fields_before_progress_and_delays_redis(
    monkeypatch,
):
    monkeypatch.setattr(
        task_lifecycle.task_store,
        "redis_task_backend_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        task_lifecycle,
        "blocked_until_timestamp",
        lambda blocked_until: 123.0,
    )
    task = SimpleNamespace(
        status="running",
        blocked_reason=None,
        blocked_vendor=None,
        blocked_until=None,
        latest_progress=None,
        progress_events=[],
    )
    saved = {}
    delayed = {}
    appended = {}
    store = SimpleNamespace(
        delay=lambda kind, task_id, run_at: delayed.update(
            kind=kind,
            task_id=task_id,
            run_at=run_at,
        ),
        append_event=lambda kind, task_id, payload: appended.update(
            kind=kind,
            task_id=task_id,
            payload=payload,
        ),
    )
    monkeypatch.setattr(task_lifecycle.task_store, "get_task_store", lambda: store)

    returned = task_lifecycle.apply_quota_wait_transition(
        kind="analysis",
        task_id="task-4",
        task=task,
        reason="rate limit",
        vendor="vendor-a",
        blocked_until="2026-05-13T02:00:00+00:00",
        build_progress=lambda waiting_task: {
            "status": waiting_task.status,
            "message": f"waiting for {waiting_task.blocked_vendor}",
        },
        save_task=lambda saved_task: saved.update(task=saved_task),
    )

    assert returned is task
    assert task.status == "waiting_for_quota"
    assert task.blocked_reason == "rate limit"
    assert task.blocked_vendor == "vendor-a"
    assert task.blocked_until == "2026-05-13T02:00:00+00:00"
    assert task.latest_progress == {
        "status": "waiting_for_quota",
        "message": "waiting for vendor-a",
    }
    assert task.progress_events == [task.latest_progress]
    assert saved == {"task": task}
    assert delayed == {"kind": "analysis", "task_id": "task-4", "run_at": 123.0}
    assert appended == {
        "kind": "analysis",
        "task_id": "task-4",
        "payload": task.latest_progress,
    }


def test_apply_recovered_failure_transition_can_replace_local_progress(
    monkeypatch,
):
    monkeypatch.setattr(
        task_lifecycle.task_store,
        "redis_task_backend_enabled",
        lambda: False,
    )
    task = SimpleNamespace(
        id="task-5",
        status="running",
        error=None,
        finished_at=None,
        latest_progress={"status": "running"},
        progress_events=[{"status": "running"}],
    )

    progress = task_lifecycle.apply_recovered_failure_transition(
        kind="analysis",
        task=task,
        error="Recovered after restart.",
        build_progress=lambda failed_task: {
            "status": failed_task.status,
            "message": failed_task.error,
        },
        replace_progress_events=True,
    )

    assert progress == {"status": "failed", "message": "Recovered after restart."}
    assert task.status == "failed"
    assert task.error == "Recovered after restart."
    assert task.finished_at is None
    assert task.latest_progress == progress
    assert task.progress_events == [progress]


def test_apply_failure_transition_marks_finished_and_replays_event(monkeypatch):
    monkeypatch.setattr(
        task_lifecycle.task_store,
        "redis_task_backend_enabled",
        lambda: True,
    )
    task = SimpleNamespace(
        id="task-5b",
        status="running",
        error=None,
        finished_at=None,
        latest_progress=None,
        progress_events=[],
    )
    saved = {}
    appended = {}
    store = SimpleNamespace(
        append_event=lambda kind, task_id, payload: appended.update(
            kind=kind,
            task_id=task_id,
            payload=payload,
        )
    )
    monkeypatch.setattr(task_lifecycle.task_store, "get_task_store", lambda: store)

    progress = task_lifecycle.apply_failure_transition(
        kind="analysis",
        task=task,
        error="failed loudly",
        build_progress=lambda failed_task: {
            "status": failed_task.status,
            "message": failed_task.error,
            "finished_at": failed_task.finished_at,
        },
        save_task=lambda saved_task: saved.update(task=saved_task),
        now_iso="2026-05-13T01:02:03+00:00",
        append_redis_event=True,
    )

    assert progress == {
        "status": "failed",
        "message": "failed loudly",
        "finished_at": "2026-05-13T01:02:03+00:00",
    }
    assert task.status == "failed"
    assert task.error == "failed loudly"
    assert task.finished_at == "2026-05-13T01:02:03+00:00"
    assert task.latest_progress == progress
    assert task.progress_events == [progress]
    assert saved == {"task": task}
    assert appended == {"kind": "analysis", "task_id": "task-5b", "payload": progress}


def test_apply_recovered_failure_transition_saves_and_acks_redis(monkeypatch):
    monkeypatch.setattr(
        task_lifecycle.task_store,
        "redis_task_backend_enabled",
        lambda: True,
    )
    task = SimpleNamespace(
        id="task-6",
        status="running",
        error=None,
        finished_at=None,
        latest_progress=None,
        progress_events=[],
    )
    saved = {}
    appended = {}
    acked = {}
    store = SimpleNamespace(
        append_event=lambda kind, task_id, payload: appended.update(
            kind=kind,
            task_id=task_id,
            payload=payload,
        ),
        ack=lambda kind, task_id: acked.update(kind=kind, task_id=task_id),
    )
    monkeypatch.setattr(task_lifecycle.task_store, "get_task_store", lambda: store)

    progress = task_lifecycle.apply_recovered_failure_transition(
        kind="data_sync",
        task=task,
        error="Recovered after restart.",
        build_progress=lambda failed_task: {
            "status": failed_task.status,
            "finished_at": failed_task.finished_at,
        },
        save_task=lambda saved_task: saved.update(task=saved_task),
        mark_finished=True,
        now_iso="2026-05-13T01:02:03+00:00",
        append_redis_event=True,
        ack_redis_processing=True,
    )

    assert progress == {
        "status": "failed",
        "finished_at": "2026-05-13T01:02:03+00:00",
    }
    assert task.status == "failed"
    assert task.error == "Recovered after restart."
    assert task.finished_at == "2026-05-13T01:02:03+00:00"
    assert task.latest_progress == progress
    assert task.progress_events == [progress]
    assert saved == {"task": task}
    assert appended == {"kind": "data_sync", "task_id": "task-6", "payload": progress}
    assert acked == {"kind": "data_sync", "task_id": "task-6"}


def test_promote_payload_to_queue_clears_blocking_fields(monkeypatch):
    monkeypatch.setattr(
        task_lifecycle,
        "utc_iso",
        lambda: "2026-05-13T01:02:03+00:00",
    )
    payload = {
        "id": "task-7",
        "status": "waiting_for_quota",
        "blocked_reason": "quota",
        "blocked_vendor": "vendor-a",
        "blocked_until": "2026-05-13T02:00:00+00:00",
    }
    saved = {}
    appended = {}
    store = SimpleNamespace(
        save_task=lambda kind, task_id, saved_payload, *, enqueue: saved.update(
            kind=kind,
            task_id=task_id,
            payload=dict(saved_payload),
            enqueue=enqueue,
        ),
        append_event=lambda kind, task_id, event: appended.update(
            kind=kind,
            task_id=task_id,
            event=event,
        ),
    )

    returned = task_lifecycle.promote_payload_to_queue(
        kind="analysis",
        task_id="task-7",
        payload=payload,
        store=store,
    )

    assert returned is payload
    assert payload["status"] == "queued"
    assert payload["queued_at"] == "2026-05-13T01:02:03+00:00"
    assert payload["blocked_reason"] is None
    assert payload["blocked_vendor"] is None
    assert payload["blocked_until"] is None
    assert saved["enqueue"] is True
    assert saved["payload"]["status"] == "queued"
    assert appended["kind"] == "analysis"
    assert appended["task_id"] == "task-7"
    assert appended["event"]["status"] == "queued"


def test_claim_payload_for_worker_projects_running_record(monkeypatch):
    monkeypatch.setattr(
        task_lifecycle,
        "utc_iso",
        lambda: "2026-05-13T01:02:03+00:00",
    )
    monkeypatch.setattr(task_lifecycle.time, "time", lambda: 1234.9)
    monkeypatch.setattr(task_lifecycle, "current_worker_id", lambda: "worker-a")
    upserted = {}
    monkeypatch.setattr(
        task_lifecycle,
        "upsert_job_record",
        lambda **kwargs: upserted.update(kwargs),
    )
    payload = {
        "id": "task-8",
        "status": "queued",
        "request_payload": {"ticker": "SPY"},
        "queue_position": 2,
    }
    saved = {}
    appended = {}
    store = SimpleNamespace(
        save_task=lambda kind, task_id, saved_payload, *, enqueue: saved.update(
            kind=kind,
            task_id=task_id,
            payload=dict(saved_payload),
            enqueue=enqueue,
        ),
        append_event=lambda kind, task_id, event: appended.update(
            kind=kind,
            task_id=task_id,
            event=event,
        ),
    )

    returned = task_lifecycle.claim_payload_for_worker(
        kind="analysis",
        task_id="task-8",
        payload=payload,
        store=store,
    )

    assert returned is payload
    assert payload["status"] == "running"
    assert payload["started_at"] == "2026-05-13T01:02:03+00:00"
    assert payload["worker_claimed_at"] == 1234
    assert payload["worker_id"] == "worker-a"
    assert payload["queue_position"] is None
    assert saved["enqueue"] is False
    assert saved["payload"]["status"] == "running"
    assert appended["kind"] == "analysis"
    assert appended["task_id"] == "task-8"
    assert appended["event"]["status"] == "running"
    assert upserted["kind"] == "analysis"
    assert upserted["task_id"] == "task-8"
    assert upserted["status"] == "running"
    assert upserted["request_payload"] == {"ticker": "SPY"}
    assert upserted["heartbeat_at"] == "2026-05-13T01:02:03+00:00"
    assert upserted["worker_id"] == "worker-a"


def test_upsert_job_record_projects_common_task_fields(monkeypatch):
    captured = {}
    task = SimpleNamespace(
        id="task-1",
        status="running",
        request_payload={"ticker": "MSFT"},
        result={"ok": True},
        error=None,
        owner_user_id="user-1",
        tenant_id="tenant-1",
        created_at="2026-05-13T01:00:00+00:00",
        queued_at="2026-05-13T01:01:00+00:00",
        started_at="2026-05-13T01:02:00+00:00",
        finished_at=None,
    )

    monkeypatch.setattr(
        task_lifecycle.job_records,
        "upsert_job_record",
        lambda **kwargs: captured.update(kwargs),
    )
    monkeypatch.setattr(task_lifecycle, "utc_iso", lambda: "2026-05-13T01:02:30+00:00")
    monkeypatch.setattr(task_lifecycle, "current_worker_id", lambda: "worker-1")

    task_lifecycle.upsert_job_record(kind="analysis", task=task)

    assert captured["kind"] == "analysis"
    assert captured["task_id"] == "task-1"
    assert captured["request_payload"] == {"ticker": "MSFT"}
    assert captured["result_summary"] == {"ok": True}
    assert captured["heartbeat_at"] == "2026-05-13T01:02:30+00:00"
    assert captured["worker_id"] == "worker-1"
