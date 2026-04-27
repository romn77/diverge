from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    delete,
    func,
    inspect,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from web.backend import auth


MODULE_ORDER = ("analysis", "screener", "assets", "journal")
ROLE_ORDER = (
    auth.UserRole.ADMIN.value,
    auth.UserRole.OPERATOR.value,
    auth.UserRole.VIEWER.value,
)
DEFAULT_ROLE_WEEKLY_LIMITS: dict[str, int | None] = {
    auth.UserRole.ADMIN.value: None,
    auth.UserRole.OPERATOR.value: 20,
    auth.UserRole.VIEWER.value: 4,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _week_key(value: datetime | None = None) -> str:
    candidate = value or datetime.now().astimezone()
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=timezone.utc)
    local_date = candidate.astimezone().date()
    week_start = local_date - timedelta(days=local_date.weekday())
    return week_start.isoformat()


class WeeklyUsageLimitExceeded(Exception):
    def __init__(
        self,
        *,
        role: str,
        module: str,
        weekly_limit: int,
        used_count: int,
        usage_week: str,
    ) -> None:
        self.role = role
        self.module = module
        self.weekly_limit = weekly_limit
        self.used_count = used_count
        self.usage_week = usage_week
        super().__init__(
            f"Weekly {module} limit reached for role '{role}' "
            f"({used_count}/{weekly_limit} used for week {usage_week})."
        )


AnalysisDailyLimitExceeded = WeeklyUsageLimitExceeded


class AnalysisRoleLimit(auth.Base):
    __tablename__ = "analysis_role_limits"

    role: Mapped[str] = mapped_column(String(32), primary_key=True)
    weekly_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class AnalysisTaskUsage(auth.Base):
    __tablename__ = "analysis_task_usage"
    __table_args__ = (
        Index(
            "ix_analysis_task_usage_tenant_user_module_week",
            "tenant_id",
            "user_id",
            "module",
            "usage_week",
        ),
        Index(
            "ix_analysis_task_usage_role_module_week",
            "role",
            "module",
            "usage_week",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid.uuid4().hex,
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    module: Mapped[str] = mapped_column(String(32), nullable=False, default="analysis")
    usage_week: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )


def ensure_analysis_limit_tables(settings: auth.AuthSettings | None = None) -> None:
    resolved_settings = settings or auth.get_auth_settings()
    if not resolved_settings.enabled:
        return

    inspector = inspect(auth.get_engine(resolved_settings))
    required_tables = ("analysis_role_limits", "analysis_task_usage")
    missing_tables = [
        table_name for table_name in required_tables if not inspector.has_table(table_name)
    ]
    if missing_tables:
        joined = ", ".join(missing_tables)
        raise RuntimeError(
            "Auth is enabled but the following analysis limit tables are missing: "
            f"{joined}. Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )


def initialize_analysis_limits_runtime() -> None:
    ensure_analysis_limit_tables()


def serialize_role_limit(role: str, weekly_limit: int | None) -> dict[str, Any]:
    return {
        "role": role,
        "weekly_limit": weekly_limit,
    }


def _normalize_role(value: auth.UserRole | str) -> str:
    if isinstance(value, auth.UserRole):
        return value.value
    candidate = str(value).strip().lower()
    try:
        return auth.UserRole(candidate).value
    except ValueError as exc:
        raise auth.AuthValidationError(
            "role must be one of admin, operator, or viewer"
        ) from exc


def _normalize_module(value: str) -> str:
    candidate = str(value).strip().lower()
    if candidate not in MODULE_ORDER:
        raise auth.AuthValidationError(
            f"module must be one of {', '.join(MODULE_ORDER)}"
        )
    return candidate


def _normalize_weekly_limit(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise auth.AuthValidationError(
            "weekly_limit must be a non-negative integer or null"
        )
    normalized = int(value)
    if normalized < 0:
        raise auth.AuthValidationError(
            "weekly_limit must be a non-negative integer or null"
        )
    return normalized


def list_role_limits(db: Session) -> list[dict[str, Any]]:
    rows = {
        row.role: row.weekly_limit
        for row in db.scalars(select(AnalysisRoleLimit))
    }
    return [
        serialize_role_limit(role, rows.get(role, DEFAULT_ROLE_WEEKLY_LIMITS[role]))
        for role in ROLE_ORDER
    ]


def update_role_limits(
    db: Session,
    limits: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen_roles: set[str] = set()
    now = _utcnow()
    for entry in limits:
        role = _normalize_role(entry.get("role"))
        if role in seen_roles:
            raise auth.AuthValidationError(f"Duplicate analysis limit for role '{role}'")
        seen_roles.add(role)

        weekly_limit = _normalize_weekly_limit(
            entry.get("weekly_limit", entry.get("daily_limit"))
        )
        row = db.get(AnalysisRoleLimit, role)
        if row is None:
            db.add(
                AnalysisRoleLimit(
                    role=role,
                    weekly_limit=weekly_limit,
                    updated_at=now,
                )
            )
        else:
            row.weekly_limit = weekly_limit
            row.updated_at = now

    db.flush()
    return list_role_limits(db)


def get_role_weekly_limit(db: Session, role: auth.UserRole | str) -> int | None:
    normalized_role = _normalize_role(role)
    row = db.get(AnalysisRoleLimit, normalized_role)
    if row is not None:
        return row.weekly_limit
    return DEFAULT_ROLE_WEEKLY_LIMITS[normalized_role]


def count_user_module_usage(
    db: Session,
    *,
    user_id: str,
    tenant_id: str | None = None,
    module: str,
    usage_week: str | None = None,
) -> int:
    normalized_module = _normalize_module(module)
    resolved_week = usage_week or _week_key()
    if tenant_id is None:
        user = db.get(auth.User, user_id)
        tenant_id = user.tenant_id if user is not None else None
    return int(
        db.scalar(
            select(func.count(AnalysisTaskUsage.id)).where(
                AnalysisTaskUsage.tenant_id == tenant_id,
                AnalysisTaskUsage.user_id == user_id,
                AnalysisTaskUsage.module == normalized_module,
                AnalysisTaskUsage.usage_week == resolved_week,
            )
        )
        or 0
    )


def record_module_usage(
    db: Session,
    user: auth.User,
    *,
    module: str,
    usage_week: str | None = None,
) -> dict[str, Any]:
    normalized_module = _normalize_module(module)
    resolved_week = usage_week or _week_key()
    role = _normalize_role(user.role)
    weekly_limit = get_role_weekly_limit(db, role)
    used_count = count_user_module_usage(
        db,
        user_id=user.id,
        tenant_id=user.tenant_id,
        module=normalized_module,
        usage_week=resolved_week,
    )

    if weekly_limit is not None and used_count >= weekly_limit:
        raise WeeklyUsageLimitExceeded(
            role=role,
            module=normalized_module,
            weekly_limit=weekly_limit,
            used_count=used_count,
            usage_week=resolved_week,
        )

    db.add(
        AnalysisTaskUsage(
            tenant_id=user.tenant_id,
            user_id=user.id,
            role=role,
            module=normalized_module,
            usage_week=resolved_week,
        )
    )
    db.flush()
    return {
        "role": role,
        "module": normalized_module,
        "weekly_limit": weekly_limit,
        "used_count": used_count + 1,
        "usage_week": resolved_week,
    }


def record_analysis_task_creation(
    db: Session,
    user: auth.User,
    *,
    usage_week: str | None = None,
) -> dict[str, Any]:
    return record_module_usage(db, user, module="analysis", usage_week=usage_week)


def count_user_analysis_usage(
    db: Session,
    *,
    user_id: str,
    usage_week: str | None = None,
) -> int:
    return count_user_module_usage(
        db,
        user_id=user_id,
        module="analysis",
        usage_week=usage_week,
    )


def build_user_weekly_usage_summary(
    db: Session,
    user: auth.User,
    *,
    usage_week: str | None = None,
) -> dict[str, Any]:
    resolved_week = usage_week or _week_key()
    weekly_limit = get_role_weekly_limit(db, user.role)
    raw_counts = {
        module: count
        for module, count in db.execute(
            select(AnalysisTaskUsage.module, func.count(AnalysisTaskUsage.id))
            .where(
                AnalysisTaskUsage.tenant_id == user.tenant_id,
                AnalysisTaskUsage.user_id == user.id,
                AnalysisTaskUsage.usage_week == resolved_week,
            )
            .group_by(AnalysisTaskUsage.module)
        )
    }
    modules = {}
    for module in MODULE_ORDER:
        used_count = int(raw_counts.get(module, 0) or 0)
        modules[module] = {
            "used_count": used_count,
            "weekly_limit": weekly_limit,
            "remaining_count": (
                None
                if weekly_limit is None
                else max(int(weekly_limit) - used_count, 0)
            ),
        }
    return {
        "usage_week": resolved_week,
        "weekly_limit": weekly_limit,
        "modules": modules,
    }


def reset_user_weekly_usage(
    db: Session,
    user_id: str,
    *,
    module: str | None = None,
    usage_week: str | None = None,
) -> int:
    resolved_week = usage_week or _week_key()
    user = db.get(auth.User, user_id)
    tenant_id = user.tenant_id if user is not None else None
    statement = delete(AnalysisTaskUsage).where(
        AnalysisTaskUsage.tenant_id == tenant_id,
        AnalysisTaskUsage.user_id == user_id,
        AnalysisTaskUsage.usage_week == resolved_week,
    )
    if module is not None:
        statement = statement.where(AnalysisTaskUsage.module == _normalize_module(module))
    result = db.execute(statement)
    db.flush()
    return int(result.rowcount or 0)
