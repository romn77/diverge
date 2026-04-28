from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from web.backend.routers import data_sync as data_sync_router
from web.backend.schemas.data_sync import (
    DataSyncFundamentalsPayload,
    DataSyncOhlcvPayload,
)


def test_create_ohlcv_sync_task_routes_to_runtime_with_admin_owner():
    actor = SimpleNamespace(id="admin-user", tenant_id="tenant-a")
    with (
        patch("web.backend.routers.data_sync._require_admin_permission", return_value=actor),
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
            )
        )

    assert response == {"task_id": "sync-1", "status": "pending"}
    create_task.assert_called_once()
    kwargs = create_task.call_args.kwargs
    assert kwargs["sync_type"] == "ohlcv"
    assert kwargs["owner_user_id"] == "admin-user"
    assert kwargs["tenant_id"] == "tenant-a"
    assert kwargs["request_payload"]["markets"] == ["us"]


def test_create_fundamental_sync_task_routes_to_runtime():
    with (
        patch("web.backend.routers.data_sync._require_admin_permission", return_value=None),
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
        patch("web.backend.routers.data_sync._require_admin_permission", return_value=actor),
        patch("web.backend.routers.data_sync.data_sync_tasks.list_data_sync_tasks", return_value=jobs),
    ):
        response = data_sync_router.list_data_sync_jobs()

    assert response == [{"id": "a"}]
