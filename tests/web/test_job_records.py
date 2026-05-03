from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from diverge.runner import AnalysisRequest
from web.backend import auth, job_records
from web.backend.runtime import analysis_tasks, data_sync_tasks, screener_tasks


def _enable_test_db(tmp_path: Path):
    return patch.dict(
        os.environ,
        {
            "AUTH_ENABLED": "true",
            "AUTH_MODE": "required",
            "DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'jobs.db'}",
            "AUTH_BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
            "AUTH_BOOTSTRAP_ADMIN_PASSWORD": "AdminPass123",
        },
        clear=False,
    )


def test_job_records_upsert_and_list_active_records(tmp_path):
    with _enable_test_db(tmp_path):
        auth.reset_runtime_state()
        auth.create_all_for_testing()

        job_records.upsert_job_record(
            kind="data_sync",
            task_id="sync-1",
            status="running",
            request_payload={"markets": ["cn"], "as_of_date": "2026-04-29"},
            owner_user_id="admin-user",
            tenant_id="tenant-a",
            started_at="2026-04-29T13:31:45+00:00",
        )

        active = job_records.list_active_job_records(tenant_id="tenant-a")

    assert len(active) == 1
    assert active[0]["id"] == "sync-1"
    assert active[0]["kind"] == "data_sync"
    assert active[0]["status"] == "running"
    assert active[0]["request_payload"]["markets"] == ["cn"]


def test_recover_stale_running_job_records_marks_them_failed(tmp_path):
    with _enable_test_db(tmp_path):
        auth.reset_runtime_state()
        auth.create_all_for_testing()
        job_records.upsert_job_record(
            kind="data_sync",
            task_id="sync-stale",
            status="running",
            request_payload={"markets": ["cn"]},
            owner_user_id="admin-user",
            tenant_id="tenant-a",
            started_at="2026-04-29T13:31:45+00:00",
        )

        recovered = job_records.recover_stale_running_job_records()
        record = job_records.get_job_record("sync-stale")

    assert recovered == 1
    assert record is not None
    assert record["status"] == "failed"
    assert "restarted" in record["error"].lower()
    assert record["finished_at"] is not None


def test_runtime_task_saves_dual_write_job_records(tmp_path):
    with _enable_test_db(tmp_path):
        auth.reset_runtime_state()
        auth.create_all_for_testing()
        data_sync_tasks._save_task(
            data_sync_tasks.DataSyncTask(
                id="sync-job",
                sync_type="ohlcv",
                request_payload={"markets": ["cn"]},
                status="running",
                owner_user_id="admin-user",
                tenant_id="tenant-a",
                started_at="2026-04-29T13:31:45+00:00",
            )
        )
        analysis_tasks.save_task(
            analysis_tasks.Task(
                id="analysis-job",
                request=AnalysisRequest(
                    ticker="AAPL",
                    analysis_date="2026-04-29",
                    analysts=["market"],
                    research_depth=1,
                    llm_provider="openai",
                    quick_think_llm="gpt-5-mini",
                    deep_think_llm="gpt-5.2",
                    output_language="en",
                    openai_reasoning_effort="medium",
                ),
                status="queued",
                owner_user_id="admin-user",
                tenant_id="tenant-a",
                queued_at="2026-04-29T13:31:45+00:00",
            )
        )
        screener_tasks.save_screener_task(
            screener_tasks.ScreenerTask(
                id="screener-job",
                request_payload={"markets": ["us"]},
                config_payload={"markets": ["us"]},
                status="completed",
                run_id="run-1",
                owner_user_id="admin-user",
                tenant_id="tenant-a",
                finished_at="2026-04-29T13:31:45+00:00",
            )
        )

        sync_record = job_records.get_job_record("sync-job")
        analysis_record = job_records.get_job_record("analysis-job")
        screener_record = job_records.get_job_record("screener-job")

    assert sync_record["kind"] == "data_sync"
    assert sync_record["status"] == "running"
    assert analysis_record["kind"] == "analysis"
    assert analysis_record["status"] == "queued"
    assert screener_record["kind"] == "screener"
    assert screener_record["status"] == "completed"
    assert screener_record["result_summary"] == {"run_id": "run-1"}


def test_production_task_state_requires_database_url_and_redis():
    with patch.dict(
        os.environ,
        {
            "APP_ENV": "production",
            "AUTH_ENABLED": "true",
            "AUTH_MODE": "required",
        },
        clear=True,
    ):
        try:
            job_records.validate_task_runtime_settings()
        except RuntimeError as exc:
            message = str(exc)
        else:
            raise AssertionError("expected production task state validation to fail")

    assert "DATABASE_URL" in message
    assert "TASK_BACKEND=redis" in message
