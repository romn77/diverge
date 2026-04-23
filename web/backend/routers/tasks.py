from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from tradingagents.runner import AnalysisRequest
from web.backend import app_config, auth
from web.backend.runtime import analysis_tasks, screener_tasks
from web.backend.schemas.tasks import TaskCreatePayload
from web.backend.services import assets as asset_service
from web.backend.services.config import (
    get_provider_availability,
    hydrate_provider_credentials,
)

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


def _serialize_sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/api/tasks")
def create_task(payload: TaskCreatePayload, request: Request = None) -> dict:
    analysis_request = AnalysisRequest(**payload.model_dump())
    hydrate_provider_credentials(analysis_request.llm_provider)
    provider_availability = get_provider_availability(analysis_request.llm_provider)
    if not provider_availability["enabled"]:
        raise HTTPException(
            status_code=400,
            detail=str(provider_availability["disabled_reason"]),
        )

    if analysis_tasks.count_active_tasks() + screener_tasks.count_active_tasks() >= 2:
        raise HTTPException(
            status_code=409,
            detail="Task queue is full. Wait for the active tasks to finish.",
        )

    owner_user_id = analysis_tasks.resolve_owner_user_id(request)
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
def list_tasks() -> list[dict]:
    with analysis_tasks.tasks_lock:
        return [task.to_dict() for task in analysis_tasks.tasks.values()]


@router.get("/api/tasks/{task_id}")
def get_task_status(task_id: str) -> dict:
    return analysis_tasks.get_task(task_id).to_dict()


@router.get("/api/tasks/{task_id}/stream")
async def stream_task(task_id: str, request: Request) -> StreamingResponse:
    analysis_tasks.get_task(task_id)

    async def event_generator():
        cursor = 0

        while True:
            if await request.is_disconnected():
                break

            with analysis_tasks.tasks_lock:
                task = analysis_tasks.tasks.get(task_id)
                if task is None:
                    break
                pending_events = task.progress_events[cursor:]
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
