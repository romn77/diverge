from __future__ import annotations

import asyncio
import json
import os
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from diverge.dataflows import vendor_usage
from diverge.screener.market_calendar import latest_trading_day_on_or_before
from diverge.screener.schema import ScreenRunConfig
from web.backend import (
    access,
    analysis_limits,
    app_config,
    audit,
    auth,
    screener_presets,
    screener_results,
)
from web.backend.runtime import analysis_tasks, data_sync_tasks, screener_tasks, task_store
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
    if not access.can_access_screener_owner(
        current_user,
        task.owner_user_id,
        tenant_id=getattr(task, "tenant_id", None),
    ):
        raise HTTPException(status_code=404, detail=f"Screener task '{task_id}' not found")
    return task


def resolve_screener_data_sources(markets: list[str]) -> dict:
    sources: dict[str, object] = {}

    cn_chain = vendor_usage.get_data_source_route(
        module="screener",
        market="cn",
        category="core_stock_apis",
    )
    if not cn_chain:
        cn_chain = ["tushare"]
    sources["cn_data_source"] = cn_chain[0]
    sources["cn_data_source_fallbacks"] = cn_chain[1:]

    us_chain = vendor_usage.get_data_source_route(
        module="screener",
        market="us",
        category="core_stock_apis",
    )
    if not us_chain:
        us_chain = ["massive"]
    sources["us_data_source"] = us_chain[0]
    sources["us_data_source_fallbacks"] = us_chain[1:]

    return sources


def resolve_screener_as_of_date(markets: list[str], data_sources: dict | None = None) -> str:
    today = date.today()
    sources = data_sources or {}
    trading_days = []
    for market in markets:
        normalized_market = str(market).strip().lower()
        trading_day = latest_trading_day_on_or_before(normalized_market, today)
        if trading_day is None:
            continue
        source = (
            str(sources.get("cn_data_source") or "tushare")
            if normalized_market == "cn"
            else str(sources.get("us_data_source") or "massive")
        )
        trading_days.append(
            data_sync_tasks.resolve_ready_ohlcv_as_of_date(
                normalized_market,
                source,
                trading_day,
            )
        )
    if not trading_days:
        raise HTTPException(status_code=400, detail="Unable to resolve screener trading date.")
    return min(trading_days).isoformat()


def _enforce_screener_submission_capacity(current_user) -> None:
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


@router.post("/api/screener/tasks")
def create_screener_task(
    payload: ScreenTaskCreatePayload,
    request: Request = None,
) -> dict:
    current_user = access.require_screener_user(
        request,
        permission=auth.PERMISSION_SCREENER_CREATE,
    )

    request_payload = payload.model_dump()
    request_payload["history_cache_policy"] = "cache_only"
    request_payload.update(resolve_screener_data_sources(request_payload["markets"]))
    if not request_payload.get("as_of_date"):
        request_payload["as_of_date"] = resolve_screener_as_of_date(
            request_payload["markets"],
            request_payload,
        )
    config_payload = dict(request_payload)
    config_payload["output_dir"] = str(app_config.SCREENER_RESULTS_DIR)
    config_payload["cache_dir"] = str(app_config.SCREENER_CACHE_DIR)
    config_payload["history_dir"] = str(app_config.STOCK_HISTORY_DIR)
    config_payload["fundamental_dir"] = str(app_config.FUNDAMENTALS_DIR)
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
        config = ScreenRunConfig(**config_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    screener_key = screener_results.screener_key_for_config(config_payload)
    request_payload["screener_key"] = screener_key
    cached_snapshot = screener_results.get_cached_screener_result(config_payload)
    if cached_snapshot is not None:
        return screener_tasks.create_cached_screener_task(
            request_payload=request_payload,
            config_payload=config_payload,
            run_id=cached_snapshot.source_run_id,
            owner_user_id=current_user.id if current_user is not None else None,
            tenant_id=getattr(current_user, "tenant_id", None),
        )

    _enforce_screener_submission_capacity(current_user)
    screener_service.ensure_screener_cache_coverage(config)

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
        request_payload=request_payload,
        config_payload=config_payload,
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
                metadata={"markets": request_payload.get("markets")},
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
    _get_authorized_screener_task(task_id, current_user)
    screener_tasks.cancel_screener_task(task_id)
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

    async def event_generator():
        cursor = start_cursor

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
