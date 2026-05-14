from web.backend.runtime import screener_stage_trace


def test_pipeline_callback_normalizes_stage_and_builds_extended_message():
    events = []
    canceled_checks = []
    trace = screener_stage_trace.ScreenerStageTrace(
        append_progress=events.append,
        check_canceled=lambda: canceled_checks.append("checked"),
    )

    trace.pipeline_callback(
        "filters",
        2,
        5,
        "MSFT",
        status="cached",
        detail="ready",
    )

    assert len(events) == 1
    progress = events[0]
    assert progress["status"] == "running"
    assert progress["stage_status"] == {
        "Features": "completed",
        "Filters": "processing",
        "Ranking": "not_started",
        "Export": "not_started",
    }
    assert progress["current_agent"] == "MSFT"
    assert progress["message"] == "Filters 2/5 MSFT [cached] ready MSFT"
    assert canceled_checks == ["checked"]


def test_pipeline_callback_ignores_unknown_stage_without_cancel_check():
    events = []
    canceled_checks = []
    trace = screener_stage_trace.ScreenerStageTrace(
        append_progress=events.append,
        check_canceled=lambda: canceled_checks.append("checked"),
    )

    trace.pipeline_callback("unknown", 1, 1)

    assert events == []
    assert canceled_checks == []


def test_failure_progress_clears_processing_stage_and_preserves_completed_stages():
    progress = screener_stage_trace.failure_progress(
        {
            "stage_status": {
                "Features": "completed",
                "Filters": "processing",
                "Ranking": "not_started",
                "Export": "not_started",
            },
            "agent_status": {"MSFT": "running"},
            "current_agent": "MSFT",
        },
        "Screener data is not ready.",
    )

    assert progress["status"] == "failed"
    assert progress["stage_status"] == {
        "Features": "completed",
        "Filters": "not_started",
        "Ranking": "not_started",
        "Export": "not_started",
    }
    assert progress["agent_status"] == {"MSFT": "running"}
    assert progress["current_agent"] == "MSFT"
    assert progress["message"] == "System: Screener data is not ready."
