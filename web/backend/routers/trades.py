from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from web.backend import auth
from web.backend.schemas.trades import (
    TradeRecordCreatePayload,
    TradeRecordUpdatePayload,
    TradeReviewCreatePayload,
    TradeReviewSavePayload,
)
from web.backend.services import trades as trade_service

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


@router.get("/api/trades")
def list_trades(ticker: str | None = None, request: Request = None) -> list[dict]:
    return trade_service.list_trades(ticker=ticker, request=request)


@router.post("/api/trades")
def create_trade(payload: TradeRecordCreatePayload, request: Request = None) -> dict:
    return trade_service.create_trade(payload, request)


@router.get("/api/trades/{trade_id}")
def get_trade(trade_id: str, request: Request = None) -> dict:
    return trade_service.get_trade(trade_id, request)


@router.put("/api/trades/{trade_id}")
def update_trade(
    trade_id: str,
    payload: TradeRecordUpdatePayload,
    request: Request = None,
) -> dict:
    return trade_service.update_trade(trade_id, payload, request)


@router.get("/api/trades/{trade_id}/reviews")
def get_trade_reviews(trade_id: str, request: Request = None) -> list[dict]:
    return trade_service.get_trade_reviews(trade_id, request)


@router.post("/api/trades/{trade_id}/reviews")
def create_trade_review(
    trade_id: str,
    payload: TradeReviewCreatePayload,
    request: Request = None,
) -> dict:
    return trade_service.create_trade_review(trade_id, payload, request)


@router.put(
    "/api/trades/{trade_id}/reviews/{review_type}",
)
def save_trade_review(
    trade_id: str,
    review_type: str,
    payload: TradeReviewSavePayload,
    request: Request = None,
) -> dict:
    return trade_service.save_trade_review(trade_id, review_type, payload, request)


@router.get("/api/trade-feedback/{ticker}")
def get_ticker_trade_feedback(
    ticker: str,
    limit: int = 3,
    analysis_date: str | None = None,
    request: Request = None,
) -> dict:
    return trade_service.get_ticker_trade_feedback(
        ticker,
        limit=limit,
        analysis_date=analysis_date,
        request=request,
    )
