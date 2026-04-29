from __future__ import annotations

from fastapi import APIRouter, Depends

from diverge.screener.market_data import LOOKBACK_DAYS
from web.backend import auth
from web.backend.schemas.ticker_history import TickerHistoryBatchPayload
from web.backend.services.ticker_history import (
    get_batch_ticker_history_payload,
    get_ticker_history_payload,
)

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


@router.get("/api/ticker-history")
def get_ticker_history_endpoint(
    symbol: str,
    market: str | None = None,
    as_of_date: str | None = None,
    days: int = LOOKBACK_DAYS,
) -> dict:
    return get_ticker_history_payload(
        symbol,
        market=market,
        as_of_date=as_of_date,
        days=days,
        include_ohlcv=True,
    )


@router.post("/api/ticker-history/batch")
def get_batch_ticker_history_endpoint(payload: TickerHistoryBatchPayload) -> dict:
    return get_batch_ticker_history_payload(payload)
