from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Index, JSON, String, Text, inspect, select
from sqlalchemy.orm import Mapped, mapped_column

from web.backend import app_config, auth
from web.backend.runtime import task_store


JOB_RECORD_TABLES = ("job_records",)
TERMINAL_STATUSES = {"completed", "failed", "canceled"}
ACTIVE_STATUSES = task_store.ACTIVE_STATUSES
logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    candidate = str(value)
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return normalized.isoformat()


class JobRecord(auth.Base):
    __tablename__ = "job_records"
    __table_args__ = (
        Index("ix_job_records_kind_status", "kind", "status"),
        Index("ix_job_records_tenant_status", "tenant_id", "status"),
        Index("ix_job_records_owner_status", "owner_user_id", "status"),
        Index("ix_job_records_updated_at", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


def database_backed_job_records_enabled(settings: auth.AuthSettings | None = None) -> bool:
    resolved_settings = settings or auth.get_auth_settings()
    return resolved_settings.enabled and bool(resolved_settings.database_url)


def ensure_job_record_tables(settings: auth.AuthSettings | None = None) -> None:
    resolved_settings = settings or auth.get_auth_settings()
    if not database_backed_job_records_enabled(resolved_settings):
        return
    try:
        inspector = inspect(auth.get_engine(resolved_settings))
    except Exception:
        if _raise_database_errors():
            raise
        logger.warning("Skipping job_records table check because the database is unavailable.")
        return
    missing_tables = [
        table_name for table_name in JOB_RECORD_TABLES if not inspector.has_table(table_name)
    ]
    if missing_tables:
        joined = ", ".join(missing_tables)
        message = (
            "Auth is enabled but the following job record tables are missing: "
            f"{joined}. Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )
        if _raise_database_errors():
            raise RuntimeError(message)
        logger.warning(message)


def initialize_job_record_runtime() -> None:
    validate_task_runtime_settings()
    ensure_job_record_tables()


def validate_task_runtime_settings(settings: auth.AuthSettings | None = None) -> None:
    if os.environ.get("APP_ENV", "").strip().lower() != "production":
        return
    resolved_settings = settings or auth.get_auth_settings()
    missing: list[str] = []
    if not resolved_settings.database_url:
        missing.append("DATABASE_URL")
    if os.environ.get("TASK_BACKEND", "local").strip().lower() != "redis":
        missing.append("TASK_BACKEND=redis")
    if missing:
        raise RuntimeError(
            "Production task state requires durable storage. Configure "
            + " and ".join(missing)
            + "."
        )


def _raise_database_errors() -> bool:
    return os.environ.get("APP_ENV", "").strip().lower() == "production"


def _serialize_record(record: JobRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "kind": record.kind,
        "tenant_id": record.tenant_id,
        "owner_user_id": record.owner_user_id,
        "status": record.status,
        "request_payload": record.request_payload or {},
        "result_summary": record.result_summary,
        "error": record.error,
        "created_at": _serialize_datetime(record.created_at),
        "queued_at": _serialize_datetime(record.queued_at),
        "started_at": _serialize_datetime(record.started_at),
        "finished_at": _serialize_datetime(record.finished_at),
        "heartbeat_at": _serialize_datetime(record.heartbeat_at),
        "worker_id": record.worker_id,
        "updated_at": _serialize_datetime(record.updated_at),
    }


def upsert_job_record(
    *,
    kind: str,
    task_id: str,
    status: str,
    request_payload: dict[str, Any] | None = None,
    result_summary: dict[str, Any] | None = None,
    error: str | None = None,
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
    created_at: str | datetime | None = None,
    queued_at: str | datetime | None = None,
    started_at: str | datetime | None = None,
    finished_at: str | datetime | None = None,
    heartbeat_at: str | datetime | None = None,
    worker_id: str | None = None,
) -> dict[str, Any] | None:
    if not database_backed_job_records_enabled():
        return None
    try:
        with auth.db_session() as db:
            record = db.get(JobRecord, task_id)
            if record is None:
                record = JobRecord(
                    id=task_id,
                    kind=kind,
                    status=status,
                    created_at=_parse_datetime(created_at) or _utcnow(),
                )
                db.add(record)
            record.kind = kind
            record.status = status
            if request_payload is not None:
                record.request_payload = dict(request_payload)
            if result_summary is not None:
                record.result_summary = dict(result_summary)
            record.error = error
            record.owner_user_id = owner_user_id
            record.tenant_id = tenant_id
            for field_name, raw_value in (
                ("queued_at", queued_at),
                ("started_at", started_at),
                ("finished_at", finished_at),
                ("heartbeat_at", heartbeat_at),
            ):
                if raw_value is not None:
                    setattr(record, field_name, _parse_datetime(raw_value))
            if worker_id is not None:
                record.worker_id = worker_id
            record.updated_at = _utcnow()
            db.flush()
            return _serialize_record(record)
    except Exception:
        if _raise_database_errors():
            raise
        logger.warning("Skipping job_records upsert because the database is unavailable.")
        return None


def get_job_record(task_id: str) -> dict[str, Any] | None:
    if not database_backed_job_records_enabled():
        return None
    try:
        with auth.db_session() as db:
            record = db.get(JobRecord, task_id)
            return _serialize_record(record) if record is not None else None
    except Exception:
        if _raise_database_errors():
            raise
        logger.warning("Skipping job_records lookup because the database is unavailable.")
        return None


def list_active_job_records(*, tenant_id: str | None = None) -> list[dict[str, Any]]:
    if not database_backed_job_records_enabled():
        return []
    try:
        with auth.db_session() as db:
            query = select(JobRecord).where(JobRecord.status.in_(ACTIVE_STATUSES))
            if tenant_id is not None:
                query = query.where(JobRecord.tenant_id == tenant_id)
            records = db.scalars(query.order_by(JobRecord.updated_at.desc())).all()
            return [_serialize_record(record) for record in records]
    except Exception:
        if _raise_database_errors():
            raise
        logger.warning("Skipping job_records list because the database is unavailable.")
        return []


def recover_stale_running_job_records() -> int:
    if not database_backed_job_records_enabled():
        return 0
    recovered = 0
    try:
        with auth.db_session() as db:
            records = db.scalars(select(JobRecord).where(JobRecord.status == "running")).all()
            for record in records:
                record.status = "failed"
                record.error = app_config.RECOVERED_TASK_ERROR
                record.finished_at = record.finished_at or _utcnow()
                record.updated_at = _utcnow()
                recovered += 1
    except Exception:
        if _raise_database_errors():
            raise
        logger.warning("Skipping job_records recovery because the database is unavailable.")
    return recovered
