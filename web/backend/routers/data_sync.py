from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from web.backend import access, audit, auth
from web.backend.runtime import data_sync_tasks
from web.backend.schemas.data_sync import (
    DataSyncFundamentalsPayload,
    DataSyncOhlcvPayload,
)

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


def _require_admin_permission(request: Request | None) -> auth.User | None:
    if request is None or not auth.auth_enabled():
        return None
    with auth.db_session() as db:
        return access.require_permission(db, request, auth.PERMISSION_ADMIN_SETTINGS)


@router.post("/api/admin/data-sync/ohlcv")
def create_ohlcv_sync_task(
    payload: DataSyncOhlcvPayload,
    request: Request = None,
) -> dict:
    actor = _require_admin_permission(request)
    request_payload = payload.model_dump()
    try:
        data_sync_tasks.ensure_ohlcv_vendor_ready(request_payload)
    except data_sync_tasks.VendorDataNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    result = data_sync_tasks.create_data_sync_task(
        sync_type="ohlcv",
        request_payload=request_payload,
        owner_user_id=actor.id if actor is not None else None,
        tenant_id=actor.tenant_id if actor is not None else None,
    )
    if actor is not None and auth.auth_enabled():
        try:
            with auth.db_session() as db:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.id,
                    action="data_sync.ohlcv.created",
                    resource_type="data_sync_task",
                    resource_id=str(result.get("task_id")),
                    metadata={
                        "sync_type": "ohlcv",
                        "markets": request_payload.get("markets"),
                        "as_of_date": request_payload.get("as_of_date"),
                        "cn_data_source": request_payload.get("cn_data_source"),
                        "us_data_source": request_payload.get("us_data_source"),
                    },
                    request=request,
                )
        except Exception:
            pass
    return result


@router.post("/api/admin/data-sync/fundamentals")
def create_fundamental_sync_task(
    payload: DataSyncFundamentalsPayload,
    request: Request = None,
) -> dict:
    actor = _require_admin_permission(request)
    result = data_sync_tasks.create_data_sync_task(
        sync_type="fundamentals",
        request_payload=payload.model_dump(),
        owner_user_id=actor.id if actor is not None else None,
        tenant_id=actor.tenant_id if actor is not None else None,
    )
    if actor is not None and auth.auth_enabled():
        try:
            with auth.db_session() as db:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.id,
                    action="data_sync.fundamentals.created",
                    resource_type="data_sync_task",
                    resource_id=str(result.get("task_id")),
                    metadata={
                        "sync_type": "fundamentals",
                        "market": payload.market,
                        "source": payload.source,
                        "as_of_date": payload.as_of_date,
                    },
                    request=request,
                )
        except Exception:
            pass
    return result


@router.get("/api/admin/data-sync/jobs")
def list_data_sync_jobs(request: Request = None) -> list[dict]:
    actor = _require_admin_permission(request)
    jobs = [
        task.to_dict()
        for task in data_sync_tasks.list_data_sync_tasks()
        if actor is None or task.tenant_id == actor.tenant_id
    ]
    return jobs


@router.get("/api/admin/data-sync/jobs/{task_id}")
def get_data_sync_job(task_id: str, request: Request = None) -> dict:
    actor = _require_admin_permission(request)
    task = data_sync_tasks.get_data_sync_task(task_id)
    if actor is not None and task.tenant_id != actor.tenant_id:
        raise access.translate_auth_error(auth.AuthNotFoundError(f"Task '{task_id}' not found"))
    return task.to_dict()
