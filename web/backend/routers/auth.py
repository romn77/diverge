from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response

from web.backend import access, auth
from web.backend.schemas.auth import ChangePasswordPayload, LoginPayload

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/auth/me")
def get_current_auth_state(request: Request) -> dict:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        return auth.build_auth_state_payload(None)

    with auth.db_session() as db:
        user = auth.get_request_user(db, request, settings=settings)
        return auth.build_auth_state_payload(user)


@router.post("/api/auth/login")
def login(payload: LoginPayload, request: Request, response: Response) -> dict:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        raise HTTPException(status_code=409, detail="Auth is disabled")
    client_ip = request.client.host if request.client else None
    auth.ensure_login_allowed(payload.email, client_ip)

    try:
        with auth.db_session() as db:
            user = auth.authenticate_user(
                db,
                email=payload.email,
                password=payload.password,
            )
            session_token = auth.create_user_session(
                db,
                user,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                settings=settings,
            )
            result = auth.build_auth_state_payload(user)
    except auth.AuthValidationError as exc:
        auth.record_login_failure(payload.email, client_ip)
        logger.warning(
            "login failed email=%s ip=%s reason=%s",
            payload.email.strip().lower(),
            client_ip,
            exc,
        )
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except auth.AuthPermissionError as exc:
        auth.record_login_failure(payload.email, client_ip)
        logger.warning(
            "login denied email=%s ip=%s reason=%s",
            payload.email.strip().lower(),
            client_ip,
            exc,
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc

    auth.clear_login_failures(payload.email, client_ip)
    auth.set_session_cookie(response, session_token)
    logger.info(
        "login success user_id=%s email=%s role=%s ip=%s",
        user.id,
        user.email,
        user.role,
        client_ip,
    )
    return result


@router.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict:
    settings = auth.get_auth_settings()
    if settings.enabled:
        with auth.db_session() as db:
            auth.revoke_session_token(db, auth.current_session_token(request))
    auth.clear_session_cookie(response)
    return auth.build_auth_state_payload(None)


@router.post("/api/auth/change-password")
def change_password(
    payload: ChangePasswordPayload,
    request: Request,
    response: Response,
) -> dict:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        raise HTTPException(status_code=409, detail="Auth is disabled")

    try:
        with auth.db_session() as db:
            user = auth.require_request_user(db, request)
            auth.change_user_password(
                db,
                user,
                current_password=payload.current_password,
                new_password=payload.new_password,
            )
            session_token = auth.create_user_session(
                db,
                user,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                settings=settings,
            )
            result = auth.build_auth_state_payload(user)
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc

    auth.set_session_cookie(response, session_token)
    return result
