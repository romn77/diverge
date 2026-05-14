from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response

from web.backend import access, audit, auth
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
        return auth.build_auth_state_payload(user, db=db)


@router.post("/api/auth/login")
def login(payload: LoginPayload, request: Request, response: Response) -> dict:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        raise HTTPException(status_code=409, detail="Auth is disabled")
    client_ip = auth.client_ip_for_request(request)
    login_identifier = payload.login_identifier
    normalized_identifier = login_identifier.strip().lower()
    auth.ensure_login_allowed(login_identifier, client_ip)

    try:
        with auth.db_session() as db:
            user = auth.authenticate_user(
                db,
                account=login_identifier,
                password=payload.password,
            )
            session_token = auth.create_user_session(
                db,
                user,
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent"),
                settings=settings,
            )
            audit.record_audit_event_safely(
                db,
                tenant_id=user.tenant_id,
                actor_user_id=user.id,
                action="auth.login.success",
                resource_type="session",
                metadata={"email": user.email, "role": user.role},
                request=request,
            )
            result = auth.build_auth_state_payload(user, db=db)
    except auth.AuthValidationError as exc:
        auth.record_login_failure(login_identifier, client_ip)
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=None,
                actor_user_id=None,
                action="auth.login.failed",
                resource_type="session",
                metadata={"account": normalized_identifier},
                request=request,
            )
        logger.warning(
            "login failed account=%s ip=%s reason=%s",
            normalized_identifier,
            client_ip,
            exc,
        )
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except auth.AuthPermissionError as exc:
        auth.record_login_failure(login_identifier, client_ip)
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=None,
                actor_user_id=None,
                action="auth.login.denied",
                resource_type="session",
                metadata={"account": normalized_identifier},
                request=request,
            )
        logger.warning(
            "login denied account=%s ip=%s reason=%s",
            normalized_identifier,
            client_ip,
            exc,
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc

    auth.clear_login_failures(login_identifier, client_ip)
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
            session_record = auth.current_session_record(db, request)
            if session_record is not None:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=session_record.user.tenant_id,
                    actor_user_id=session_record.user_id,
                    action="auth.logout",
                    resource_type="session",
                    resource_id=session_record.id,
                    request=request,
                )
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
            audit.record_audit_event_safely(
                db,
                tenant_id=user.tenant_id,
                actor_user_id=user.id,
                action="auth.password_changed",
                resource_type="user",
                resource_id=user.id,
                request=request,
            )
            session_token = auth.create_user_session(
                db,
                user,
                ip_address=auth.client_ip_for_request(request),
                user_agent=request.headers.get("user-agent"),
                settings=settings,
            )
            result = auth.build_auth_state_payload(user, db=db)
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc

    auth.set_session_cookie(response, session_token)
    return result
