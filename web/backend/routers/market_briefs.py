from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from web.backend import access, audit, auth
from web.backend.runtime import market_brief_tasks
from web.backend.schemas.market_briefs import MarketBriefCreatePayload
from web.backend.services import market_briefs as market_brief_service
from web.backend.services import task_route_support

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


def _current_user(
    request: Request | None,
    *,
    permission: str = auth.PERMISSION_ANALYSIS_READ,
):
    if not auth.auth_enabled() or request is None:
        return None
    with auth.db_session() as db:
        return access.require_permission(db, request, permission)


def _can_access_task(task: market_brief_tasks.MarketBriefTask, current_user) -> bool:
    if not auth.auth_enabled():
        return True
    return access.can_access_owner(
        current_user,
        task.owner_user_id,
        tenant_id=getattr(task, "tenant_id", None),
        allow_unowned=True,
    )


def _get_authorized_task(task_id: str, request: Request | None):
    current_user = _current_user(request)
    task = market_brief_tasks.get_market_brief_task(task_id)
    if not _can_access_task(task, current_user):
        raise HTTPException(
            status_code=404, detail=f"Market brief task '{task_id}' not found"
        )
    return task


@router.get("/api/market-briefs")
def list_market_briefs(request: Request = None) -> dict:
    return market_brief_service.list_market_briefs(request)


@router.post("/api/market-briefs/tasks")
def create_market_brief_task(
    payload: MarketBriefCreatePayload,
    request: Request = None,
) -> dict:
    current_user = _current_user(request, permission=auth.PERMISSION_ANALYSIS_CREATE)
    task_route_support.enforce_task_submission_capacity(current_user)
    owner_user_id = current_user.id if current_user is not None else None
    tenant_id = getattr(current_user, "tenant_id", None)
    request_payload = payload.model_dump()
    request_payload["trigger"] = "manual"
    result = market_brief_tasks.create_market_brief_task(
        request_payload=request_payload,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
    )
    if current_user is not None and tenant_id is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=tenant_id,
                actor_user_id=current_user.id,
                action="market_brief.task.created",
                resource_type="market_brief_task",
                resource_id=str(result.get("task_id")),
                metadata={
                    "markets": request_payload.get("markets"),
                    "report_visibility": request_payload.get("report_visibility"),
                },
                request=request,
            )
    return result


@router.get("/api/market-briefs/tasks")
def list_market_brief_tasks(request: Request = None) -> list[dict]:
    current_user = _current_user(request)
    return [
        task.to_dict()
        for task in market_brief_tasks.list_market_brief_tasks()
        if _can_access_task(task, current_user)
    ]


@router.get("/api/market-briefs/tasks/{task_id}")
def get_market_brief_task(task_id: str, request: Request = None) -> dict:
    return _get_authorized_task(task_id, request).to_dict()


@router.post("/api/market-briefs/tasks/{task_id}/cancel")
def cancel_market_brief_task(task_id: str, request: Request = None) -> dict:
    task = _get_authorized_task(task_id, request)
    market_brief_tasks.cancel_market_brief_task(task.id)
    return {"canceled": True, "task_id": task.id}


@router.get("/api/market-briefs/tasks/{task_id}/stream")
async def stream_market_brief_task(task_id: str, request: Request) -> StreamingResponse:
    _get_authorized_task(task_id, request)
    return await task_route_support.stream_task_progress(
        request=request,
        get_task=lambda: _get_authorized_task(task_id, request),
        get_progress_events=lambda cursor: (
            market_brief_tasks.get_market_brief_progress_events(
                task_id,
                cursor,
            )
        ),
    )
