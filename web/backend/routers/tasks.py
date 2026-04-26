from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from tradingagents.runner import AnalysisRequest
from web.backend import access, analysis_limits, app_config, auth
from web.backend.runtime import analysis_tasks, screener_tasks, task_store
from web.backend.schemas.tasks import TaskCreatePayload
from web.backend.services import assets as asset_service
from web.backend.services.config import (
    get_provider_availability,
    hydrate_provider_credentials,
)

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


def _serialize_sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _current_user(request: Request | None):
    if not auth.auth_enabled() or request is None:
        return None
    with auth.db_session() as db:
        return access.get_request_user_with_password_change(db, request)


def _can_access_task(task: analysis_tasks.Task, current_user) -> bool:
    if not auth.auth_enabled():
        return True
    return access.can_access_owner(current_user, task.owner_user_id, allow_unowned=True)


def _get_authorized_task(task_id: str, request: Request | None):
    current_user = _current_user(request)
    task = analysis_tasks.get_task(task_id)
    if not _can_access_task(task, current_user):
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


@router.post("/api/tasks")
def create_task(payload: TaskCreatePayload, request: Request = None) -> dict:
    try:
        analysis_request = AnalysisRequest(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    hydrate_provider_credentials(analysis_request.llm_provider)
    provider_availability = get_provider_availability(analysis_request.llm_provider)
    if not provider_availability["enabled"]:
        raise HTTPException(
            status_code=400,
            detail=str(provider_availability["disabled_reason"]),
        )

    if (
        analysis_tasks.count_active_tasks() + screener_tasks.count_active_tasks()
        >= task_store.get_queue_limit()
    ):
        raise HTTPException(
            status_code=409,
            detail="Task queue is full. Wait for the active tasks to finish.",
        )

    current_user = _current_user(request)
    owner_user_id = current_user.id if current_user is not None else None
    if current_user is not None:
        try:
            with auth.db_session() as db:
                persisted_user = auth.get_user_by_id(db, current_user.id)
                analysis_limits.record_analysis_task_creation(db, persisted_user)
        except analysis_limits.WeeklyUsageLimitExceeded as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except Exception as exc:
            raise access.translate_auth_error(exc) from exc

    if owner_user_id:
        analysis_request.portfolio_context = asset_service.build_portfolio_context_for_owner(
            owner_user_id,
            ticker=analysis_request.ticker,
        )

    return analysis_tasks.create_task(
        analysis_request,
        owner_user_id=owner_user_id,
    )


@router.get("/api/tasks")
def list_tasks(request: Request = None) -> list[dict]:
    current_user = _current_user(request)
    return [
        task.to_dict()
        for task in analysis_tasks.list_tasks()
        if _can_access_task(task, current_user)
    ]


@router.get("/api/tasks/{task_id}")
def get_task_status(task_id: str, request: Request = None) -> dict:
    return _get_authorized_task(task_id, request).to_dict()


@router.delete("/api/tasks/{task_id}")
def delete_task(task_id: str, request: Request = None) -> dict:
    _get_authorized_task(task_id, request)
    analysis_tasks.delete_failed_task(task_id)
    return {"deleted": True, "task_id": task_id}


@router.get("/api/tasks/{task_id}/stream")
async def stream_task(task_id: str, request: Request) -> StreamingResponse:
    _get_authorized_task(task_id, request)

    async def event_generator():
        cursor = 0

        while True:
            if await request.is_disconnected():
                break

            try:
                task = _get_authorized_task(task_id, request)
            except HTTPException:
                break
            pending_events = analysis_tasks.get_progress_events(task_id, cursor)
            task_status = task.status

            for event in pending_events:
                cursor += 1
                yield _serialize_sse_event(event)

            if task_status in app_config.TERMINAL_TASK_STATUSES and not pending_events:
                break

            await asyncio.sleep(0.25)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
