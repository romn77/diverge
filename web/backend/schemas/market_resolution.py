from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MarketResolutionPayload(BaseModel):
    raw_symbol: str
    canonical_symbol: str
    display_symbol: str
    market: Literal["cn", "us", "unknown"]
    exchange: str | None = None
    asset_type: Literal["equity", "etf", "unknown"]
    confidence: Literal["high", "medium", "low", "manual"]
    source: Literal["manifest", "rule", "manual", "unknown"]
    warnings: list[str] = Field(default_factory=list)
