from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request

from web.backend import access, auth
from web.backend.schemas.assets import (
    AssetPositionCreatePayload,
    AssetPositionUpdatePayload,
    AssetRefreshPayload,
)
from web.backend.services import assets as asset_service

router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


def _run_asset_route(operation: Callable[[], dict | list[dict]]) -> dict | list[dict]:
    try:
        return operation()
    except HTTPException:
        raise
    except Exception as exc:
        raise asset_service.translate_asset_error(exc) from exc


def _require_asset_permission(request: Request | None, permission: str) -> None:
    if not auth.auth_enabled():
        return
    with auth.db_session() as db:
        access.require_permission(db, request, permission)


@router.get("/api/assets")
def list_assets(request: Request = None) -> list[dict]:
    _require_asset_permission(request, auth.PERMISSION_ASSETS_READ)
    return _run_asset_route(lambda: asset_service.list_asset_positions(request))


@router.get("/api/assets/summary")
def get_asset_summary(
    base_currency: str = "USD",
    refresh_if_stale: bool = False,
    request: Request = None,
) -> dict:
    _require_asset_permission(request, auth.PERMISSION_ASSETS_READ)
    if refresh_if_stale:
        _require_asset_permission(request, auth.PERMISSION_ASSETS_WRITE)
    return _run_asset_route(
        lambda: asset_service.get_asset_summary(
            base_currency=base_currency,
            refresh_if_stale=refresh_if_stale,
            request=request,
        )
    )


@router.post("/api/assets")
def create_asset(payload: AssetPositionCreatePayload, request: Request = None) -> dict:
    _require_asset_permission(request, auth.PERMISSION_ASSETS_WRITE)
    return _run_asset_route(lambda: asset_service.create_asset_position(payload, request))


@router.get("/api/assets/{position_id}")
def get_asset(position_id: str, request: Request = None) -> dict:
    _require_asset_permission(request, auth.PERMISSION_ASSETS_READ)
    return _run_asset_route(lambda: asset_service.get_asset_position(position_id, request))


@router.put("/api/assets/{position_id}")
def update_asset(
    position_id: str,
    payload: AssetPositionUpdatePayload,
    request: Request = None,
) -> dict:
    _require_asset_permission(request, auth.PERMISSION_ASSETS_WRITE)
    return _run_asset_route(
        lambda: asset_service.update_asset_position(position_id, payload, request)
    )


@router.delete("/api/assets/{position_id}")
def delete_asset(position_id: str, request: Request = None) -> dict:
    _require_asset_permission(request, auth.PERMISSION_ASSETS_WRITE)
    return _run_asset_route(lambda: asset_service.delete_asset_position(position_id, request))


@router.post("/api/assets/{position_id}/refresh")
def refresh_asset(
    position_id: str,
    payload: AssetRefreshPayload,
    request: Request = None,
) -> dict:
    _require_asset_permission(request, auth.PERMISSION_ASSETS_WRITE)
    return _run_asset_route(
        lambda: asset_service.refresh_asset_position(
            position_id,
            base_currency=payload.base_currency,
            request=request,
        )
    )


@router.post("/api/assets/refresh")
def refresh_assets(payload: AssetRefreshPayload, request: Request = None) -> list[dict]:
    _require_asset_permission(request, auth.PERMISSION_ASSETS_WRITE)
    return _run_asset_route(
        lambda: asset_service.refresh_due_asset_positions(
            base_currency=payload.base_currency,
            force=payload.force,
            request=request,
        )
    )
