from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi import HTTPException

from diverge.screener.sync import SyncResult
from web.backend import worker
from web.backend.routers import data_sync as data_sync_router
from web.backend.runtime import data_sync_tasks, task_store
from web.backend.schemas.data_sync import (
    DataSyncFundamentalsPayload,
    DataSyncOhlcvPayload,
)


def test_create_ohlcv_sync_task_routes_to_runtime_with_admin_owner():
    actor = SimpleNamespace(id="admin-user", tenant_id="tenant-a")
    with (
        patch(
            "web.backend.routers.data_sync._require_admin_permission",
            return_value=actor,
        ),
        patch(
            "web.backend.routers.data_sync.data_sync_tasks.ensure_ohlcv_vendor_ready"
        ),
        patch(
            "web.backend.routers.data_sync.data_sync_tasks.create_data_sync_task",
            return_value={"task_id": "sync-1", "status": "pending"},
        ) as create_task,
    ):
        response = data_sync_router.create_ohlcv_sync_task(
            DataSyncOhlcvPayload(
                markets=["us"],
                as_of_date="2026-04-28",
                us_manifest_path="/tmp/us.csv",
                run_screener_prewarm=True,
            )
        )

    assert response == {"task_id": "sync-1", "status": "pending"}
    create_task.assert_called_once()
    kwargs = create_task.call_args.kwargs
    assert kwargs["sync_type"] == "ohlcv"
    assert kwargs["owner_user_id"] == "admin-user"
    assert kwargs["tenant_id"] == "tenant-a"
    assert kwargs["request_payload"]["markets"] == ["us"]
    assert kwargs["request_payload"]["top_k"] == 100
    assert kwargs["request_payload"]["run_screener_prewarm"] is True


def test_create_ohlcv_sync_task_records_audit_event_for_admin():
    actor = SimpleNamespace(id="admin-user", tenant_id="tenant-a")
    with (
        patch(
            "web.backend.routers.data_sync._require_admin_permission",
            return_value=actor,
        ),
        patch("web.backend.routers.data_sync.auth.auth_enabled", return_value=True),
        patch(
            "web.backend.routers.data_sync.data_sync_tasks.ensure_ohlcv_vendor_ready"
        ),
        patch(
            "web.backend.routers.data_sync.data_sync_tasks.create_data_sync_task",
            return_value={"task_id": "sync-1", "status": "pending"},
        ),
        patch(
            "web.backend.routers.data_sync.auth.db_session",
            return_value=nullcontext("db"),
        ),
        patch(
            "web.backend.routers.data_sync.audit.record_audit_event_safely"
        ) as record_audit,
    ):
        data_sync_router.create_ohlcv_sync_task(
            DataSyncOhlcvPayload(
                markets=["cn"],
                as_of_date="2026-04-29",
                cn_data_source="tushare",
            )
        )

    record_audit.assert_called_once()
    kwargs = record_audit.call_args.kwargs
    assert kwargs["action"] == "data_sync.ohlcv.created"
    assert kwargs["resource_type"] == "data_sync_task"
    assert kwargs["resource_id"] == "sync-1"
    assert kwargs["metadata"]["as_of_date"] == "2026-04-29"


def test_create_ohlcv_sync_task_rejects_when_vendor_not_ready():
    actor = SimpleNamespace(id="admin-user", tenant_id="tenant-a")
    with (
        patch(
            "web.backend.routers.data_sync._require_admin_permission",
            return_value=actor,
        ),
        patch(
            "web.backend.routers.data_sync.data_sync_tasks.ensure_ohlcv_vendor_ready",
            side_effect=data_sync_tasks.VendorDataNotReadyError(
                "Tushare daily data is not ready."
            ),
        ),
        patch(
            "web.backend.routers.data_sync.data_sync_tasks.create_data_sync_task"
        ) as create_task,
    ):
        with pytest.raises(HTTPException) as exc_info:
            data_sync_router.create_ohlcv_sync_task(
                DataSyncOhlcvPayload(
                    markets=["cn"],
                    as_of_date="2026-04-29",
                    cn_data_source="tushare",
                )
            )

    assert exc_info.value.status_code == 409
    assert "not ready" in str(exc_info.value.detail)
    create_task.assert_not_called()


def test_create_fundamental_sync_task_routes_to_runtime():
    with (
        patch(
            "web.backend.routers.data_sync._require_admin_permission", return_value=None
        ),
        patch(
            "web.backend.routers.data_sync.data_sync_tasks.create_data_sync_task",
            return_value={"task_id": "sync-2", "status": "pending"},
        ) as create_task,
    ):
        response = data_sync_router.create_fundamental_sync_task(
            DataSyncFundamentalsPayload(
                market="us",
                source="simfin",
                symbols=["MSFT"],
                as_of_date="2026-04-28",
            )
        )

    assert response["task_id"] == "sync-2"
    kwargs = create_task.call_args.kwargs
    assert kwargs["sync_type"] == "fundamentals"
    assert kwargs["request_payload"]["source"] == "simfin"
    assert kwargs["request_payload"]["symbols"] == ["MSFT"]


def test_list_data_sync_jobs_is_tenant_scoped():
    actor = SimpleNamespace(id="admin-user", tenant_id="tenant-a")
    jobs = [
        SimpleNamespace(id="a", tenant_id="tenant-a", to_dict=lambda: {"id": "a"}),
        SimpleNamespace(id="b", tenant_id="tenant-b", to_dict=lambda: {"id": "b"}),
    ]
    with (
        patch(
            "web.backend.routers.data_sync._require_admin_permission",
            return_value=actor,
        ),
        patch(
            "web.backend.routers.data_sync.data_sync_tasks.list_data_sync_tasks",
            return_value=jobs,
        ),
    ):
        response = data_sync_router.list_data_sync_jobs()

    assert response == [{"id": "a"}]


def test_create_data_sync_task_uses_unified_queue_when_redis_enabled(monkeypatch):
    store = task_store.InMemoryTaskStore()
    monkeypatch.setenv("TASK_BACKEND", "redis")
    monkeypatch.setattr(task_store, "_TASK_STORE", store)

    with patch("web.backend.runtime.data_sync_tasks.threading.Thread") as thread:
        response = data_sync_tasks.create_data_sync_task(
            sync_type="ohlcv",
            request_payload={"markets": ["us"], "as_of_date": "2026-04-28"},
            owner_user_id="admin-user",
            tenant_id="tenant-a",
        )

    assert response["status"] == "queued"
    assert store.queue_ids("data_sync") == [response["task_id"]]
    payload = store.get_task("data_sync", response["task_id"])
    assert payload is not None
    assert payload["status"] == "queued"
    assert payload["owner_user_id"] == "admin-user"
    assert payload["queued_at"] is not None
    thread.assert_not_called()


def test_worker_dispatches_data_sync_tasks_from_unified_queue(monkeypatch):
    store = task_store.InMemoryTaskStore()
    monkeypatch.setenv("TASK_BACKEND", "redis")
    monkeypatch.setattr(task_store, "_TASK_STORE", store)
    response = data_sync_tasks.create_data_sync_task(
        sync_type="ohlcv",
        request_payload={"markets": ["us"], "as_of_date": "2026-04-28"},
    )

    with patch("web.backend.worker.data_sync_tasks.run_data_sync_task") as run_task:
        did_work = worker.run_once(timeout=0)

    assert did_work is True
    run_task.assert_called_once_with(response["task_id"])
    assert store.processing_ids("data_sync") == []


def test_worker_startup_restores_data_sync_tasks_when_redis_enabled(monkeypatch):
    monkeypatch.setenv("TASK_BACKEND", "redis")
    monkeypatch.setenv("WORKER_ONCE", "true")

    with (
        patch("web.backend.worker.analysis_tasks.restore_persisted_active_tasks"),
        patch("web.backend.worker.screener_tasks.restore_persisted_screener_tasks"),
        patch(
            "web.backend.worker.data_sync_tasks.restore_persisted_data_sync_tasks"
        ) as restore_data_sync,
        patch("web.backend.worker.run_once", return_value=False),
    ):
        worker.main()

    restore_data_sync.assert_called_once_with()


def test_ohlcv_sync_requires_existing_us_manifest(tmp_path, monkeypatch):
    monkeypatch.delenv("SCREEN_US_MANIFEST_PATH", raising=False)
    monkeypatch.delenv("MANIFEST_DIR", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    with pytest.raises(RuntimeError, match="US data sync requires a manifest"):
        data_sync_tasks.build_ohlcv_config_payload(
            {"markets": ["us"], "as_of_date": "2026-04-28"}
        )


def test_completed_data_sync_task_is_persisted_to_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(
        data_sync_tasks.app_config, "SCREENER_STATE_DIR", tmp_path / "state"
    )
    data_sync_tasks.data_sync_tasks.clear()
    task = data_sync_tasks.DataSyncTask(
        id="sync-completed",
        sync_type="ohlcv",
        request_payload={"markets": ["cn"], "as_of_date": "2026-04-29"},
        status="completed",
        result={"status": "completed", "symbols_total": 1},
    )

    data_sync_tasks._save_task(task)
    data_sync_tasks.data_sync_tasks.clear()

    restored = data_sync_tasks.get_data_sync_task("sync-completed")
    assert restored.status == "completed"
    assert restored.result == {"status": "completed", "symbols_total": 1}


def test_restore_persisted_data_sync_tasks_marks_running_tasks_failed(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        data_sync_tasks.app_config, "SCREENER_STATE_DIR", tmp_path / "state"
    )
    data_sync_tasks.data_sync_tasks.clear()
    task = data_sync_tasks.DataSyncTask(
        id="sync-recover",
        sync_type="ohlcv",
        request_payload={"markets": ["cn"], "as_of_date": "2026-04-29"},
        status="running",
        started_at="2026-04-29T13:31:45+00:00",
        latest_progress={"timestamp": "21:31:45", "message": "history 1/10"},
        progress_events=[{"timestamp": "21:31:45", "message": "history 1/10"}],
    )
    data_sync_tasks._save_task(task)
    data_sync_tasks.data_sync_tasks.clear()

    data_sync_tasks.restore_persisted_data_sync_tasks()

    restored = data_sync_tasks.get_data_sync_task("sync-recover")
    assert restored.status == "failed"
    assert restored.error == data_sync_tasks.app_config.RECOVERED_TASK_ERROR
    assert restored.finished_at is not None
    assert restored.latest_progress["status"] == "failed"
    assert "restarted" in restored.latest_progress["message"].lower()


def test_run_data_sync_task_records_completed_audit_event(tmp_path, monkeypatch):
    monkeypatch.setattr(
        data_sync_tasks.app_config, "SCREENER_STATE_DIR", tmp_path / "state"
    )
    monkeypatch.setattr(data_sync_tasks.auth, "auth_enabled", lambda: True)
    data_sync_tasks.data_sync_tasks.clear()
    with patch("web.backend.runtime.data_sync_tasks.threading.Thread"):
        response = data_sync_tasks.create_data_sync_task(
            sync_type="ohlcv",
            request_payload={"markets": ["cn"], "as_of_date": "2026-04-29"},
            owner_user_id="admin-user",
            tenant_id="tenant-a",
        )
    result = {
        "status": "completed",
        "symbols_total": 10,
        "symbols_success": 8,
        "symbols_failed": 2,
        "symbols_missing_as_of_bar": 2,
        "quality_artifact_path": "/tmp/quality.json",
    }

    with (
        patch(
            "web.backend.runtime.data_sync_tasks._run_ohlcv_task", return_value=result
        ),
        patch(
            "web.backend.runtime.data_sync_tasks.auth.db_session",
            return_value=nullcontext("db"),
        ),
        patch(
            "web.backend.runtime.data_sync_tasks.audit.record_audit_event_safely"
        ) as record_audit,
    ):
        data_sync_tasks.run_data_sync_task(response["task_id"])

    record_audit.assert_called_once()
    kwargs = record_audit.call_args.kwargs
    assert kwargs["action"] == "data_sync.ohlcv.completed"
    assert kwargs["metadata"]["symbols_missing_as_of_bar"] == 2
    assert kwargs["metadata"]["quality_artifact_path"] == "/tmp/quality.json"


def test_fundamental_sync_can_build_symbols_from_us_manifest(tmp_path, monkeypatch):
    manifest_path = tmp_path / "us.csv"
    manifest_path.write_text(
        "symbol,name,exchange,sector,list_date,mktcap\n"
        "AAPL,Apple,NASDAQ,Technology,19801212,100\n"
        "MSFT,Microsoft,NASDAQ,Technology,19860313,90\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SIMFIN_API_KEY", "test-key")
    captured = {}

    def fake_sync(**kwargs):
        captured.update(kwargs)
        return SyncResult(
            sync_type="fundamentals",
            markets=["us"],
            source="simfin",
            status="completed",
            symbols_total=2,
            symbols_success=2,
            symbols_failed=0,
            rows_written=2,
            snapshot_path=None,
            meta_path=None,
            field_coverage=None,
            missing_fields=[],
            failed_symbols=[],
            updated_at="",
        )

    monkeypatch.setattr(data_sync_tasks, "sync_us_simfin_fundamentals", fake_sync)

    result = data_sync_tasks.run_fundamental_sync_payload(
        {
            "market": "us",
            "source": "simfin",
            "symbols": [],
            "manifest_path": str(manifest_path),
            "as_of_date": "2026-04-28",
        }
    )

    assert result["status"] == "completed"
    assert captured["tickers"] == ["AAPL", "MSFT"]


def test_us_simfin_fundamental_sync_rejects_empty_symbol_list(monkeypatch):
    monkeypatch.delenv("SCREEN_US_MANIFEST_PATH", raising=False)
    with pytest.raises(RuntimeError, match="symbols are required"):
        data_sync_tasks.run_fundamental_sync_payload(
            {
                "market": "us",
                "source": "simfin",
                "symbols": [],
                "as_of_date": "2026-04-28",
            }
        )


def test_us_simfin_fundamental_sync_rejects_symbols_over_daily_limit(monkeypatch):
    monkeypatch.setenv("SIMFIN_DAILY_TICKER_LIMIT", "2")

    with pytest.raises(RuntimeError, match="exceeds SIMFIN_DAILY_TICKER_LIMIT=2"):
        data_sync_tasks.run_fundamental_sync_payload(
            {
                "market": "us",
                "source": "simfin",
                "symbols": ["AAPL", "MSFT", "NVDA"],
                "as_of_date": "2026-04-28",
            }
        )


def test_tushare_ohlcv_sync_rejects_today_before_ready_cutoff(monkeypatch):
    monkeypatch.setattr(
        data_sync_tasks,
        "_now_for_vendor_timezone",
        lambda timezone_name: data_sync_tasks.datetime(2026, 4, 29, 17, 59),
    )
    with patch("web.backend.runtime.data_sync_tasks.sync_ohlcv_cache") as sync_cache:
        with pytest.raises(
            RuntimeError, match="Tushare daily data for 2026-04-29 is not ready"
        ):
            data_sync_tasks.run_ohlcv_sync_payload(
                {
                    "markets": ["cn"],
                    "as_of_date": "2026-04-29",
                    "cn_data_source": "tushare",
                }
            )

    sync_cache.assert_not_called()


def test_tushare_ohlcv_sync_rejects_when_ready_probe_is_empty(monkeypatch):
    monkeypatch.setattr(
        data_sync_tasks,
        "_now_for_vendor_timezone",
        lambda timezone_name: data_sync_tasks.datetime(2026, 4, 29, 18, 30),
    )
    monkeypatch.setattr(
        data_sync_tasks,
        "fetch_price_history",
        lambda *args, **kwargs: pd.DataFrame(),
    )

    with patch("web.backend.runtime.data_sync_tasks.sync_ohlcv_cache") as sync_cache:
        with pytest.raises(
            RuntimeError, match="Tushare daily data for 2026-04-29 is not ready"
        ):
            data_sync_tasks.run_ohlcv_sync_payload(
                {
                    "markets": ["cn"],
                    "as_of_date": "2026-04-29",
                    "cn_data_source": "tushare",
                }
            )

    sync_cache.assert_not_called()


def test_massive_ohlcv_sync_uses_new_york_ready_cutoff(monkeypatch):
    monkeypatch.setattr(
        data_sync_tasks,
        "_now_for_vendor_timezone",
        lambda timezone_name: data_sync_tasks.datetime(2026, 4, 29, 20, 30),
    )

    with patch("web.backend.runtime.data_sync_tasks.sync_ohlcv_cache") as sync_cache:
        with pytest.raises(
            RuntimeError, match="Massive daily data for 2026-04-29 is not ready"
        ):
            data_sync_tasks.run_ohlcv_sync_payload(
                {
                    "markets": ["us"],
                    "as_of_date": "2026-04-29",
                    "us_data_source": "massive",
                    "us_manifest_path": "/tmp/us.csv",
                }
            )

    sync_cache.assert_not_called()
