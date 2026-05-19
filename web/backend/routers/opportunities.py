from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from diverge.analysis.options import ANALYST_ORDER
from diverge.runner import AnalysisRequest
from web.backend import access, audit, auth
from web.backend.runtime import analysis_tasks, opportunity_tasks
from web.backend.schemas.opportunities import (
    CandidateAnalyzePayload,
    OpportunityRunPayload,
    WatchlistMutationPayload,
)
from web.backend.services import opportunities as opportunity_service
from web.backend.services import task_route_support
from web.backend.services.preferences import preferred_output_language_from_request

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


def _get_authorized_task(task_id: str, current_user):
    task = opportunity_tasks.get_task(task_id)
    if auth.auth_enabled() and getattr(task, "tenant_id", None) != getattr(
        current_user, "tenant_id", None
    ):
        raise HTTPException(
            status_code=404, detail=f"Opportunity task '{task_id}' not found"
        )
    return task


def _current_user(
    request: Request | None, permission: str = auth.PERMISSION_OPPORTUNITY_READ
):
    if not auth.auth_enabled() or request is None:
        return None
    with auth.db_session() as db:
        return access.require_permission(db, request, permission)


@router.get("/api/opportunities/runs")
def list_runs(request: Request = None) -> list[dict]:
    return opportunity_service.list_runs(_current_user(request))


@router.get("/api/opportunities/runs/{run_id}")
def get_run(run_id: str, request: Request = None) -> dict:
    return opportunity_service.get_run(run_id, _current_user(request))


@router.get("/api/opportunities/runs/{run_id}/market-pulse")
def get_market_pulse(run_id: str, request: Request = None):
    return opportunity_service.get_artifact(
        run_id, "market_pulse", _current_user(request)
    )


@router.get("/api/opportunities/runs/{run_id}/themes")
def get_themes(run_id: str, request: Request = None):
    return opportunity_service.get_artifact(run_id, "themes", _current_user(request))


@router.get("/api/opportunities/runs/{run_id}/events")
def get_events(run_id: str, request: Request = None):
    return opportunity_service.get_artifact(run_id, "events", _current_user(request))


@router.get("/api/opportunities/runs/{run_id}/candidates")
def get_candidates(run_id: str, request: Request = None):
    return opportunity_service.get_artifact(
        run_id, "candidates", _current_user(request)
    )


@router.get("/api/opportunities/runs/{run_id}/watchlist")
def get_watchlist_snapshot(run_id: str, request: Request = None):
    return opportunity_service.get_artifact(run_id, "watchlist", _current_user(request))


@router.get("/api/opportunities/watchlist")
def list_watchlist(request: Request = None):
    return opportunity_service.list_watchlist(_current_user(request))


@router.post("/api/opportunities/watchlist")
def upsert_watchlist(payload: WatchlistMutationPayload, request: Request = None):
    user = _current_user(request, auth.PERMISSION_OPPORTUNITY_WRITE)
    result = opportunity_service.upsert_watchlist_item(payload.model_dump(), user)
    if user is not None and getattr(user, "tenant_id", None) is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=user.tenant_id,
                actor_user_id=user.id,
                action="opportunity.watchlist.upserted",
                resource_type="watchlist_item",
                resource_id=str(result.get("id") or payload.symbol),
                metadata={
                    "symbol": payload.symbol,
                    "status": payload.status,
                    "source_run_id": payload.source_run_id,
                },
                request=request,
            )
    return result


@router.delete("/api/opportunities/watchlist/{symbol}")
def delete_watchlist(symbol: str, request: Request = None):
    user = _current_user(request, auth.PERMISSION_OPPORTUNITY_WRITE)
    result = opportunity_service.delete_watchlist_item(symbol, user)
    if user is not None and getattr(user, "tenant_id", None) is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=user.tenant_id,
                actor_user_id=user.id,
                action="opportunity.watchlist.removed",
                resource_type="watchlist_item",
                resource_id=symbol,
                metadata={"symbol": symbol},
                request=request,
            )
    return result


@router.post("/api/opportunities/run")
def create_run(payload: OpportunityRunPayload, request: Request = None) -> dict:
    user = _current_user(request, auth.PERMISSION_OPPORTUNITY_RUN)
    result = opportunity_tasks.create_opportunity_task(
        request_payload=payload.model_dump(),
        owner_user_id=user.id if user else None,
        tenant_id=getattr(user, "tenant_id", None),
    )
    if user is not None and getattr(user, "tenant_id", None) is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=user.tenant_id,
                actor_user_id=user.id,
                action="opportunity.run.created",
                resource_type="opportunity_task",
                resource_id=str(result.get("task_id")),
                metadata={"market": payload.market, "trade_date": payload.trade_date},
                request=request,
            )
    return result


@router.get("/api/opportunities/tasks")
def list_opportunity_tasks(request: Request = None) -> list[dict]:
    user = _current_user(request)
    return [
        task.to_dict()
        for task in opportunity_tasks.list_tasks()
        if not auth.auth_enabled() or task.tenant_id == getattr(user, "tenant_id", None)
    ]


@router.get("/api/opportunities/tasks/{task_id}")
def get_opportunity_task(task_id: str, request: Request = None) -> dict:
    user = _current_user(request)
    return _get_authorized_task(task_id, user).to_dict()


@router.post("/api/opportunities/tasks/{task_id}/cancel")
def cancel_opportunity_task(task_id: str, request: Request = None) -> dict:
    user = _current_user(request, auth.PERMISSION_OPPORTUNITY_RUN)
    _get_authorized_task(task_id, user)
    result = opportunity_tasks.cancel_opportunity_task(task_id)
    return {
        "canceled": result in {"requested", "canceled", "already_terminal"},
        "task_id": task_id,
        "status": result,
    }


@router.get("/api/opportunities/tasks/{task_id}/stream")
async def stream_opportunity_task(
    task_id: str, request: Request, cursor: int = 0
) -> StreamingResponse:
    user = _current_user(request)
    _get_authorized_task(task_id, user)
    return await task_route_support.stream_task_progress(
        request=request,
        get_task=lambda: _get_authorized_task(task_id, user),
        get_progress_events=lambda cursor: opportunity_tasks.get_progress_events(
            task_id, cursor
        ),
        start_cursor=max(cursor, 0),
    )


@router.post("/api/opportunities/candidates/{symbol}/analyze")
def analyze_candidate(
    symbol: str, payload: CandidateAnalyzePayload, request: Request = None
) -> dict:
    user = _current_user(request, auth.PERMISSION_ANALYSIS_CREATE)
    context = (
        payload.opportunity_context
        or opportunity_service.build_candidate_opportunity_context(
            symbol, payload.run_id, user
        )
    )
    analysis_date = payload.analysis_date or date.today().isoformat()
    try:
        analysis_request = AnalysisRequest(
            ticker=symbol,
            analysis_date=analysis_date,
            analysts=list(ANALYST_ORDER),
            research_depth=3,
            model_profile=payload.model_profile or "default",
            llm_provider="openai",
            quick_think_llm="gpt-4o-mini",
            deep_think_llm="gpt-4o",
            output_language=(
                payload.output_language
                or preferred_output_language_from_request(request)
                or "cn"
            ),
            openai_reasoning_effort="medium",
            opportunity_context=context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = analysis_tasks.create_task(
        analysis_request,
        owner_user_id=user.id if user else None,
        tenant_id=getattr(user, "tenant_id", None),
        report_visibility=payload.report_visibility,
    )
    if user is not None and getattr(user, "tenant_id", None) is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=user.tenant_id,
                actor_user_id=user.id,
                action="opportunity.analysis_triggered",
                resource_type="analysis_task",
                resource_id=str(result.get("task_id")),
                metadata={"symbol": symbol, "run_id": payload.run_id},
                request=request,
            )
    return result
