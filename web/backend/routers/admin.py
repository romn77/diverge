from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from tradingagents.dataflows import vendor_usage
from web.backend import access, analysis_limits, auth, data_sources
from web.backend.runtime import analysis_tasks, screener_tasks, task_store
from web.backend.schemas.admin import (
    AdminAnalysisLimitsUpdatePayload,
    AdminDataSourceRouteUpdatePayload,
    AdminDataSourceUpdatePayload,
    AdminUserCreatePayload,
    AdminUserResetPasswordPayload,
    AdminUserUpdatePayload,
)

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(auth.enforce_admin_api_access)])


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_admin_user_lookup() -> dict[str, dict]:
    with auth.db_session() as db:
        return {user.id: auth.serialize_user(user) for user in auth.list_users(db)}


def _normalize_queue_status(status: object) -> str:
    normalized = str(status or "pending")
    if task_store.redis_task_backend_enabled() and normalized == "pending":
        return "queued"
    return normalized


def _analysis_label(payload: dict) -> str:
    request_payload = payload.get("request_payload")
    if isinstance(request_payload, dict) and request_payload.get("ticker"):
        return str(request_payload["ticker"])
    if payload.get("ticker"):
        return str(payload["ticker"])
    return str(payload.get("id") or "Analysis task")


def _screener_label(payload: dict) -> str:
    request_payload = payload.get("request_payload")
    if isinstance(request_payload, dict):
        markets = request_payload.get("markets")
        if isinstance(markets, list) and markets:
            return ", ".join(str(market) for market in markets)
    return str(payload.get("id") or "Screener task")


def _active_task_payloads(kind: str) -> list[dict]:
    if task_store.redis_task_backend_enabled():
        return task_store.get_task_store().list_tasks(kind)
    if kind == "analysis":
        return [task.to_dict() for task in analysis_tasks.list_tasks()]
    return [task.to_dict() for task in screener_tasks.list_screener_tasks()]


def _queue_position(kind: str, task_id: str, payload: dict) -> int | None:
    if task_store.redis_task_backend_enabled():
        return task_store.get_task_store().queue_position(kind, task_id)
    value = payload.get("queue_position")
    return value if isinstance(value, int) else None


def _serialize_queue_item(
    *,
    kind: str,
    payload: dict,
    user_lookup: dict[str, dict],
) -> dict:
    task_id = str(payload.get("id") or "")
    status = _normalize_queue_status(payload.get("status"))
    owner_user_id = payload.get("owner_user_id")
    owner = user_lookup.get(str(owner_user_id)) if owner_user_id else None
    label = _analysis_label(payload) if kind == "analysis" else _screener_label(payload)
    return {
        "kind": kind,
        "task_id": task_id,
        "label": label,
        "status": status,
        "owner_user_id": owner_user_id,
        "owner": owner,
        "created_at": payload.get("created_at"),
        "queued_at": payload.get("queued_at"),
        "started_at": payload.get("started_at"),
        "finished_at": payload.get("finished_at"),
        "queue_position": _queue_position(kind, task_id, payload),
        "blocked_reason": payload.get("blocked_reason"),
        "blocked_vendor": payload.get("blocked_vendor"),
        "blocked_until": payload.get("blocked_until"),
        "detail_path": f"/tasks/{task_id}" if kind == "analysis" else f"/screener-tasks/{task_id}",
    }


def _queue_sort_key(item: dict) -> tuple[int, int, str, str]:
    status_priority = {
        "running": 0,
        "queued": 1,
        "pending": 1,
        "waiting_for_quota": 2,
    }.get(str(item["status"]), 9)
    queue_position = item.get("queue_position")
    position = queue_position if isinstance(queue_position, int) else 999_999
    timestamp = (
        item.get("started_at")
        or item.get("queued_at")
        or item.get("blocked_until")
        or item.get("created_at")
        or ""
    )
    return (status_priority, position, str(timestamp), str(item["task_id"]))


@router.get("/api/admin/task-queue")
def list_admin_task_queue() -> dict:
    try:
        user_lookup = _load_admin_user_lookup()
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc

    items: list[dict] = []
    for kind in ("analysis", "screener"):
        for payload in _active_task_payloads(kind):
            status = _normalize_queue_status(payload.get("status"))
            if status not in task_store.ACTIVE_STATUSES:
                continue
            items.append(
                _serialize_queue_item(
                    kind=kind,
                    payload=payload,
                    user_lookup=user_lookup,
                )
            )
    items.sort(key=_queue_sort_key)
    totals = {
        "active": len(items),
        "queued": sum(1 for item in items if item["status"] in task_store.QUEUED_STATUSES),
        "running": sum(1 for item in items if item["status"] == "running"),
        "waiting_for_quota": sum(
            1 for item in items if item["status"] == "waiting_for_quota"
        ),
    }
    return {
        "task_backend": os.environ.get("TASK_BACKEND", "local").strip().lower(),
        "generated_at": _utc_iso(),
        "totals": totals,
        "tasks": items,
    }


@router.get("/api/admin/users")
def list_admin_users() -> list[dict]:
    try:
        with auth.db_session() as db:
            users = auth.list_users(db)
            return [
                {
                    **auth.serialize_user(user),
                    "usage": analysis_limits.build_user_weekly_usage_summary(db, user),
                }
                for user in users
            ]
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


@router.get("/api/admin/analysis-limits")
def list_admin_analysis_limits() -> dict:
    try:
        with auth.db_session() as db:
            return {"limits": analysis_limits.list_role_limits(db)}
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


@router.put("/api/admin/analysis-limits")
def update_admin_analysis_limits(
    payload: AdminAnalysisLimitsUpdatePayload,
    request: Request,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = auth.require_request_user(db, request)
            limits = analysis_limits.update_role_limits(
                db,
                [item.model_dump() for item in payload.limits],
            )
            result = {"limits": limits}
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
    logger.info(
        "admin analysis limits updated actor_user_id=%s roles=%s",
        actor.id,
        ",".join(row["role"] for row in result["limits"]),
    )
    return result


@router.get("/api/admin/data-sources")
def list_admin_data_sources() -> dict:
    return vendor_usage.get_data_source_usage_summary()


@router.put("/api/admin/data-sources/{vendor}")
def update_admin_data_source(
    vendor: str,
    payload: AdminDataSourceUpdatePayload,
) -> dict:
    try:
        source = vendor_usage.update_data_source_config(
            vendor,
            enabled=payload.enabled,
            daily_limit=payload.daily_limit,
            hourly_limit=payload.hourly_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info(
        "admin data source updated vendor=%s enabled=%s daily_limit=%s hourly_limit=%s",
        source["vendor"],
        source["enabled"],
        source["daily_limit"],
        source["hourly_limit"],
    )
    return {"source": source}


@router.put("/api/admin/data-source-routes/{module}/{market}/{category}")
def update_admin_data_source_route(
    module: str,
    market: str,
    category: str,
    payload: AdminDataSourceRouteUpdatePayload,
) -> dict:
    try:
        route = data_sources.update_data_source_route(
            module=module,
            market=market,
            category=category,
            vendor_chain=payload.vendor_chain,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info(
        "admin data source route updated module=%s market=%s category=%s vendor_chain=%s",
        route["module"],
        route["market"],
        route["category"],
        ",".join(route["vendor_chain"]),
    )
    return {"route": route}


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


@router.post("/api/admin/users/{user_id}/usage/reset")
def reset_admin_user_usage(user_id: str, request: Request) -> dict:
    try:
        with auth.db_session() as db:
            actor = auth.require_request_user(db, request)
            user = auth.get_user_by_id(db, user_id)
            reset_count = analysis_limits.reset_user_weekly_usage(db, user_id)
            result = {
                "user_id": user_id,
                "reset_count": reset_count,
                "usage": analysis_limits.build_user_weekly_usage_summary(db, user),
            }
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
    logger.info(
        "admin user weekly usage reset actor_user_id=%s target_user_id=%s reset_count=%s",
        actor.id,
        user_id,
        reset_count,
    )
    return result
