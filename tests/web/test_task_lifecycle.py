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
