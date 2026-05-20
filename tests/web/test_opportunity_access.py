from __future__ import annotations

import asyncio
import contextlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from web.backend import app_config, auth
from web.backend.routers import opportunities as opportunities_router
from web.backend.runtime import analysis_tasks, opportunity_tasks, task_store
from web.backend.schemas.opportunities import CandidateAnalyzePayload
from web.backend.services import backtests, opportunities


def _request_with_language(language: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "headers": [(b"x-diverge-ui-language", language.encode("utf-8"))],
        }
    )


def test_opportunity_service_lists_runs_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    assert opportunities.list_runs() == []


def test_backend_lifespan_initializes_opportunity_tables_and_tasks_by_default(
    monkeypatch,
):
    from web.backend import main

    async def run_lifespan_once():
        async with main._app_lifespan(None):
            return None

    patch_targets = [
        "web.backend.main.auth.initialize_auth_runtime",
        "web.backend.main.analysis_limits.initialize_analysis_limits_runtime",
        "web.backend.main.data_sources.initialize_data_source_runtime",
        "web.backend.main.llm_models.initialize_llm_model_runtime",
        "web.backend.main.search_quota.initialize_search_quota_runtime",
        "web.backend.main.report_metadata.initialize_report_metadata_runtime",
        "web.backend.main.screener_runs.initialize_screener_runtime",
        "web.backend.main.screener_results.initialize_screener_result_runtime",
        "web.backend.main.trade_entries.initialize_trade_entries_runtime",
        "web.backend.main.trade_plan_entries.initialize_trade_plan_entries_runtime",
        "web.backend.main.asset_entries.initialize_asset_runtime",
        "web.backend.main.audit.ensure_audit_tables",
        "web.backend.main.job_records.initialize_job_record_runtime",
        "web.backend.main.job_records.recover_stale_running_job_records",
        "web.backend.main.restore_persisted_active_tasks",
        "web.backend.main.restore_persisted_screener_tasks",
        "web.backend.main.restore_persisted_data_sync_tasks",
    ]
    with contextlib.ExitStack() as stack:
        for target in patch_targets:
            stack.enter_context(patch(target))
        stack.enter_context(
            patch(
                "web.backend.main.task_store.redis_task_backend_enabled",
                return_value=False,
            )
        )
        initialize_tables = stack.enter_context(
            patch("web.backend.main.opportunity_models.initialize_opportunity_runtime")
        )
        restore_opportunity = stack.enter_context(
            patch("web.backend.main.restore_persisted_opportunity_tasks")
        )
        restore_backtest = stack.enter_context(
            patch("web.backend.main.restore_persisted_backtest_tasks")
        )
        asyncio.run(run_lifespan_once())

    initialize_tables.assert_called_once()
    restore_opportunity.assert_called_once()
    restore_backtest.assert_called_once()


def test_opportunity_artifacts_are_tenant_scoped(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(auth, "auth_enabled", lambda: True)

    run_dir = tmp_path / "data" / "opportunity" / "runs" / "run-a"
    run_dir.mkdir(parents=True)
    (run_dir / "run_meta.json").write_text(
        json.dumps({"run_id": "run-a", "tenant_id": "tenant-a"}),
        encoding="utf-8",
    )
    (run_dir / "candidate_pool.json").write_text(
        json.dumps({"candidates": [{"symbol": "300001.SZ"}]}),
        encoding="utf-8",
    )

    same_tenant = SimpleNamespace(id="u1", tenant_id="tenant-a")
    other_tenant = SimpleNamespace(id="u2", tenant_id="tenant-b")

    assert (
        opportunities.get_artifact("run-a", "candidates", same_tenant)["candidates"][0][
            "symbol"
        ]
        == "300001.SZ"
    )
    with pytest.raises(HTTPException) as excinfo:
        opportunities.get_artifact("run-a", "candidates", other_tenant)

    assert excinfo.value.status_code == 404


def test_opportunity_candidate_analysis_uses_supported_analyst_keys(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(app_config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(auth, "auth_enabled", lambda: False)
    monkeypatch.setattr(task_store, "redis_task_backend_enabled", lambda: False)
    analysis_tasks.tasks.clear()

    try:
        with patch("web.backend.runtime.analysis_tasks.start_task_thread") as start_task:
            result = opportunities_router.analyze_candidate(
                "300002.SZ",
                CandidateAnalyzePayload(
                    run_id="run-a",
                    analysis_date="2026-05-14",
                    opportunity_context={
                        "source": "opportunity_radar",
                        "symbol": "300002.SZ",
                        "theme": "AI Compute",
                    },
                ),
            )

        task = analysis_tasks.get_task(result["task_id"])
        assert result["status"] == "pending"
        assert task.request.analysts == ["market", "social", "news", "fundamentals"]
        assert "sentiment" not in task.request.analysts
        start_task.assert_called_once_with(result["task_id"])
    finally:
        analysis_tasks.tasks.clear()


def test_opportunity_candidate_analysis_uses_request_language_preference(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(app_config, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(auth, "auth_enabled", lambda: False)
    monkeypatch.setattr(task_store, "redis_task_backend_enabled", lambda: False)
    analysis_tasks.tasks.clear()

    try:
        with patch("web.backend.runtime.analysis_tasks.start_task_thread"):
            result = opportunities_router.analyze_candidate(
                "300002.SZ",
                CandidateAnalyzePayload(
                    run_id="run-a",
                    analysis_date="2026-05-14",
                    opportunity_context={
                        "source": "opportunity_radar",
                        "symbol": "300002.SZ",
                        "theme": "AI Compute",
                    },
                ),
                request=_request_with_language("en"),
            )

        task = analysis_tasks.get_task(result["task_id"])
        assert task.request.output_language == "en"
    finally:
        analysis_tasks.tasks.clear()


def test_backtest_artifacts_and_tasks_are_tenant_scoped(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "BACKTEST_RUNS_DIR", tmp_path / "backtest_runs")
    monkeypatch.setattr(auth, "auth_enabled", lambda: True)

    run_dir = app_config.BACKTEST_RUNS_DIR / "bt_1"
    run_dir.mkdir(parents=True)
    (run_dir / "run_meta.json").write_text(
        json.dumps({"run_id": "bt_1", "tenant_id": "tenant-a"}),
        encoding="utf-8",
    )
    (run_dir / "backtest_snapshot.json").write_text(
        json.dumps({"run_id": "bt_1", "status": "completed"}),
        encoding="utf-8",
    )

    same_tenant = SimpleNamespace(id="u1", tenant_id="tenant-a")
    other_tenant = SimpleNamespace(id="u2", tenant_id="tenant-b")

    assert backtests.get_snapshot("bt_1", same_tenant)["status"] == "completed"
    with pytest.raises(HTTPException) as excinfo:
        backtests.get_snapshot("bt_1", other_tenant)

    assert excinfo.value.status_code == 404


def test_opportunity_task_idempotency_checks_task_store_in_redis_mode(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(app_config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    store = task_store.InMemoryTaskStore()
    monkeypatch.setattr(task_store, "_TASK_STORE", store)
    monkeypatch.setattr(task_store, "redis_task_backend_enabled", lambda: True)

    payload = {"trade_date": "2026-05-14", "market": "cn"}
    first = opportunity_tasks.create_opportunity_task(
        request_payload=payload,
        owner_user_id="user-a",
        tenant_id="tenant-a",
    )
    second = opportunity_tasks.create_opportunity_task(
        request_payload=payload,
        owner_user_id="user-a",
        tenant_id="tenant-a",
    )

    assert second["task_id"] == first["task_id"]
    assert second["cached"] is False
    assert store.queue_ids("opportunity") == [first["task_id"]]

    other_tenant = opportunity_tasks.create_opportunity_task(
        request_payload=payload,
        owner_user_id="user-b",
        tenant_id="tenant-b",
    )

    assert other_tenant["task_id"] != first["task_id"]
    assert len(store.queue_ids("opportunity")) == 2
