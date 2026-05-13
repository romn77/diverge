from __future__ import annotations

from types import SimpleNamespace

from web.backend.runtime import task_lifecycle


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
