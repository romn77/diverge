from __future__ import annotations

from typing import Any, Callable

from web.backend import audit, auth

AuditMetadataBuilder = Callable[..., dict[str, Any]]

RESULT_METADATA_KEYS = (
    "symbols_total",
    "symbols_success",
    "symbols_failed",
    "rows_written",
    "symbols_missing_as_of_bar",
    "symbols_pruned_from_screener",
    "quality_artifact_path",
    "quality_reason_counts",
)


def data_sync_audit_metadata(
    task: Any,
    *,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    payload = task.request_payload
    metadata: dict[str, Any] = {
        "sync_type": task.sync_type,
        "markets": payload.get("markets"),
        "market": payload.get("market"),
        "as_of_date": payload.get("as_of_date"),
        "cn_data_source": payload.get("cn_data_source"),
        "us_data_source": payload.get("us_data_source"),
    }
    if result:
        for key in RESULT_METADATA_KEYS:
            if key in result:
                metadata[key] = result.get(key)
    if error:
        metadata["error"] = error
    return {key: value for key, value in metadata.items() if value is not None}


def record_data_sync_audit_event(
    task: Any,
    *,
    action: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    auth_module: Any = auth,
    audit_module: Any = audit,
    metadata_builder: AuditMetadataBuilder = data_sync_audit_metadata,
) -> None:
    if (
        task.owner_user_id is None
        or task.tenant_id is None
        or not auth_module.auth_enabled()
    ):
        return
    try:
        with auth_module.db_session() as db:
            audit_module.record_audit_event_safely(
                db,
                tenant_id=task.tenant_id,
                actor_user_id=task.owner_user_id,
                action=action,
                resource_type="data_sync_task",
                resource_id=task.id,
                metadata=metadata_builder(task, result=result, error=error),
            )
    except Exception:
        return
