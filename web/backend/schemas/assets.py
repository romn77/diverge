from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class AssetPositionCreatePayload(BaseModel):
    platform_name: str
    account_name: str
    asset_name: str
    asset_category: str
    quantity: float
    cost_basis: float
    valuation_mode: Literal["market", "manual"] = "market"
    ticker: Optional[str] = None
    market: Optional[str] = None
    exchange: Optional[str] = None
    quote_type: Optional[str] = None
    resolved_name: Optional[str] = None
    currency: Optional[str] = None
    manual_price: Optional[float] = None
    notes: Optional[str] = None


class AssetPositionUpdatePayload(BaseModel):
    platform_name: Optional[str] = None
    account_name: Optional[str] = None
    asset_name: Optional[str] = None
    asset_category: Optional[str] = None
    quantity: Optional[float] = None
    cost_basis: Optional[float] = None
    valuation_mode: Optional[Literal["market", "manual"]] = None
    ticker: Optional[str] = None
    market: Optional[str] = None
    exchange: Optional[str] = None
    quote_type: Optional[str] = None
    resolved_name: Optional[str] = None
    currency: Optional[str] = None
    manual_price: Optional[float] = None
    notes: Optional[str] = None


class AssetRefreshPayload(BaseModel):
    base_currency: str = "USD"
    force: bool = False
