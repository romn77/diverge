from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from web.backend import access, auth
from web.backend.runtime import backtest_tasks
from web.backend.schemas.backtests import BacktestSnapshotPayload
from web.backend.services import backtests, opportunities

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


def _current_user(
    request: Request | None, permission: str = auth.PERMISSION_OPPORTUNITY_READ
):
    opportunities.require_enabled()
    if not auth.auth_enabled() or request is None:
        return None
    with auth.db_session() as db:
        return access.require_permission(db, request, permission)


@router.post("/api/backtests/snapshot")
def create_snapshot(payload: BacktestSnapshotPayload, request: Request = None) -> dict:
    user = _current_user(request, auth.PERMISSION_OPPORTUNITY_RUN)
    return backtest_tasks.create_backtest_task(
        request_payload=payload.model_dump(),
        owner_user_id=user.id if user else None,
        tenant_id=getattr(user, "tenant_id", None),
    )


@router.get("/api/backtests/tasks")
def list_backtest_tasks(request: Request = None) -> list[dict]:
    user = _current_user(request)
    return [
        task.to_dict()
        for task in backtest_tasks.list_tasks()
        if not auth.auth_enabled() or task.tenant_id == getattr(user, "tenant_id", None)
    ]


@router.get("/api/backtests/{run_id}")
def get_snapshot(run_id: str, request: Request = None) -> dict:
    user = _current_user(request)
    return backtests.get_snapshot(run_id, user)


@router.get("/api/backtests/{run_id}/metrics")
def get_metrics(run_id: str, request: Request = None) -> dict:
    user = _current_user(request)
    return backtests.get_metrics(run_id, user)


@router.get("/api/backtests/{run_id}/signals")
def get_signals(run_id: str, request: Request = None) -> list[dict]:
    user = _current_user(request)
    return backtests.get_signals(run_id, user)


@router.get("/api/backtests/{run_id}/outcomes")
def get_outcomes(run_id: str, request: Request = None) -> list[dict]:
    user = _current_user(request)
    return backtests.get_outcomes(run_id, user)


@router.get("/api/backtests/{run_id}/parameter-scan")
def get_parameter_scan(run_id: str, request: Request = None) -> list[dict]:
    user = _current_user(request)
    return backtests.get_parameter_scan(run_id, user)
