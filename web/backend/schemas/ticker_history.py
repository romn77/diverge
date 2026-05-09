from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from diverge.market_data.price_history import LOOKBACK_DAYS


class TickerHistoryBatchItemPayload(BaseModel):
    symbol: str
    market: Optional[str] = None


class TickerHistoryBatchPayload(BaseModel):
    tickers: list[TickerHistoryBatchItemPayload]
    as_of_date: Optional[str] = None
    days: int = LOOKBACK_DAYS
