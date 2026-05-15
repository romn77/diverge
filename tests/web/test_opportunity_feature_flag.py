from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from web.backend import app_config, auth
from web.backend.runtime import opportunity_tasks, task_store
from web.backend.services import backtests, opportunities


def test_opportunity_service_returns_404_when_feature_flag_disabled(monkeypatch):
    monkeypatch.delenv("OPPORTUNITY_RADAR_ENABLED", raising=False)

    with pytest.raises(HTTPException) as excinfo:
        opportunities.require_enabled()

    assert excinfo.value.status_code == 404


def test_opportunity_runtime_initialization_is_noop_when_feature_flag_disabled(
    monkeypatch,
):
    monkeypatch.delenv("OPPORTUNITY_RADAR_ENABLED", raising=False)

    with patch(
        "web.backend.services.opportunities.opportunity_models.initialize_opportunity_runtime"
    ) as initialize_tables:
        opportunities.initialize_opportunity_runtime()

    initialize_tables.assert_not_called()


def test_backend_lifespan_skips_opportunity_tables_and_tasks_when_disabled(
    monkeypatch,
):
    from web.backend import main

    monkeypatch.delenv("OPPORTUNITY_RADAR_ENABLED", raising=False)

    async def run_lifespan_once():
        async with main._app_lifespan(None):
            return None

    with (
        patch("web.backend.main.auth.initialize_auth_runtime"),
        patch("web.backend.main.analysis_limits.initialize_analysis_limits_runtime"),
        patch("web.backend.main.data_sources.initialize_data_source_runtime"),
        patch("web.backend.main.llm_models.initialize_llm_model_runtime"),
        patch("web.backend.main.search_quota.initialize_search_quota_runtime"),
        patch("web.backend.main.report_metadata.initialize_report_metadata_runtime"),
        patch("web.backend.main.screener_runs.initialize_screener_runtime"),
        patch("web.backend.main.screener_results.initialize_screener_result_runtime"),
        patch("web.backend.main.trade_entries.initialize_trade_entries_runtime"),
        patch("web.backend.main.asset_entries.initialize_asset_runtime"),
        patch("web.backend.main.audit.ensure_audit_tables"),
        patch("web.backend.main.job_records.initialize_job_record_runtime"),
        patch("web.backend.main.job_records.recover_stale_running_job_records"),
        patch(
            "web.backend.main.task_store.redis_task_backend_enabled", return_value=False
        ),
        patch("web.backend.main.restore_persisted_active_tasks"),
        patch("web.backend.main.restore_persisted_screener_tasks"),
        patch("web.backend.main.restore_persisted_data_sync_tasks"),
        patch(
            "web.backend.main.app_config.ensure_opportunity_dependencies"
        ) as ensure_deps,
        patch(
            "web.backend.main.opportunity_models.initialize_opportunity_runtime"
        ) as initialize_tables,
        patch(
            "web.backend.main.restore_persisted_opportunity_tasks"
        ) as restore_opportunity,
        patch("web.backend.main.restore_persisted_backtest_tasks") as restore_backtest,
    ):
        asyncio.run(run_lifespan_once())

    ensure_deps.assert_not_called()
    initialize_tables.assert_not_called()
    restore_opportunity.assert_not_called()
    restore_backtest.assert_not_called()


def test_opportunity_artifacts_are_tenant_scoped(monkeypatch, tmp_path):
    monkeypatch.setenv("OPPORTUNITY_RADAR_ENABLED", "true")
    monkeypatch.setattr(app_config, "PROJECT_ROOT", tmp_path)
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
    monkeypatch.setenv("OPPORTUNITY_RADAR_ENABLED", "true")
    monkeypatch.setattr(app_config, "PROJECT_ROOT", tmp_path)
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
