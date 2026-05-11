from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, Integer, String, delete, inspect
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Mapped, Session, mapped_column

from web.backend import auth


SEARCH_PROVIDER_ORDER = ("brave", "tavily", "bocha")
SEARCH_PROVIDER_LABELS = {
    "brave": "Brave Search",
    "tavily": "Tavily",
    "bocha": "Bocha",
}
SEARCH_PROVIDER_KEY_ENVS = {
    "brave": "BRAVE_SEARCH_API_KEY",
    "tavily": "TAVILY_API_KEY",
    "bocha": "BOCHA_API_KEY",
}
SEARCH_QUOTA_TABLES = (
    "search_global_configs",
    "search_provider_configs",
    "search_provider_usage",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def current_usage_month(value: datetime | None = None) -> str:
    candidate = value or _utcnow()
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=timezone.utc)
    return candidate.astimezone(timezone.utc).strftime("%Y-%m")


def month_end_utc(value: datetime | None = None) -> datetime:
    candidate = value or _utcnow()
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=timezone.utc)
    candidate = candidate.astimezone(timezone.utc)
    year = candidate.year + (1 if candidate.month == 12 else 0)
    month = 1 if candidate.month == 12 else candidate.month + 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


class SearchGlobalConfig(auth.Base):
    __tablename__ = "search_global_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default="global")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disabled_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    disabled_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class SearchProviderConfig(auth.Base):
    __tablename__ = "search_provider_configs"
    __table_args__ = (Index("ix_search_provider_configs_provider", "provider"),)

    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    monthly_free_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    monthly_hard_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    disabled_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    disabled_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class SearchProviderUsage(auth.Base):
    __tablename__ = "search_provider_usage"
    __table_args__ = (
        Index("ix_search_provider_usage_provider_month", "provider", "usage_month"),
    )

    usage_month: Mapped[str] = mapped_column(String(7), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    total_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_called_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)


def ensure_search_quota_tables(settings: auth.AuthSettings | None = None) -> None:
    resolved_settings = settings or auth.get_auth_settings()
    if not resolved_settings.enabled:
        return
    inspector = inspect(auth.get_engine(resolved_settings))
    missing_tables = [
        table_name
        for table_name in SEARCH_QUOTA_TABLES
        if not inspector.has_table(table_name)
    ]
    if missing_tables:
        raise RuntimeError(
            "Auth is enabled but the following search quota tables are missing: "
            f"{', '.join(missing_tables)}. Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )


def initialize_search_quota_runtime() -> None:
    ensure_search_quota_tables()


def _normalize_provider(provider: str) -> str:
    candidate = str(provider or "").strip().lower()
    if candidate not in SEARCH_PROVIDER_ORDER:
        raise ValueError(f"Unknown search provider '{provider}'")
    return candidate


def _normalize_nonnegative_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a non-negative integer") from exc
    if normalized < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return normalized


def _ensure_global_config(db: Session) -> SearchGlobalConfig:
    row = db.get(SearchGlobalConfig, "global")
    if row is None:
        row = SearchGlobalConfig(id="global", enabled=False, updated_at=_utcnow())
        db.add(row)
        db.flush()
    return row


def _ensure_provider_config(db: Session, provider: str) -> SearchProviderConfig:
    normalized = _normalize_provider(provider)
    row = db.get(SearchProviderConfig, normalized)
    if row is None:
        row = SearchProviderConfig(
            provider=normalized,
            enabled=False,
            monthly_free_quota=0,
            monthly_hard_cap=0,
            updated_at=_utcnow(),
        )
        db.add(row)
        db.flush()
    return row


def _ensure_defaults(db: Session) -> None:
    _ensure_global_config(db)
    for provider in SEARCH_PROVIDER_ORDER:
        _ensure_provider_config(db, provider)


def _usage_row(
    db: Session, provider: str, usage_month: str
) -> SearchProviderUsage | None:
    return db.get(SearchProviderUsage, (usage_month, provider))


def _usage_summary(db: Session, provider: str, usage_month: str) -> dict[str, Any]:
    row = _usage_row(db, provider, usage_month)
    if row is None:
        return {
            "total_calls": 0,
            "success_count": 0,
            "failure_count": 0,
            "last_called_at": None,
            "last_error": None,
        }
    return {
        "total_calls": row.total_calls,
        "success_count": row.success_count,
        "failure_count": row.failure_count,
        "last_called_at": row.last_called_at,
        "last_error": row.last_error,
    }


def _global_payload(row: SearchGlobalConfig) -> dict[str, Any]:
    return {
        "enabled": row.enabled,
        "disabled_until": _serialize_datetime(row.disabled_until),
        "disabled_reason": row.disabled_reason,
        "updated_at": _serialize_datetime(row.updated_at),
    }


def _provider_payload(
    row: SearchProviderConfig,
    *,
    usage: dict[str, Any],
) -> dict[str, Any]:
    hard_cap = row.monthly_hard_cap
    used = int(usage["total_calls"])
    remaining = max(hard_cap - used, 0)
    return {
        "provider": row.provider,
        "label": SEARCH_PROVIDER_LABELS[row.provider],
        "enabled": row.enabled,
        "key_status": (
            "configured"
            if os.environ.get(SEARCH_PROVIDER_KEY_ENVS[row.provider], "").strip()
            else "missing"
        ),
        "monthly_free_quota": row.monthly_free_quota,
        "monthly_hard_cap": hard_cap,
        "used_this_month": used,
        "remaining_to_hard_cap": remaining,
        "hard_cap_reached": used >= hard_cap,
        "success_count": int(usage["success_count"]),
        "failure_count": int(usage["failure_count"]),
        "disabled_until": _serialize_datetime(row.disabled_until),
        "disabled_reason": row.disabled_reason,
        "last_error": usage["last_error"],
        "last_called_at": _serialize_datetime(usage["last_called_at"]),
        "updated_at": _serialize_datetime(row.updated_at),
    }


def get_search_quota_summary(db: Session) -> dict[str, Any]:
    _ensure_defaults(db)
    usage_month = current_usage_month()
    global_config = _ensure_global_config(db)
    providers = [
        _provider_payload(
            _ensure_provider_config(db, provider),
            usage=_usage_summary(db, provider, usage_month),
        )
        for provider in SEARCH_PROVIDER_ORDER
    ]
    return {
        "month": usage_month,
        "global": _global_payload(global_config),
        "providers": providers,
    }


def update_global_config(db: Session, enabled: bool) -> dict[str, Any]:
    row = _ensure_global_config(db)
    row.enabled = bool(enabled)
    if enabled:
        row.disabled_until = None
        row.disabled_reason = None
    row.updated_at = _utcnow()
    db.flush()
    return _global_payload(row)


def update_provider_config(
    db: Session, provider: str, payload: dict[str, Any]
) -> dict[str, Any]:
    row = _ensure_provider_config(db, provider)
    monthly_free_quota = (
        _normalize_nonnegative_int(
            payload["monthly_free_quota"], field_name="monthly_free_quota"
        )
        if "monthly_free_quota" in payload and payload["monthly_free_quota"] is not None
        else row.monthly_free_quota
    )
    monthly_hard_cap = (
        _normalize_nonnegative_int(
            payload["monthly_hard_cap"], field_name="monthly_hard_cap"
        )
        if "monthly_hard_cap" in payload and payload["monthly_hard_cap"] is not None
        else row.monthly_hard_cap
    )
    if monthly_hard_cap > monthly_free_quota:
        raise ValueError(
            "monthly_hard_cap must be less than or equal to monthly_free_quota"
        )
    if "enabled" in payload and payload["enabled"] is not None:
        row.enabled = bool(payload["enabled"])
        if row.enabled:
            row.disabled_until = None
            row.disabled_reason = None
    row.monthly_free_quota = monthly_free_quota
    row.monthly_hard_cap = monthly_hard_cap
    row.updated_at = _utcnow()
    db.flush()
    return _provider_payload(
        row,
        usage=_usage_summary(db, row.provider, current_usage_month()),
    )


def record_search_provider_call(
    db: Session,
    provider: str,
    *,
    success: bool,
    error: str | None = None,
) -> None:
    normalized = _normalize_provider(provider)
    usage_month = current_usage_month()
    now = _utcnow()
    dialect_name = db.get_bind().dialect.name
    truncated_error = str(error)[:512] if error else None
    if dialect_name in {"postgresql", "sqlite"}:
        table = SearchProviderUsage.__table__
        insert_factory = (
            postgresql.insert if dialect_name == "postgresql" else sqlite.insert
        )
        statement = insert_factory(table).values(
            usage_month=usage_month,
            provider=normalized,
            total_calls=1,
            success_count=1 if success else 0,
            failure_count=0 if success else 1,
            last_called_at=now,
            last_error=truncated_error,
        )
        db.execute(
            statement.on_conflict_do_update(
                index_elements=["usage_month", "provider"],
                set_={
                    "total_calls": table.c.total_calls + 1,
                    "success_count": table.c.success_count + (1 if success else 0),
                    "failure_count": table.c.failure_count + (0 if success else 1),
                    "last_called_at": now,
                    "last_error": truncated_error,
                },
            )
        )
        db.flush()
        return

    row = _usage_row(db, normalized, usage_month)
    if row is None:
        row = SearchProviderUsage(
            usage_month=usage_month,
            provider=normalized,
            total_calls=0,
            success_count=0,
            failure_count=0,
        )
        db.add(row)
    row.total_calls += 1
    if success:
        row.success_count += 1
    else:
        row.failure_count += 1
    row.last_called_at = now
    row.last_error = truncated_error
    db.flush()


def reset_provider_month_usage(
    db: Session,
    provider: str,
    usage_month: str | None = None,
) -> int:
    normalized = _normalize_provider(provider)
    month = usage_month or current_usage_month()
    row = _usage_row(db, normalized, month)
    if row is None:
        return 0
    total = row.total_calls
    db.execute(
        delete(SearchProviderUsage).where(
            SearchProviderUsage.provider == normalized,
            SearchProviderUsage.usage_month == month,
        )
    )
    db.flush()
    return total


def reactivate_provider(db: Session, provider: str) -> dict[str, Any]:
    row = _ensure_provider_config(db, provider)
    usage = _usage_summary(db, row.provider, current_usage_month())
    if int(usage["total_calls"]) >= row.monthly_hard_cap:
        raise ValueError("monthly_hard_cap has been reached for this provider")
    row.enabled = True
    row.disabled_until = None
    row.disabled_reason = None
    row.updated_at = _utcnow()
    db.flush()
    return _provider_payload(row, usage=usage)


def disable_provider_until_month_end(
    db: Session, provider: str, reason: str
) -> dict[str, Any]:
    row = _ensure_provider_config(db, provider)
    row.enabled = False
    row.disabled_until = month_end_utc()
    row.disabled_reason = str(reason or "disabled")
    row.updated_at = _utcnow()
    db.flush()
    return _provider_payload(
        row,
        usage=_usage_summary(db, row.provider, current_usage_month()),
    )


def disable_global_until_month_end(db: Session, reason: str) -> dict[str, Any]:
    row = _ensure_global_config(db)
    row.enabled = False
    row.disabled_until = month_end_utc()
    row.disabled_reason = str(reason or "disabled")
    row.updated_at = _utcnow()
    db.flush()
    return _global_payload(row)
