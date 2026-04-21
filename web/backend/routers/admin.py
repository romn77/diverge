from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from web.backend import access, auth
from web.backend.schemas.admin import (
    AdminUserCreatePayload,
    AdminUserResetPasswordPayload,
    AdminUserUpdatePayload,
)

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(auth.enforce_admin_api_access)])


@router.get("/api/admin/users")
def list_admin_users() -> list[dict]:
    try:
        with auth.db_session() as db:
            return [auth.serialize_user(user) for user in auth.list_users(db)]
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


@router.get("/api/admin/users/{user_id}")
def get_admin_user(user_id: str) -> dict:
    try:
        with auth.db_session() as db:
            return auth.serialize_user(auth.get_user_by_id(db, user_id))
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


@router.post("/api/admin/users")
def create_admin_user(payload: AdminUserCreatePayload, request: Request) -> dict:
    try:
        with auth.db_session() as db:
            actor = auth.require_request_user(db, request)
            user = auth.create_user(
                db,
                email=payload.email,
                display_name=payload.display_name,
                password=payload.password,
                role=payload.role,
                status=payload.status,
                must_change_password=payload.must_change_password,
            )
            result = auth.serialize_user(user)
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
    logger.info(
        "admin user created actor_user_id=%s target_user_id=%s role=%s status=%s",
        actor.id,
        user.id,
        user.role,
        user.status,
    )
    return result


@router.put("/api/admin/users/{user_id}")
def update_admin_user(
    user_id: str,
    payload: AdminUserUpdatePayload,
    request: Request,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = auth.require_request_user(db, request)
            user = auth.update_user(
                db,
                user_id,
                display_name=payload.display_name,
                role=payload.role,
                status=payload.status,
                must_change_password=payload.must_change_password,
            )
            result = auth.serialize_user(user)
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
    logger.info(
        "admin user updated actor_user_id=%s target_user_id=%s role=%s status=%s",
        actor.id,
        user.id,
        user.role,
        user.status,
    )
    return result


@router.delete("/api/admin/users/{user_id}")
def delete_admin_user(user_id: str, request: Request) -> dict:
    try:
        with auth.db_session() as db:
            actor = auth.require_request_user(db, request)
            auth.delete_user(db, user_id)
            result = {"deleted": True, "user_id": user_id}
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
    logger.info(
        "admin user deleted actor_user_id=%s target_user_id=%s",
        actor.id,
        user_id,
    )
    return result


@router.post(
    "/api/admin/users/{user_id}/reset-password",
)
def reset_admin_user_password(
    user_id: str,
    payload: AdminUserResetPasswordPayload,
    request: Request,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = auth.require_request_user(db, request)
            user = auth.reset_user_password(
                db,
                user_id,
                new_password=payload.new_password,
                must_change_password=payload.must_change_password,
            )
            result = auth.serialize_user(user)
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
    logger.info(
        "admin user password reset actor_user_id=%s target_user_id=%s",
        actor.id,
        user.id,
    )
    return result
