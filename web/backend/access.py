from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from web.backend import auth, trade_entries


def translate_auth_error(exc: Exception) -> HTTPException:
    if isinstance(exc, auth.AuthNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, auth.AuthConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, auth.AuthPermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, auth.AuthDisabledError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, auth.AuthValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


def is_admin_user(user: auth.User | None) -> bool:
    return user is not None and user.role == auth.UserRole.ADMIN.value


def owner_scope_for_user(user: auth.User | None) -> str | None:
    if user is None or is_admin_user(user):
        return None
    return user.id


def get_request_user_with_password_change(
    db: Any,
    request: Request,
    *,
    settings: auth.AuthSettings | None = None,
) -> auth.User | None:
    user = auth.get_request_user(db, request, settings=settings)
    if user is not None:
        auth.enforce_password_change_completed(user, request)
    return user


def require_trade_request_user(db: Any, request: Request | None) -> auth.User | None:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        return None
    if request is None:
        raise HTTPException(status_code=500, detail="Trade request context is missing")

    user = get_request_user_with_password_change(db, request, settings=settings)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def visible_trade_ids_for_task(task: Any) -> set[str] | None:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        return None
    if not getattr(task, "owner_user_id", None):
        return set()

    with auth.db_session() as db:
        return trade_entries.list_visible_trade_ids(
            db,
            task.owner_user_id,
            ticker=task.request.ticker,
        )


def resolve_task_owner_user_id(request: Request | None) -> str | None:
    settings = auth.get_auth_settings()
    if not settings.enabled or request is None:
        return None

    with auth.db_session() as db:
        user = get_request_user_with_password_change(db, request, settings=settings)
        if user is None:
            return None
        return user.id


def require_screener_user(request: Request | None) -> auth.User | None:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        return None
    if request is None:
        raise HTTPException(status_code=500, detail="Request context is required")
    with auth.db_session() as db:
        return auth.require_request_user_role(
            db,
            request,
            (
                auth.UserRole.ADMIN.value,
                auth.UserRole.OPERATOR.value,
                auth.UserRole.VIEWER.value,
            ),
        )


def can_access_screener_owner(user: auth.User | None, owner_user_id: str | None) -> bool:
    if user is None:
        return True
    return can_access_owner(user, owner_user_id)


def can_access_owner(
    user: auth.User | None,
    owner_user_id: str | None,
    *,
    allow_unowned: bool = False,
) -> bool:
    if owner_user_id is None:
        return allow_unowned
    if user is None:
        return False
    if is_admin_user(user):
        return True
    return owner_user_id == user.id
