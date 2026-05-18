from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from web.backend import access, auth
from web.backend.schemas.trades import (
    TradePlanCreatePayload,
    TradePlanExecutePayload,
    TradePlanLinkPayload,
    TradePlanUpdatePayload,
    TradeRecordCreatePayload,
    TradeRecordUpdatePayload,
    TradeReviewGeneratePayload,
    TradeReviewSavePayload,
)
from web.backend.services import trades as trade_service

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


def _require_journal_permission(request: Request | None, permission: str) -> None:
    if not auth.auth_enabled():
        return
    with auth.db_session() as db:
        access.require_permission(db, request, permission)


@router.get("/api/trades")
def list_trades(ticker: str | None = None, request: Request = None) -> list[dict]:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_READ)
    return trade_service.list_trades(ticker=ticker, request=request)


@router.get("/api/journal/review-tasks")
def list_trade_review_activity(request: Request = None) -> list[dict]:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_READ)
    return trade_service.list_trade_review_activity(request)


@router.get("/api/trade-plans")
def list_trade_plans(
    ticker: str | None = None,
    status: str | None = "planned",
    request: Request = None,
) -> list[dict]:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_READ)
    return trade_service.list_trade_plans(ticker=ticker, status=status, request=request)


@router.post("/api/trade-plans")
def create_trade_plan(
    payload: TradePlanCreatePayload,
    request: Request = None,
) -> dict:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_WRITE)
    return trade_service.create_trade_plan(payload, request)


@router.get("/api/trade-plans/{plan_id}")
def get_trade_plan(plan_id: str, request: Request = None) -> dict:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_READ)
    return trade_service.get_trade_plan(plan_id, request)


@router.put("/api/trade-plans/{plan_id}")
def update_trade_plan(
    plan_id: str,
    payload: TradePlanUpdatePayload,
    request: Request = None,
) -> dict:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_WRITE)
    return trade_service.update_trade_plan(plan_id, payload, request)


@router.delete("/api/trade-plans/{plan_id}")
def delete_trade_plan(plan_id: str, request: Request = None) -> dict:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_WRITE)
    return trade_service.delete_trade_plan(plan_id, request)


@router.post("/api/trade-plans/{plan_id}/execute")
def execute_trade_plan(
    plan_id: str,
    payload: TradePlanExecutePayload,
    request: Request = None,
) -> dict:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_WRITE)
    return trade_service.execute_trade_plan(plan_id, payload, request)


@router.post("/api/trades")
def create_trade(payload: TradeRecordCreatePayload, request: Request = None) -> dict:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_WRITE)
    return trade_service.create_trade(payload, request)


@router.get("/api/trades/{trade_id}")
def get_trade(trade_id: str, request: Request = None) -> dict:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_READ)
    return trade_service.get_trade(trade_id, request)


@router.put("/api/trades/{trade_id}")
def update_trade(
    trade_id: str,
    payload: TradeRecordUpdatePayload,
    request: Request = None,
) -> dict:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_WRITE)
    return trade_service.update_trade(trade_id, payload, request)


@router.post("/api/trades/{trade_id}/link-plan")
def link_trade_to_plan(
    trade_id: str,
    payload: TradePlanLinkPayload,
    request: Request = None,
) -> dict:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_WRITE)
    return trade_service.link_trade_to_plan(trade_id, payload, request)


@router.get("/api/trades/{trade_id}/reviews")
def get_trade_reviews(trade_id: str, request: Request = None) -> list[dict]:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_READ)
    return trade_service.get_trade_reviews(trade_id, request)


@router.post("/api/trades/{trade_id}/reviews/{review_type}/generate")
def generate_trade_review(
    trade_id: str,
    review_type: str,
    payload: TradeReviewGeneratePayload,
    request: Request = None,
) -> dict:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_WRITE)
    return trade_service.generate_configured_trade_review(
        trade_id,
        review_type,
        payload,
        request,
    )


@router.put(
    "/api/trades/{trade_id}/reviews/{review_type}",
)
def save_trade_review(
    trade_id: str,
    review_type: str,
    payload: TradeReviewSavePayload,
    request: Request = None,
) -> dict:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_WRITE)
    return trade_service.save_trade_review(trade_id, review_type, payload, request)


@router.get("/api/trade-feedback/{ticker}")
def get_ticker_trade_feedback(
    ticker: str,
    limit: int = 3,
    analysis_date: str | None = None,
    request: Request = None,
) -> dict:
    _require_journal_permission(request, auth.PERMISSION_JOURNAL_READ)
    return trade_service.get_ticker_trade_feedback(
        ticker,
        limit=limit,
        analysis_date=analysis_date,
        request=request,
    )
