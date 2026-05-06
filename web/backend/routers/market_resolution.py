from __future__ import annotations

from fastapi import APIRouter, Depends

from diverge.markets import resolve_symbol
from web.backend import auth

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


@router.get("/api/market-resolution")
def resolve_market_symbol(
    symbol: str,
    manual_market: str | None = None,
    manual_exchange: str | None = None,
    manual_asset_type: str | None = None,
) -> dict:
    return resolve_symbol(
        symbol,
        manual_market=manual_market,
        manual_exchange=manual_exchange,
        manual_asset_type=manual_asset_type,
    )
