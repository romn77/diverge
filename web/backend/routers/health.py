from __future__ import annotations

from fastapi import APIRouter

from web.backend import auth

router = APIRouter()


@router.get("/api/healthz")
def healthz() -> dict:
    settings = auth.get_auth_settings()
    return {
        "status": "ok",
        "auth": {"enabled": settings.enabled, "mode": settings.mode},
    }
