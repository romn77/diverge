from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, inspect, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from web.backend import auth

logger = logging.getLogger(__name__)

SENSITIVE_METADATA_TOKENS = ("password", "secret", "token", "api_key", "apikey", "key")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditEvent(auth.Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_audit_events_tenant_action_created_at", "tenant_id", "action", "created_at"),
        Index("ix_audit_events_tenant_actor_created_at", "tenant_id", "actor_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


def ensure_audit_tables(settings: auth.AuthSettings | None = None) -> None:
    resolved_settings = settings or auth.get_auth_settings()
    if not resolved_settings.enabled:
        return

    inspector = inspect(auth.get_engine(resolved_settings))
    if not inspector.has_table("audit_events"):
        raise RuntimeError(
            "Auth is enabled but the audit_events table is missing. "
            "Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )


def _sanitize_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, nested_value in value.items():
            normalized_key = str(key)
            if any(token in normalized_key.lower() for token in SENSITIVE_METADATA_TOKENS):
                continue
            sanitized[normalized_key] = _sanitize_metadata(nested_value)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_metadata(item) for item in value[:20]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _request_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    return auth.client_ip_for_request(request)


def record_audit_event(
    db: Session,
    *,
    tenant_id: str | None,
    actor_user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditEvent:
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=str(action).strip(),
        resource_type=str(resource_type).strip(),
        resource_id=str(resource_id).strip() if resource_id is not None else None,
        metadata_json=_sanitize_metadata(metadata or {}),
        ip_address=_request_ip(request),
        user_agent=request.headers.get("user-agent") if request is not None else None,
    )
    db.add(event)
    db.flush()
    return event


def record_audit_event_safely(
    db: Session,
    *,
    tenant_id: str | None,
    actor_user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    try:
        record_audit_event(
            db,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
            request=request,
        )
    except Exception:
        logger.exception("failed to record audit event action=%s resource_type=%s", action, resource_type)


def list_audit_events(
    db: Session,
    *,
    tenant_id: str,
    action: str | None = None,
    resource_type: str | None = None,
    actor_user_id: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 100,
) -> list[AuditEvent]:
    statement = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
    if action:
        statement = statement.where(AuditEvent.action == action)
    if resource_type:
        statement = statement.where(AuditEvent.resource_type == resource_type)
    if actor_user_id:
        statement = statement.where(AuditEvent.actor_user_id == actor_user_id)
    if created_from is not None:
        statement = statement.where(AuditEvent.created_at >= created_from)
    if created_to is not None:
        statement = statement.where(AuditEvent.created_at <= created_to)
    statement = statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(max(min(limit, 500), 1))
    return list(db.scalars(statement))


def serialize_audit_event(event: AuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "tenant_id": event.tenant_id,
        "actor_user_id": event.actor_user_id,
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "metadata": dict(event.metadata_json or {}),
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "created_at": event.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
