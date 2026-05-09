from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from diverge.llm_clients.model_profiles import (
    resolve_model_profile as resolve_static_model_profile,
)
from diverge.runner import AnalysisRequest
from web.backend import access, analysis_limits, app_config, audit, auth, llm_models
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


def _current_user(
    request: Request | None,
    *,
    permission: str = auth.PERMISSION_ANALYSIS_READ,
):
    if not auth.auth_enabled() or request is None:
        return None
    with auth.db_session() as db:
        return access.require_permission(db, request, permission)


def _can_access_task(task: analysis_tasks.Task, current_user) -> bool:
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
    task = analysis_tasks.get_task(task_id)
    if not _can_access_task(task, current_user):
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


def _enforce_task_submission_capacity(current_user) -> None:
    if not task_store.redis_task_backend_enabled():
        if (
            analysis_tasks.count_active_tasks() + screener_tasks.count_active_tasks()
            >= task_store.get_queue_limit()
        ):
            raise HTTPException(
                status_code=409,
                detail="Task queue is full. Wait for the active tasks to finish.",
            )
        return

    store = task_store.get_task_store()
    global_active = store.count_active("analysis") + store.count_active("screener")
    if global_active >= task_store.get_global_pending_limit():
        raise HTTPException(
            status_code=409,
            detail="Global task queue is full. Wait for queued work to finish.",
        )
    if current_user is None:
        return
    user_limit = task_store.get_user_pending_limit(getattr(current_user, "role", None))
    if store.count_active_by_owner(current_user.id) >= user_limit:
        raise HTTPException(
            status_code=409,
            detail=(
                f"User task queue is full ({user_limit} queued, waiting, or running tasks). "
                "Cancel queued work or wait for tasks to finish."
            ),
        )


def _analysis_request_payload(payload: TaskCreatePayload) -> dict:
    request_payload = payload.model_dump(exclude={"report_visibility"})
    profile = (payload.model_profile or "").strip().lower()
    if profile and profile != "custom":
        try:
            resolved = (
                llm_models.resolve_model_profile_from_db(profile)
                if llm_models.database_backed_llm_models_enabled()
                else resolve_static_model_profile(profile, get_provider_availability)
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        request_payload.update(
            {
                "model_profile": resolved.model_profile,
                "llm_provider": resolved.llm_provider,
                "quick_think_llm": resolved.quick_think_llm,
                "deep_think_llm": resolved.deep_think_llm,
            }
        )
        if resolved.llm_provider == "openai" and not request_payload.get(
            "openai_reasoning_effort"
        ):
            request_payload["openai_reasoning_effort"] = "medium"
        if resolved.llm_provider == "google" and not request_payload.get(
            "google_thinking_level"
        ):
            request_payload["google_thinking_level"] = "high"
    else:
        request_payload["model_profile"] = profile or None

    missing = [
        field
        for field in ("llm_provider", "quick_think_llm", "deep_think_llm")
        if not request_payload.get(field)
    ]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing model selection fields: {', '.join(missing)}",
        )

    return request_payload


@router.post("/api/tasks")
def create_task(payload: TaskCreatePayload, request: Request = None) -> dict:
    try:
        analysis_request = AnalysisRequest(**_analysis_request_payload(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    current_user = _current_user(request, permission=auth.PERMISSION_ANALYSIS_CREATE)
    hydrate_provider_credentials(analysis_request.llm_provider)
    provider_availability = get_provider_availability(analysis_request.llm_provider)
    if not provider_availability["enabled"]:
        raise HTTPException(
            status_code=400,
            detail=str(provider_availability["disabled_reason"]),
        )
    try:
        llm_models.ensure_model_selection_available(
            analysis_request.llm_provider,
            analysis_request.quick_think_llm,
            analysis_request.deep_think_llm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    _enforce_task_submission_capacity(current_user)
    owner_user_id = current_user.id if current_user is not None else None
    tenant_id = getattr(current_user, "tenant_id", None)
    if current_user is not None:
        try:
            with auth.db_session() as db:
                persisted_user = auth.get_user_by_id(db, current_user.id)
                analysis_limits.record_analysis_task_creation(db, persisted_user)
        except analysis_limits.WeeklyUsageLimitExceeded as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except Exception as exc:
            raise access.translate_auth_error(exc) from exc
        try:
            llm_models.record_model_usage(
                analysis_request.llm_provider,
                analysis_request.quick_think_llm,
                module="analysis",
            )
            llm_models.record_model_usage(
                analysis_request.llm_provider,
                analysis_request.deep_think_llm,
                module="analysis",
            )
        except Exception as exc:
            raise access.translate_auth_error(exc) from exc

    if owner_user_id:
        analysis_request.portfolio_context = (
            asset_service.build_portfolio_context_for_owner(
                owner_user_id,
                tenant_id=tenant_id,
                ticker=analysis_request.ticker,
            )
        )

    result = analysis_tasks.create_task(
        analysis_request,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        report_visibility=payload.report_visibility,
    )
    if current_user is not None and tenant_id is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=tenant_id,
                actor_user_id=current_user.id,
                action="analysis.task.created",
                resource_type="analysis_task",
                resource_id=str(result.get("task_id")),
                metadata={
                    "ticker": analysis_request.ticker,
                    "report_visibility": payload.report_visibility,
                },
                request=request,
            )
    return result


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


@router.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str, request: Request = None) -> dict:
    _get_authorized_task(task_id, request)
    analysis_tasks.cancel_task(task_id)
    return {"canceled": True, "task_id": task_id}


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
