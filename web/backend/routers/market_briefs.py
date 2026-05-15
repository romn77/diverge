from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from web.backend import auth
from web.backend.services import market_briefs as market_brief_service

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


@router.get("/api/market-briefs")
def list_market_briefs(request: Request = None) -> dict:
    return market_brief_service.list_market_briefs(request)
