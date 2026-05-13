from __future__ import annotations

from datetime import date as _date

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from web.backend import (
    access,
    analysis_limits,
    audit,
    auth,
    screener_presets,
)
from web.backend.runtime import (
    screener_tasks,
)
from web.backend.schemas.screeners import ScreenTaskCreatePayload
from web.backend.services import screener_preparation
from web.backend.services import screeners as screener_service
from web.backend.services import task_route_support

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])
date = _date


def _get_authorized_screener_task(
    task_id: str,
    current_user,
):
    task = screener_tasks.get_screener_task(task_id)
    if not access.can_access_screener_owner(
        current_user,
        task.owner_user_id,
        tenant_id=getattr(task, "tenant_id", None),
    ):
        raise HTTPException(
            status_code=404, detail=f"Screener task '{task_id}' not found"
        )
    return task


def resolve_screener_data_sources(markets: list[str]) -> dict:
    return screener_preparation.resolve_screener_data_sources(markets)


def resolve_screener_as_of_date(
    markets: list[str], data_sources: dict | None = None
) -> str:
    try:
        return screener_preparation.resolve_screener_as_of_date(
            markets,
            data_sources,
        )
    except screener_preparation.ScreenerPreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/screener/tasks")
def create_screener_task(
    payload: ScreenTaskCreatePayload,
    request: Request = None,
) -> dict:
    current_user = access.require_screener_user(
        request,
        permission=auth.PERMISSION_SCREENER_CREATE,
    )

    try:
        prepared = screener_preparation.prepare_screener_run(
            payload.model_dump(),
            data_source_resolver=resolve_screener_data_sources,
            as_of_date_resolver=resolve_screener_as_of_date,
        )
    except screener_preparation.ScreenerPreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if prepared.cached:
        return screener_tasks.create_cached_screener_task(
            request_payload=prepared.request_payload,
            config_payload=prepared.config_payload,
            run_id=prepared.cached_run_id,
            owner_user_id=current_user.id if current_user is not None else None,
            tenant_id=getattr(current_user, "tenant_id", None),
        )

    task_route_support.enforce_task_submission_capacity(current_user)

    if current_user is not None:
        try:
            with auth.db_session() as db:
                persisted_user = auth.get_user_by_id(db, current_user.id)
                analysis_limits.record_module_usage(
                    db,
                    persisted_user,
                    module="screener",
                )
        except analysis_limits.WeeklyUsageLimitExceeded as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except Exception as exc:
            raise access.translate_auth_error(exc) from exc

    tenant_id = getattr(current_user, "tenant_id", None)
    result = screener_tasks.create_screener_task(
        request_payload=prepared.request_payload,
        config_payload=prepared.config_payload,
        owner_user_id=current_user.id if current_user is not None else None,
        tenant_id=tenant_id,
    )
    if current_user is not None and tenant_id is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=tenant_id,
                actor_user_id=current_user.id,
                action="screener.task.created",
                resource_type="screener_task",
                resource_id=str(result.get("task_id")),
                metadata={"markets": prepared.request_payload.get("markets")},
                request=request,
            )
    return result


@router.get("/api/screener/presets")
def list_screener_presets_endpoint(request: Request = None) -> list[dict]:
    current_user = access.require_screener_user(request)
    return screener_presets.load_screener_presets(
        current_user.id if current_user is not None else None
    )


@router.put("/api/screener/presets")
def replace_screener_presets_endpoint(
    payload: list[dict] | None = Body(default=None),
    request: Request = None,
) -> list[dict]:
    current_user = access.require_screener_user(
        request,
        permission=auth.PERMISSION_SCREENER_CREATE,
    )
    try:
        return screener_presets.save_screener_presets(
            current_user.id if current_user is not None else None,
            payload or [],
            tenant_id=getattr(current_user, "tenant_id", None),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/screener/tasks")
def list_screener_tasks(request: Request = None) -> list[dict]:
    current_user = access.require_screener_user(request)
    return [
        task.to_dict()
        for task in screener_tasks.list_screener_tasks()
        if access.can_access_screener_owner(
            current_user,
            task.owner_user_id,
            tenant_id=getattr(task, "tenant_id", None),
        )
    ]


@router.get("/api/screener/tasks/{task_id}")
def get_screener_task_status(task_id: str, request: Request = None) -> dict:
    current_user = access.require_screener_user(request)
    return _get_authorized_screener_task(task_id, current_user).to_dict()


@router.delete("/api/screener/tasks/{task_id}")
def delete_screener_task(task_id: str, request: Request = None) -> dict:
    current_user = access.require_screener_user(request)
    _get_authorized_screener_task(task_id, current_user)
    screener_tasks.delete_failed_screener_task(task_id)
    return {"deleted": True, "task_id": task_id}


@router.post("/api/screener/tasks/{task_id}/cancel")
def cancel_screener_task(task_id: str, request: Request = None) -> dict:
    current_user = access.require_screener_user(request)
    task = _get_authorized_screener_task(task_id, current_user)
    screener_tasks.cancel_screener_task(task_id)
    if current_user is not None and getattr(task, "tenant_id", None) is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=task.tenant_id,
                actor_user_id=current_user.id,
                action="screener.task.cancel_requested",
                resource_type="screener_task",
                resource_id=task_id,
                metadata={
                    "markets": task.request_payload.get("markets"),
                    "status": task.status,
                    "owner_user_id": task.owner_user_id,
                },
                request=request,
            )
    return {"canceled": True, "task_id": task_id}


@router.get(
    "/api/screener/tasks/{task_id}/stream",
)
async def stream_screener_task(
    task_id: str,
    request: Request,
    cursor: int = 0,
) -> StreamingResponse:
    current_user = access.require_screener_user(request)
    _get_authorized_screener_task(task_id, current_user)
    start_cursor = max(cursor, 0)
    return await task_route_support.stream_task_progress(
        request=request,
        get_task=lambda: _get_authorized_screener_task(task_id, current_user),
        get_progress_events=lambda cursor: screener_tasks.get_screener_progress_events(
            task_id, cursor
        ),
        start_cursor=start_cursor,
    )


@router.get("/api/screener/runs")
def list_screener_runs_endpoint(request: Request) -> list[dict]:
    current_user = access.require_screener_user(request)
    return screener_service.list_screener_runs(current_user)


@router.get("/api/screener/runs/{run_id}")
def get_screener_run_endpoint(run_id: str, request: Request) -> dict:
    current_user = access.require_screener_user(request)
    return screener_service.get_screener_run(run_id, current_user)


@router.get(
    "/api/screener/runs/{run_id}/candidates",
)
def get_screener_run_candidates_endpoint(run_id: str, request: Request) -> list[dict]:
    current_user = access.require_screener_user(request)
    return screener_service.get_screener_run_candidates(run_id, current_user)
