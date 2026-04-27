from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, inspect, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from web.backend import auth


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScreenerRun(auth.Base):
    __tablename__ = "screener_runs"
    __table_args__ = (
        Index("ix_screener_runs_tenant_generated_at", "tenant_id", "generated_at"),
        Index("ix_screener_runs_owner_generated_at", "owner_user_id", "generated_at"),
        Index("ix_screener_runs_generated_at", "generated_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=True,
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    as_of_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    markets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    artifact_manifest: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


def ensure_screener_runs_table(settings: auth.AuthSettings | None = None) -> None:
    resolved_settings = settings or auth.get_auth_settings()
    if not resolved_settings.enabled:
        return

    inspector = inspect(auth.get_engine(resolved_settings))
    if not inspector.has_table("screener_runs"):
        raise RuntimeError(
            "Auth is enabled but the screener_runs table is missing. "
            "Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )


def initialize_screener_runtime() -> None:
    ensure_screener_runs_table()


def _normalize_text(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise auth.AuthValidationError(f"{field_name} is required")
    return value.strip()


def _normalize_markets(markets: list[str] | tuple[str, ...] | None) -> list[str]:
    if not markets:
        return []
    normalized: list[str] = []
    for market in markets:
        candidate = str(market).strip().lower()
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _normalize_manifest(artifact_manifest: dict[str, Any] | None) -> dict[str, str]:
    if not artifact_manifest:
        return {}

    normalized: dict[str, str] = {}
    for key, value in artifact_manifest.items():
        normalized_key = str(key).strip()
        normalized_value = str(value).strip() if value is not None else ""
        if normalized_key and normalized_value:
            normalized[normalized_key] = normalized_value
    return normalized


def upsert_screener_run(
    db: Session,
    *,
    run_id: str,
    owner_user_id: str,
    tenant_id: str | None = None,
    as_of_date: str | None,
    markets: list[str] | tuple[str, ...] | None,
    candidate_count: int,
    generated_at: str,
    storage_path: str,
    artifact_manifest: dict[str, Any] | None,
) -> ScreenerRun:
    normalized_run_id = _normalize_text(run_id, "run_id")
    normalized_owner_user_id = _normalize_text(owner_user_id, "owner_user_id")
    normalized_tenant_id = tenant_id.strip() if isinstance(tenant_id, str) and tenant_id.strip() else None
    if normalized_tenant_id is None:
        owner = db.get(auth.User, normalized_owner_user_id)
        normalized_tenant_id = owner.tenant_id if owner is not None else auth.DEFAULT_TENANT_ID
    normalized_storage_path = _normalize_text(storage_path, "storage_path")
    normalized_generated_at = _normalize_text(generated_at, "generated_at")

    record = db.get(ScreenerRun, normalized_run_id)
    if record is None:
        record = ScreenerRun(
            id=normalized_run_id,
            tenant_id=normalized_tenant_id,
            owner_user_id=normalized_owner_user_id,
        )
        db.add(record)

    record.tenant_id = normalized_tenant_id
    record.owner_user_id = normalized_owner_user_id
    record.as_of_date = as_of_date.strip() if isinstance(as_of_date, str) and as_of_date.strip() else None
    record.markets = _normalize_markets(markets)
    record.candidate_count = max(int(candidate_count), 0)
    record.generated_at = normalized_generated_at
    record.storage_path = normalized_storage_path
    record.artifact_manifest = _normalize_manifest(artifact_manifest)
    record.updated_at = _utcnow()
    db.flush()
    return record


def list_screener_run_records(
    db: Session,
    *,
    tenant_id: str | None = None,
    owner_user_id: str | None = None,
) -> list[ScreenerRun]:
    statement = select(ScreenerRun)
    if tenant_id is not None:
        statement = statement.where(ScreenerRun.tenant_id == tenant_id)
    if owner_user_id is not None:
        statement = statement.where(ScreenerRun.owner_user_id == owner_user_id)
    statement = statement.order_by(ScreenerRun.generated_at.desc(), ScreenerRun.id.desc())
    return list(db.scalars(statement))


def get_screener_run_record(
    db: Session,
    run_id: str,
    *,
    tenant_id: str | None = None,
    owner_user_id: str | None = None,
) -> ScreenerRun:
    statement = select(ScreenerRun).where(ScreenerRun.id == run_id)
    if tenant_id is not None:
        statement = statement.where(ScreenerRun.tenant_id == tenant_id)
    if owner_user_id is not None:
        statement = statement.where(ScreenerRun.owner_user_id == owner_user_id)
    record = db.scalar(statement)
    if record is None:
        raise auth.AuthNotFoundError(f"Screener run '{run_id}' not found")
    return record


def serialize_screener_run_summary(record: ScreenerRun) -> dict[str, Any]:
    return {
        "id": record.id,
        "as_of_date": record.as_of_date,
        "markets": list(record.markets or []),
        "candidate_count": record.candidate_count,
        "generated_at": record.generated_at,
    }


def serialize_screener_run_detail(record: ScreenerRun) -> dict[str, Any]:
    payload = serialize_screener_run_summary(record)
    payload.update(
        {
            "owner_user_id": record.owner_user_id,
            "tenant_id": record.tenant_id,
            "storage_path": record.storage_path,
            "artifact_paths": dict(record.artifact_manifest or {}),
        }
    )
    return payload
