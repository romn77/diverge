from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from diverge.dataflows.routes import source_chain_for_market
from diverge.llm_clients.model_profiles import (
    resolve_model_profile as resolve_static_model_profile,
)
from diverge.common.symbols import detect_market, normalize_analysis_ticker_symbol
from diverge.runner import AnalysisRequest
from web.backend import access, analysis_limits, audit, auth, llm_models
from web.backend.runtime import (
    analysis_tasks,
    data_sync_tasks,
)
from web.backend.schemas.tasks import TaskCreatePayload
from web.backend.services import assets as asset_service
from web.backend.services import task_route_support
from web.backend.services.preferences import preferred_output_language_from_request
from web.backend.services.config import (
    get_provider_availability,
    hydrate_provider_credentials,
)

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


def _env_flag_enabled(name: str, *, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _analysis_portfolio_context_enabled() -> bool:
    return _env_flag_enabled("ANALYSIS_PORTFOLIO_CONTEXT_ENABLED")


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


def _analysis_core_data_source(market: str, request_payload: dict) -> str:
    legacy_source = request_payload.get("market_data_source")
    if market == "us" and legacy_source:
        return str(legacy_source).strip().lower()

    route = source_chain_for_market(module="analysis", market=market)
    if route:
        return route[0]
    return "tushare" if market == "cn" else "massive"


def _analysis_request_payload(
    payload: TaskCreatePayload,
    current_user=None,
    request: Request | None = None,
) -> dict:
    request_payload = payload.model_dump(exclude={"report_visibility"})
    request_payload["output_language"] = (
        payload.output_language
        or preferred_output_language_from_request(request)
        or "en"
    )
    normalized_ticker = normalize_analysis_ticker_symbol(
        request_payload["ticker"],
        ticker_exchange=request_payload.get("ticker_exchange"),
    )
    market = detect_market(normalized_ticker)
    if market not in {"cn", "us"}:
        market = "us"
    source = _analysis_core_data_source(market, request_payload)
    request_payload["analysis_date"] = data_sync_tasks.resolve_latest_ready_trading_day(
        market, source
    ).isoformat()
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
                "backend_url": resolved.backend_url,
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
        custom_profile_allowed = llm_models.custom_analysis_profile_visible_for_role(
            getattr(current_user, "role", None)
        )
        if profile == "custom" and not custom_profile_allowed:
            raise HTTPException(
                status_code=403,
                detail="Custom analysis model selection is available to admins only.",
            )
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
    current_user = _current_user(request, permission=auth.PERMISSION_ANALYSIS_CREATE)
    try:
        analysis_request = AnalysisRequest(
            **_analysis_request_payload(
                payload, current_user=current_user, request=request
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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

    task_route_support.enforce_task_submission_capacity(current_user)
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

    if owner_user_id and _analysis_portfolio_context_enabled():
        analysis_request.portfolio_context = (
            asset_service.build_portfolio_context_for_owner(
                owner_user_id,
                tenant_id=tenant_id,
                ticker=analysis_request.ticker,
                output_language=analysis_request.output_language,
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
    current_user = _current_user(request)
    task = analysis_tasks.get_task(task_id)
    if not _can_access_task(task, current_user):
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    analysis_tasks.cancel_task(task_id)
    if current_user is not None and getattr(task, "tenant_id", None) is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=task.tenant_id,
                actor_user_id=current_user.id,
                action="analysis.task.cancel_requested",
                resource_type="analysis_task",
                resource_id=task_id,
                metadata={
                    "ticker": task.request.ticker,
                    "status": task.status,
                    "owner_user_id": task.owner_user_id,
                },
                request=request,
            )
    return {"canceled": True, "task_id": task_id}


@router.get("/api/tasks/{task_id}/stream")
async def stream_task(task_id: str, request: Request) -> StreamingResponse:
    _get_authorized_task(task_id, request)
    return await task_route_support.stream_task_progress(
        request=request,
        get_task=lambda: _get_authorized_task(task_id, request),
        get_progress_events=lambda cursor: analysis_tasks.get_progress_events(
            task_id, cursor
        ),
    )
