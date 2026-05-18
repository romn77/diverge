from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, ForeignKey, Index, String, inspect, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from diverge.trade_plans import TRADE_PLAN_FILENAME
from web.backend import auth


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_ticker(value: str) -> str:
    return str(value).strip().upper()


def _storage_path_for_plan(plan: dict, reports_dir: Path) -> str:
    reports_root = Path(reports_dir).resolve()
    plan_path = (
        reports_root
        / ".trade_feedback"
        / ".trade_plans"
        / _normalize_ticker(plan["ticker"])
        / plan["plan_id"]
        / TRADE_PLAN_FILENAME
    )
    return plan_path.relative_to(reports_root).as_posix()


class TradePlanEntry(auth.Base):
    __tablename__ = "trade_plan_entries"
    __table_args__ = (
        Index("ix_trade_plan_entries_tenant_updated_at", "tenant_id", "updated_at"),
        Index("ix_trade_plan_entries_owner_updated_at", "owner_user_id", "updated_at"),
        Index(
            "ix_trade_plan_entries_tenant_owner_status_expires",
            "tenant_id",
            "owner_user_id",
            "status",
            "expires_at",
        ),
        Index(
            "ix_trade_plan_entries_tenant_owner_ticker_status",
            "tenant_id",
            "owner_user_id",
            "ticker",
            "status",
        ),
    )

    plan_id: Mapped[str] = mapped_column(String(32), primary_key=True)
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
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    linked_trade_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


def ensure_trade_plan_entries_table(settings: auth.AuthSettings | None = None) -> None:
    resolved_settings = settings or auth.get_auth_settings()
    if not resolved_settings.enabled:
        return

    inspector = inspect(auth.get_engine(resolved_settings))
    if not inspector.has_table("trade_plan_entries"):
        raise RuntimeError(
            "Auth is enabled but the trade_plan_entries table is missing. "
            "Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )


def initialize_trade_plan_entries_runtime() -> None:
    ensure_trade_plan_entries_table()


def _parse_datetime(value: str | None) -> datetime:
    candidate = str(value or "").strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def upsert_trade_plan_entry(
    db: Session,
    plan: dict,
    *,
    owner_user_id: str,
    tenant_id: str | None = None,
    reports_dir: Path,
) -> TradePlanEntry:
    now = _utcnow()
    normalized_tenant_id = (
        tenant_id.strip() if isinstance(tenant_id, str) and tenant_id.strip() else None
    )
    if normalized_tenant_id is None:
        owner = db.get(auth.User, owner_user_id)
        normalized_tenant_id = (
            owner.tenant_id if owner is not None else auth.DEFAULT_TENANT_ID
        )

    entry = db.get(TradePlanEntry, plan["plan_id"])
    if entry is None:
        entry = TradePlanEntry(
            plan_id=plan["plan_id"],
            tenant_id=normalized_tenant_id,
            owner_user_id=owner_user_id,
            ticker=_normalize_ticker(plan["ticker"]),
            side=str(plan["side"]),
            status=str(plan["status"]),
            expires_at=_parse_datetime(plan["expires_at"]),
            linked_trade_id=str(plan.get("linked_trade_id") or "") or None,
            storage_path=_storage_path_for_plan(plan, reports_dir),
            created_at=now,
            updated_at=now,
        )
        db.add(entry)
    else:
        entry.tenant_id = normalized_tenant_id
        entry.owner_user_id = owner_user_id
        entry.ticker = _normalize_ticker(plan["ticker"])
        entry.side = str(plan["side"])
        entry.status = str(plan["status"])
        entry.expires_at = _parse_datetime(plan["expires_at"])
        entry.linked_trade_id = str(plan.get("linked_trade_id") or "") or None
        entry.storage_path = _storage_path_for_plan(plan, reports_dir)
        entry.updated_at = now

    db.flush()
    return entry


def delete_trade_plan_entry(
    db: Session,
    plan_id: str,
    owner_user_id: str,
    *,
    tenant_id: str | None = None,
) -> None:
    entry = require_trade_plan_entry_for_owner(
        db, plan_id, owner_user_id, tenant_id=tenant_id
    )
    db.delete(entry)
    db.flush()


def list_trade_plan_entries_for_owner(
    db: Session,
    owner_user_id: str,
    *,
    tenant_id: str | None = None,
    ticker: str | None = None,
    status: str | None = None,
) -> list[TradePlanEntry]:
    statement = select(TradePlanEntry).where(
        TradePlanEntry.owner_user_id == owner_user_id
    )
    if tenant_id is not None:
        statement = statement.where(TradePlanEntry.tenant_id == tenant_id)
    if ticker:
        statement = statement.where(TradePlanEntry.ticker == _normalize_ticker(ticker))
    if status:
        statement = statement.where(TradePlanEntry.status == status)
    statement = statement.order_by(
        TradePlanEntry.expires_at.asc(),
        TradePlanEntry.updated_at.desc(),
        TradePlanEntry.plan_id.desc(),
    )
    return list(db.scalars(statement))


def require_trade_plan_entry_for_owner(
    db: Session,
    plan_id: str,
    owner_user_id: str,
    tenant_id: str | None = None,
) -> TradePlanEntry:
    entry = db.get(TradePlanEntry, plan_id)
    if entry is None or entry.owner_user_id != owner_user_id:
        raise ValueError(f"Trade plan '{plan_id}' not found")
    if tenant_id is not None and entry.tenant_id != tenant_id:
        raise ValueError(f"Trade plan '{plan_id}' not found")
    return entry
