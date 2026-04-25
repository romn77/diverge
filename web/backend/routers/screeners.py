from __future__ import annotations

import asyncio
import json
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from tradingagents.screener.schema import ScreenRunConfig
from web.backend import access, analysis_limits, app_config, auth
from web.backend.runtime import analysis_tasks, screener_tasks, task_store
from web.backend.schemas.screeners import ScreenTaskCreatePayload
from web.backend.services import screeners as screener_service

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


def _serialize_sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _get_authorized_screener_task(
    task_id: str,
    current_user,
):
    task = screener_tasks.get_screener_task(task_id)
    if not access.can_access_screener_owner(current_user, task.owner_user_id):
        raise HTTPException(status_code=404, detail=f"Screener task '{task_id}' not found")
    return task


@router.post("/api/screener/tasks")
def create_screener_task(
    payload: ScreenTaskCreatePayload,
    request: Request = None,
) -> dict:
    current_user = access.require_screener_user(request)
    if (
        analysis_tasks.count_active_tasks() + screener_tasks.count_active_tasks()
        >= task_store.get_queue_limit()
    ):
        raise HTTPException(
            status_code=409,
            detail="Task queue is full. Wait for the active tasks to finish.",
        )

    request_payload = payload.model_dump()
    config_payload = dict(request_payload)
    config_payload["output_dir"] = str(app_config.SCREENER_RESULTS_DIR)
    if "cn" in request_payload["markets"]:
        manifest_path = os.environ.get("SCREEN_CN_MANIFEST_PATH")
        if manifest_path:
            config_payload["cn_manifest_path"] = manifest_path
    if "us" in request_payload["markets"]:
        manifest_path = os.environ.get("SCREEN_US_MANIFEST_PATH")
        if not manifest_path:
            raise HTTPException(
                status_code=400,
                detail="Configure SCREEN_US_MANIFEST_PATH on the backend before launching US screening tasks.",
            )
        config_payload["us_manifest_path"] = manifest_path

    try:
        ScreenRunConfig(**config_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    return screener_tasks.create_screener_task(
        request_payload=request_payload,
        config_payload=config_payload,
        owner_user_id=current_user.id if current_user is not None else None,
    )


@router.get("/api/screener/tasks")
def list_screener_tasks(request: Request = None) -> list[dict]:
    current_user = access.require_screener_user(request)
    return [
        task.to_dict()
        for task in screener_tasks.list_screener_tasks()
        if access.can_access_screener_owner(current_user, task.owner_user_id)
    ]


@router.get("/api/screener/tasks/{task_id}")
def get_screener_task_status(task_id: str, request: Request = None) -> dict:
    current_user = access.require_screener_user(request)
    return _get_authorized_screener_task(task_id, current_user).to_dict()


@router.get(
    "/api/screener/tasks/{task_id}/stream",
)
async def stream_screener_task(task_id: str, request: Request) -> StreamingResponse:
    current_user = access.require_screener_user(request)
    _get_authorized_screener_task(task_id, current_user)

    async def event_generator():
        cursor = 0

        while True:
            if await request.is_disconnected():
                break

            try:
                task = _get_authorized_screener_task(task_id, current_user)
            except HTTPException:
                break
            pending_events = screener_tasks.get_screener_progress_events(task_id, cursor)
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
