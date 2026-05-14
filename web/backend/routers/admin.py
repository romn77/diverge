from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from diverge.dataflows import vendor_usage
from web.backend import (
    access,
    analysis_limits,
    audit,
    auth,
    data_sources,
    job_records,
    llm_models,
    search_quota,
)
from web.backend.runtime import (
    analysis_tasks,
    data_sync_tasks,
    screener_tasks,
    task_store,
)
from web.backend.schemas.admin import (
    AdminAnalysisLimitsUpdatePayload,
    AdminDataSourceRouteUpdatePayload,
    AdminDataSourceUpdatePayload,
    AdminLLMModelUpdatePayload,
    AdminLLMModuleSettingUpdatePayload,
    AdminLLMProfileRoutesUpdatePayload,
    AdminLLMProfileUpdatePayload,
    AdminLLMProviderUpdatePayload,
    AdminLLMUiSettingUpdatePayload,
    AdminUserCreatePayload,
    AdminUserResetPasswordPayload,
    AdminUserUpdatePayload,
    SearchGlobalUpdatePayload,
    SearchProviderUpdatePayload,
)

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(auth.enforce_authenticated_api_access)])


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime_filter(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _require_admin_permission(
    request: Request | None, permission: str
) -> auth.User | None:
    if request is None or not auth.auth_enabled():
        return None
    with auth.db_session() as db:
        return access.require_permission(db, request, permission)


def _require_db_admin_permission(
    db,
    request: Request | None,
    permission: str,
) -> auth.User | None:
    if request is None or not auth.auth_enabled():
        return None
    return access.require_permission(db, request, permission)


def _ensure_same_tenant(actor: auth.User | None, target: auth.User) -> None:
    if actor is not None and target.tenant_id != actor.tenant_id:
        raise auth.AuthNotFoundError(f"User '{target.id}' not found")


def _load_admin_user_lookup(tenant_id: str | None = None) -> dict[str, dict]:
    with auth.db_session() as db:
        return {
            user.id: auth.serialize_user(user)
            for user in auth.list_users(db, tenant_id=tenant_id)
        }


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


def _data_sync_label(payload: dict) -> str:
    sync_type = str(payload.get("sync_type") or "data sync")
    request_payload = payload.get("request_payload")
    if isinstance(request_payload, dict):
        markets = request_payload.get("markets")
        if isinstance(markets, list) and markets:
            return f"{sync_type}: {', '.join(str(market) for market in markets)}"
        market = request_payload.get("market")
        if market:
            return f"{sync_type}: {market}"
    return str(payload.get("id") or "Data sync task")


def _active_task_payloads(kind: str, *, tenant_id: str | None = None) -> list[dict]:
    if job_records.database_backed_job_records_enabled():
        return [
            record
            for record in job_records.list_active_job_records(tenant_id=tenant_id)
            if record.get("kind") == kind
        ]
    if task_store.redis_task_backend_enabled():
        return task_store.get_task_store().list_tasks(kind)
    if kind == "analysis":
        return [task.to_dict() for task in analysis_tasks.list_tasks()]
    if kind == "screener":
        return [task.to_dict() for task in screener_tasks.list_screener_tasks()]
    return [task.to_dict() for task in data_sync_tasks.list_data_sync_tasks()]


def _queue_position(kind: str, task_id: str, payload: dict) -> int | None:
    if task_store.redis_task_backend_enabled():
        return task_store.get_task_store().queue_position(kind, task_id)
    value = payload.get("queue_position")
    return value if isinstance(value, int) else None


def _runtime_task_present(kind: str, task_id: str) -> bool:
    if kind not in task_store.TASK_KINDS:
        return False
    try:
        if task_store.redis_task_backend_enabled():
            return task_store.get_task_store().get_task(kind, task_id) is not None
        if kind == "analysis":
            analysis_tasks.get_task(task_id)
        elif kind == "screener":
            screener_tasks.get_screener_task(task_id)
        else:
            data_sync_tasks.get_data_sync_task(task_id)
        return True
    except HTTPException as exc:
        if exc.status_code == 404:
            return False
        raise


def _serialize_queue_item(
    *,
    kind: str,
    payload: dict,
    user_lookup: dict[str, dict],
    runtime_present: bool = True,
) -> dict:
    task_id = str(payload.get("id") or "")
    status = _normalize_queue_status(payload.get("status"))
    owner_user_id = payload.get("owner_user_id")
    owner = user_lookup.get(str(owner_user_id)) if owner_user_id else None
    if kind == "analysis":
        label = _analysis_label(payload)
        detail_path = f"/tasks/{task_id}"
    elif kind == "screener":
        label = _screener_label(payload)
        detail_path = f"/screener-tasks/{task_id}"
    else:
        label = _data_sync_label(payload)
        detail_path = "/admin/data-sources"
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
        "detail_path": detail_path,
        "runtime_present": runtime_present,
        "stale": not runtime_present,
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
def list_admin_task_queue(request: Request = None) -> dict:
    actor = _require_admin_permission(request, auth.PERMISSION_ADMIN_SETTINGS)
    try:
        user_lookup = _load_admin_user_lookup(
            actor.tenant_id if actor is not None else None
        )
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc

    items: list[dict] = []
    for kind in task_store.TASK_KINDS:
        for payload in _active_task_payloads(
            kind,
            tenant_id=actor.tenant_id if actor is not None else None,
        ):
            if actor is not None and payload.get("tenant_id") != actor.tenant_id:
                continue
            status = _normalize_queue_status(payload.get("status"))
            if status not in task_store.ACTIVE_STATUSES:
                continue
            runtime_present = True
            if job_records.database_backed_job_records_enabled():
                runtime_present = _runtime_task_present(kind, str(payload.get("id") or ""))
            items.append(
                _serialize_queue_item(
                    kind=kind,
                    payload=payload,
                    user_lookup=user_lookup,
                    runtime_present=runtime_present,
                )
            )
    items.sort(key=_queue_sort_key)
    totals = {
        "active": len(items),
        "queued": sum(
            1 for item in items if item["status"] in task_store.QUEUED_STATUSES
        ),
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


@router.delete("/api/admin/task-queue/{kind}/{task_id}")
def delete_admin_task_queue_item(
    kind: str,
    task_id: str,
    request: Request = None,
) -> dict:
    actor = _require_admin_permission(request, auth.PERMISSION_ADMIN_SETTINGS)
    if kind not in task_store.TASK_KINDS:
        raise HTTPException(status_code=404, detail="Task queue item not found")

    runtime_present = _runtime_task_present(kind, task_id)
    if runtime_present:
        raise HTTPException(
            status_code=409,
            detail=(
                "Task still exists in the runtime queue. Cancel live work before "
                "removing queue records."
            ),
        )

    if job_records.database_backed_job_records_enabled():
        tenant_id = actor.tenant_id if actor is not None else None
        deleted = job_records.delete_job_record(
            task_id,
            kind=kind,
            tenant_id=tenant_id,
        )
        if deleted:
            return {"deleted": True, "kind": kind, "task_id": task_id}

    raise HTTPException(status_code=404, detail="Task queue item not found")


@router.get("/api/admin/audit-events")
def list_admin_audit_events(
    request: Request = None,
    action: str | None = None,
    resource_type: str | None = None,
    actor_user_id: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    limit: int = 100,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db, request, auth.PERMISSION_ADMIN_AUDIT
            )
            if actor is None:
                return {"events": []}
            events = audit.list_audit_events(
                db,
                tenant_id=actor.tenant_id,
                action=action,
                resource_type=resource_type,
                actor_user_id=actor_user_id,
                created_from=_parse_datetime_filter(created_from),
                created_to=_parse_datetime_filter(created_to),
                limit=limit,
            )
            return {"events": [audit.serialize_audit_event(event) for event in events]}
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


@router.get("/api/admin/users")
def list_admin_users(request: Request = None) -> list[dict]:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db, request, auth.PERMISSION_ADMIN_USERS
            )
            users = auth.list_users(
                db,
                tenant_id=actor.tenant_id if actor is not None else None,
            )
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
def list_admin_analysis_limits(request: Request = None) -> dict:
    try:
        with auth.db_session() as db:
            _require_db_admin_permission(db, request, auth.PERMISSION_ADMIN_SETTINGS)
            return {"limits": analysis_limits.list_role_limits(db)}
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


@router.put("/api/admin/analysis-limits")
def update_admin_analysis_limits(
    payload: AdminAnalysisLimitsUpdatePayload,
    request: Request = None,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db,
                request,
                auth.PERMISSION_ADMIN_SETTINGS,
            )
            limits = analysis_limits.update_role_limits(
                db,
                [item.model_dump() for item in payload.limits],
            )
            if actor is not None:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.id,
                    action="admin.analysis_limits.updated",
                    resource_type="analysis_limits",
                    metadata={"roles": [row["role"] for row in limits]},
                    request=request,
                )
            result = {"limits": limits}
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
    logger.info(
        "admin analysis limits updated actor_user_id=%s roles=%s",
        actor.id if actor is not None else None,
        ",".join(row["role"] for row in result["limits"]),
    )
    return result


@router.get("/api/admin/data-sources")
def list_admin_data_sources(request: Request = None) -> dict:
    _require_admin_permission(request, auth.PERMISSION_ADMIN_SETTINGS)
    return vendor_usage.get_data_source_usage_summary()


@router.put("/api/admin/data-sources/{vendor}")
def update_admin_data_source(
    vendor: str,
    payload: AdminDataSourceUpdatePayload,
    request: Request = None,
) -> dict:
    actor = _require_admin_permission(request, auth.PERMISSION_ADMIN_SETTINGS)
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
    if actor is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=actor.tenant_id,
                actor_user_id=actor.id,
                action="admin.data_source.updated",
                resource_type="data_source",
                resource_id=source["vendor"],
                metadata={"enabled": source["enabled"]},
                request=request,
            )
    return {"source": source}


@router.put("/api/admin/data-source-routes/{module}/{market}/{category}")
def update_admin_data_source_route(
    module: str,
    market: str,
    category: str,
    payload: AdminDataSourceRouteUpdatePayload,
    request: Request = None,
) -> dict:
    actor = _require_admin_permission(request, auth.PERMISSION_ADMIN_SETTINGS)
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
    if actor is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=actor.tenant_id,
                actor_user_id=actor.id,
                action="admin.data_source_route.updated",
                resource_type="data_source_route",
                resource_id=f"{module}:{market}:{category}",
                metadata={"vendor_chain": route["vendor_chain"]},
                request=request,
            )
    return {"route": route}


@router.get("/api/admin/search-quota")
def list_admin_search_quota(request: Request = None) -> dict:
    try:
        with auth.db_session() as db:
            _require_db_admin_permission(db, request, auth.PERMISSION_ADMIN_SETTINGS)
            return search_quota.get_search_quota_summary(db)
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


@router.put("/api/admin/search-quota/global")
def update_admin_search_global(
    payload: SearchGlobalUpdatePayload,
    request: Request = None,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db,
                request,
                auth.PERMISSION_ADMIN_SETTINGS,
            )
            global_config = search_quota.update_global_config(db, payload.enabled)
            if actor is not None:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.id,
                    action="admin.search.global_updated",
                    resource_type="search_quota",
                    resource_id="global",
                    metadata={"enabled": global_config["enabled"]},
                    request=request,
                )
            return {"global": global_config}
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


@router.put("/api/admin/search-quota/providers/{provider}")
def update_admin_search_provider(
    provider: str,
    payload: SearchProviderUpdatePayload,
    request: Request = None,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db,
                request,
                auth.PERMISSION_ADMIN_SETTINGS,
            )
            provider_config = search_quota.update_provider_config(
                db,
                provider,
                payload.model_dump(exclude_unset=True),
            )
            if actor is not None:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.id,
                    action="admin.search.provider_updated",
                    resource_type="search_provider",
                    resource_id=provider_config["provider"],
                    metadata={
                        "enabled": provider_config["enabled"],
                        "monthly_free_quota": provider_config["monthly_free_quota"],
                        "monthly_hard_cap": provider_config["monthly_hard_cap"],
                    },
                    request=request,
                )
            return {"provider": provider_config}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


@router.post("/api/admin/search-quota/providers/{provider}/reactivate")
def reactivate_admin_search_provider(
    provider: str,
    request: Request = None,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db,
                request,
                auth.PERMISSION_ADMIN_SETTINGS,
            )
            provider_config = search_quota.reactivate_provider(db, provider)
            if actor is not None:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.id,
                    action="admin.search.provider_reactivated",
                    resource_type="search_provider",
                    resource_id=provider_config["provider"],
                    metadata={"enabled": provider_config["enabled"]},
                    request=request,
                )
            return {"provider": provider_config}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


@router.post("/api/admin/search-quota/providers/{provider}/usage/reset")
def reset_admin_search_provider_usage(
    provider: str,
    request: Request = None,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db,
                request,
                auth.PERMISSION_ADMIN_SETTINGS,
            )
            normalized_provider = search_quota._normalize_provider(provider)
            reset_count = search_quota.reset_provider_month_usage(
                db, normalized_provider
            )
            summary = search_quota.get_search_quota_summary(db)
            provider_config = next(
                item
                for item in summary["providers"]
                if item["provider"] == normalized_provider
            )
            if actor is not None:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.id,
                    action="admin.search.provider_usage_reset",
                    resource_type="search_provider_usage",
                    resource_id=normalized_provider,
                    metadata={
                        "reset_count": reset_count,
                        "usage_month": summary["month"],
                    },
                    request=request,
                )
            return {"provider": provider_config, "reset_count": reset_count}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


@router.get("/api/admin/llm-models")
def list_admin_llm_models(request: Request = None) -> dict:
    _require_admin_permission(request, auth.PERMISSION_ADMIN_SETTINGS)
    return llm_models.list_llm_model_summary()


@router.put("/api/admin/llm-models/providers/{provider}")
def update_admin_llm_provider(
    provider: str,
    payload: AdminLLMProviderUpdatePayload,
    request: Request = None,
) -> dict:
    actor = _require_admin_permission(request, auth.PERMISSION_ADMIN_SETTINGS)
    try:
        source = llm_models.update_provider_config(
            provider,
            enabled=payload.enabled,
            base_url=payload.base_url,
            daily_limit=payload.daily_limit,
            hourly_limit=payload.hourly_limit,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if actor is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=actor.tenant_id,
                actor_user_id=actor.id,
                action="admin.llm_provider.updated",
                resource_type="llm_provider",
                resource_id=source["provider"],
                metadata={
                    "enabled": source["enabled"],
                    "api_key_env": source["api_key_env"],
                },
                request=request,
            )
    return {"provider": source}


@router.put("/api/admin/llm-models/models/{provider}/{model_id:path}")
def update_admin_llm_model(
    provider: str,
    model_id: str,
    payload: AdminLLMModelUpdatePayload,
    request: Request = None,
) -> dict:
    actor = _require_admin_permission(request, auth.PERMISSION_ADMIN_SETTINGS)
    try:
        model = llm_models.update_model_config(
            provider,
            model_id,
            enabled=payload.enabled,
            cost_tier=payload.cost_tier,
            visible_to_roles=[role.value for role in payload.visible_to_roles],
            daily_limit=payload.daily_limit,
            weekly_limit=payload.weekly_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if actor is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=actor.tenant_id,
                actor_user_id=actor.id,
                action="admin.llm_model.updated",
                resource_type="llm_model",
                resource_id=model["id"],
                metadata={"enabled": model["enabled"], "cost_tier": model["cost_tier"]},
                request=request,
            )
    return {"model": model}


@router.put("/api/admin/llm-models/profiles/{profile_id}")
def update_admin_llm_profile(
    profile_id: str,
    payload: AdminLLMProfileUpdatePayload,
    request: Request = None,
) -> dict:
    actor = _require_admin_permission(request, auth.PERMISSION_ADMIN_SETTINGS)
    try:
        profile = llm_models.update_profile_config(
            profile_id,
            enabled=payload.enabled,
            default_for_roles=[role.value for role in payload.default_for_roles],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if actor is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=actor.tenant_id,
                actor_user_id=actor.id,
                action="admin.llm_profile.updated",
                resource_type="llm_model_profile",
                resource_id=profile["profile_id"],
                metadata={"enabled": profile["enabled"]},
                request=request,
            )
    return {"profile": profile}


@router.put("/api/admin/llm-models/profiles/{profile_id}/routes")
def update_admin_llm_profile_routes(
    profile_id: str,
    payload: AdminLLMProfileRoutesUpdatePayload,
    request: Request = None,
) -> dict:
    actor = _require_admin_permission(request, auth.PERMISSION_ADMIN_SETTINGS)
    try:
        routes = llm_models.update_profile_routes(
            profile_id,
            [item.model_dump() for item in payload.routes],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if actor is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=actor.tenant_id,
                actor_user_id=actor.id,
                action="admin.llm_profile_routes.updated",
                resource_type="llm_model_profile",
                resource_id=profile_id,
                metadata={"route_count": len(routes)},
                request=request,
            )
    return {"routes": routes}


@router.put("/api/admin/llm-models/module-settings/{module}")
def update_admin_llm_module_setting(
    module: str,
    payload: AdminLLMModuleSettingUpdatePayload,
    request: Request = None,
) -> dict:
    actor = _require_admin_permission(request, auth.PERMISSION_ADMIN_SETTINGS)
    try:
        setting = llm_models.update_module_setting(
            module,
            enabled=payload.enabled,
            model_profile=payload.model_profile,
            output_language=payload.output_language,
            custom_provider=payload.custom_provider,
            custom_model=payload.custom_model,
            openai_reasoning_effort=payload.openai_reasoning_effort,
            google_thinking_level=payload.google_thinking_level,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if actor is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=actor.tenant_id,
                actor_user_id=actor.id,
                action="admin.llm_module_setting.updated",
                resource_type="llm_module_setting",
                resource_id=setting["module"],
                metadata={
                    "enabled": setting["enabled"],
                    "model_profile": setting["model_profile"],
                },
                request=request,
            )
    return {"setting": setting}


@router.put("/api/admin/llm-models/ui-settings/{setting_key}")
def update_admin_llm_ui_setting(
    setting_key: str,
    payload: AdminLLMUiSettingUpdatePayload,
    request: Request = None,
) -> dict:
    actor = _require_admin_permission(request, auth.PERMISSION_ADMIN_SETTINGS)
    try:
        setting = llm_models.update_ui_setting(
            setting_key,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if actor is not None:
        with auth.db_session() as db:
            audit.record_audit_event_safely(
                db,
                tenant_id=actor.tenant_id,
                actor_user_id=actor.id,
                action="admin.llm_ui_setting.updated",
                resource_type="llm_ui_setting",
                resource_id=setting["setting_key"],
                metadata={"enabled": setting["enabled"]},
                request=request,
            )
    return {"setting": setting}


@router.get("/api/admin/users/{user_id}")
def get_admin_user(user_id: str, request: Request = None) -> dict:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db, request, auth.PERMISSION_ADMIN_USERS
            )
            target = auth.get_user_by_id(db, user_id)
            _ensure_same_tenant(actor, target)
            return auth.serialize_user(target)
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


@router.post("/api/admin/users")
def create_admin_user(payload: AdminUserCreatePayload, request: Request = None) -> dict:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db,
                request,
                auth.PERMISSION_ADMIN_USERS,
            )
            user = auth.create_user(
                db,
                email=payload.email,
                username=payload.username,
                display_name=payload.display_name,
                password=payload.password,
                role=payload.role,
                status=payload.status,
                must_change_password=payload.must_change_password,
                tenant_id=actor.tenant_id if actor is not None else None,
            )
            if actor is not None:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.id,
                    action="admin.user.created",
                    resource_type="user",
                    resource_id=user.id,
                    metadata={"role": user.role, "status": user.status},
                    request=request,
                )
            result = auth.serialize_user(user)
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
    logger.info(
        "admin user created actor_user_id=%s target_user_id=%s role=%s status=%s",
        actor.id if actor is not None else None,
        user.id,
        user.role,
        user.status,
    )
    return result


@router.put("/api/admin/users/{user_id}")
def update_admin_user(
    user_id: str,
    payload: AdminUserUpdatePayload,
    request: Request = None,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db,
                request,
                auth.PERMISSION_ADMIN_USERS,
            )
            _ensure_same_tenant(actor, auth.get_user_by_id(db, user_id))
            user = auth.update_user(
                db,
                user_id,
                username=payload.username,
                display_name=payload.display_name,
                role=payload.role,
                status=payload.status,
                must_change_password=payload.must_change_password,
            )
            _ensure_same_tenant(actor, user)
            if actor is not None:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.id,
                    action="admin.user.updated",
                    resource_type="user",
                    resource_id=user.id,
                    metadata={"role": user.role, "status": user.status},
                    request=request,
                )
            result = auth.serialize_user(user)
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
    logger.info(
        "admin user updated actor_user_id=%s target_user_id=%s role=%s status=%s",
        actor.id if actor is not None else None,
        user.id,
        user.role,
        user.status,
    )
    return result


@router.delete("/api/admin/users/{user_id}")
def delete_admin_user(user_id: str, request: Request = None) -> dict:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db,
                request,
                auth.PERMISSION_ADMIN_USERS,
            )
            user = auth.get_user_by_id(db, user_id)
            _ensure_same_tenant(actor, user)
            auth.delete_user(db, user_id)
            if actor is not None:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.id,
                    action="admin.user.deleted",
                    resource_type="user",
                    resource_id=user_id,
                    request=request,
                )
            result = {"deleted": True, "user_id": user_id}
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
    logger.info(
        "admin user deleted actor_user_id=%s target_user_id=%s",
        actor.id if actor is not None else None,
        user_id,
    )
    return result


@router.post(
    "/api/admin/users/{user_id}/reset-password",
)
def reset_admin_user_password(
    user_id: str,
    payload: AdminUserResetPasswordPayload,
    request: Request = None,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db,
                request,
                auth.PERMISSION_ADMIN_USERS,
            )
            _ensure_same_tenant(actor, auth.get_user_by_id(db, user_id))
            user = auth.reset_user_password(
                db,
                user_id,
                new_password=payload.new_password,
                must_change_password=payload.must_change_password,
            )
            _ensure_same_tenant(actor, user)
            if actor is not None:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.id,
                    action="admin.user.password_reset",
                    resource_type="user",
                    resource_id=user.id,
                    metadata={"must_change_password": user.must_change_password},
                    request=request,
                )
            result = auth.serialize_user(user)
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
    logger.info(
        "admin user password reset actor_user_id=%s target_user_id=%s",
        actor.id if actor is not None else None,
        user.id,
    )
    return result


@router.post("/api/admin/users/{user_id}/usage/reset")
def reset_admin_user_usage(user_id: str, request: Request = None) -> dict:
    try:
        with auth.db_session() as db:
            actor = _require_db_admin_permission(
                db,
                request,
                auth.PERMISSION_ADMIN_USERS,
            )
            user = auth.get_user_by_id(db, user_id)
            _ensure_same_tenant(actor, user)
            reset_count = analysis_limits.reset_user_weekly_usage(db, user_id)
            if actor is not None:
                audit.record_audit_event_safely(
                    db,
                    tenant_id=actor.tenant_id,
                    actor_user_id=actor.id,
                    action="admin.user.usage_reset",
                    resource_type="user",
                    resource_id=user_id,
                    metadata={"reset_count": reset_count},
                    request=request,
                )
            result = {
                "user_id": user_id,
                "reset_count": reset_count,
                "usage": analysis_limits.build_user_weekly_usage_summary(db, user),
            }
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
    logger.info(
        "admin user weekly usage reset actor_user_id=%s target_user_id=%s reset_count=%s",
        actor.id if actor is not None else None,
        user_id,
        reset_count,
    )
    return result
