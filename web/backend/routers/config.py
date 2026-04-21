from __future__ import annotations

from fastapi import APIRouter, Depends

from web.backend import auth
from web.backend.services.config import (
    get_config_options_payload,
    get_screener_config_options_payload,
)

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


@router.get("/api/config/options")
def get_config_options() -> dict:
    return get_config_options_payload()


@router.get("/api/screener/config/options")
def get_screener_config_options() -> dict:
    return get_screener_config_options_payload()
