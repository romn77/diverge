from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, inspect, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from web.backend import auth


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AssetAccount(auth.Base):
    __tablename__ = "asset_accounts"
    __table_args__ = (
        Index("ix_asset_accounts_owner_updated_at", "owner_user_id", "updated_at"),
        Index(
            "ix_asset_accounts_owner_platform_account",
            "owner_user_id",
            "platform_name",
            "account_name",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid.uuid4().hex,
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
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


class AssetPosition(auth.Base):
    __tablename__ = "asset_positions"
    __table_args__ = (
        Index("ix_asset_positions_owner_updated_at", "owner_user_id", "updated_at"),
        Index(
            "ix_asset_positions_owner_ticker_updated_at",
            "owner_user_id",
            "ticker",
            "updated_at",
        ),
        Index("ix_asset_positions_account_updated_at", "account_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid.uuid4().hex,
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("asset_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_category: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    cost_basis: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    valuation_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    manual_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(32), nullable=True)
    market: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quote_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quote_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mapping_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unresolved")
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
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


class AssetValuationSnapshot(auth.Base):
    __tablename__ = "asset_valuation_snapshots"
    __table_args__ = (
        Index(
            "ix_asset_valuation_snapshots_position_captured_at",
            "position_id",
            "captured_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid.uuid4().hex,
    )
    position_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("asset_positions.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    quote_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    base_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    fx_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unrealized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )


def ensure_asset_tables(settings: auth.AuthSettings | None = None) -> None:
    resolved_settings = settings or auth.get_auth_settings()
    if not resolved_settings.enabled:
        return

    inspector = inspect(auth.get_engine(resolved_settings))
    required_tables = (
        "asset_accounts",
        "asset_positions",
        "asset_valuation_snapshots",
    )
    missing_tables = [
        table_name for table_name in required_tables if not inspector.has_table(table_name)
    ]
    if missing_tables:
        joined = ", ".join(missing_tables)
        raise RuntimeError(
            "Auth is enabled but the following asset tables are missing: "
            f"{joined}. Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )


def initialize_asset_runtime() -> None:
    ensure_asset_tables()


def _require_text(value: str | None, field_name: str) -> str:
    if value is None or not str(value).strip():
        raise auth.AuthValidationError(f"{field_name} is required")
    return str(value).strip()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _normalize_upper(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    return normalized.upper() if normalized else None


def serialize_asset_account(account: AssetAccount) -> dict[str, Any]:
    return {
        "id": account.id,
        "owner_user_id": account.owner_user_id,
        "platform_name": account.platform_name,
        "account_name": account.account_name,
        "created_at": account.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "updated_at": account.updated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def serialize_asset_snapshot(snapshot: AssetValuationSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "id": snapshot.id,
        "position_id": snapshot.position_id,
        "status": snapshot.status,
        "price": snapshot.price,
        "quote_currency": snapshot.quote_currency,
        "base_currency": snapshot.base_currency,
        "fx_rate": snapshot.fx_rate,
        "market_value": snapshot.market_value,
        "unrealized_pnl": snapshot.unrealized_pnl,
        "source": snapshot.source,
        "error_message": snapshot.error_message,
        "captured_at": snapshot.captured_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def get_or_create_asset_account(
    db: Session,
    *,
    owner_user_id: str,
    platform_name: str,
    account_name: str,
) -> AssetAccount:
    normalized_owner_user_id = _require_text(owner_user_id, "owner_user_id")
    normalized_platform_name = _require_text(platform_name, "platform_name")
    normalized_account_name = _require_text(account_name, "account_name")

    statement = select(AssetAccount).where(
        AssetAccount.owner_user_id == normalized_owner_user_id,
        AssetAccount.platform_name == normalized_platform_name,
        AssetAccount.account_name == normalized_account_name,
    )
    record = db.scalar(statement)
    if record is not None:
        return record

    record = AssetAccount(
        owner_user_id=normalized_owner_user_id,
        platform_name=normalized_platform_name,
        account_name=normalized_account_name,
    )
    db.add(record)
    db.flush()
    return record


def list_asset_account_records(
    db: Session,
    *,
    owner_user_id: str | None = None,
) -> list[AssetAccount]:
    statement = select(AssetAccount)
    if owner_user_id is not None:
        statement = statement.where(
            AssetAccount.owner_user_id == _require_text(owner_user_id, "owner_user_id")
        )
    statement = statement.order_by(
        AssetAccount.platform_name.asc(),
        AssetAccount.account_name.asc(),
        AssetAccount.id.asc(),
    )
    return list(db.scalars(statement))


def get_asset_account_record(
    db: Session,
    account_id: str,
    *,
    owner_user_id: str | None = None,
) -> AssetAccount:
    normalized_account_id = _require_text(account_id, "account_id")
    statement = select(AssetAccount).where(AssetAccount.id == normalized_account_id)
    if owner_user_id is not None:
        statement = statement.where(
            AssetAccount.owner_user_id == _require_text(owner_user_id, "owner_user_id")
        )
    record = db.scalar(statement)
    if record is None:
        raise auth.AuthNotFoundError(f"Asset account '{normalized_account_id}' not found")
    return record


def list_asset_position_records(
    db: Session,
    *,
    owner_user_id: str | None = None,
) -> list[AssetPosition]:
    statement = select(AssetPosition)
    if owner_user_id is not None:
        statement = statement.where(
            AssetPosition.owner_user_id == _require_text(owner_user_id, "owner_user_id")
        )
    statement = statement.order_by(
        AssetPosition.asset_name.asc(),
        AssetPosition.updated_at.desc(),
        AssetPosition.id.asc(),
    )
    return list(db.scalars(statement))


def get_asset_position_record(
    db: Session,
    position_id: str,
    *,
    owner_user_id: str | None = None,
) -> AssetPosition:
    normalized_position_id = _require_text(position_id, "position_id")
    statement = select(AssetPosition).where(AssetPosition.id == normalized_position_id)
    if owner_user_id is not None:
        statement = statement.where(
            AssetPosition.owner_user_id == _require_text(owner_user_id, "owner_user_id")
        )
    record = db.scalar(statement)
    if record is None:
        raise auth.AuthNotFoundError(f"Asset position '{normalized_position_id}' not found")
    return record


def list_latest_snapshots_by_position(
    db: Session,
    position_ids: list[str],
) -> dict[str, AssetValuationSnapshot]:
    if not position_ids:
        return {}

    statement = (
        select(AssetValuationSnapshot)
        .where(AssetValuationSnapshot.position_id.in_(position_ids))
        .order_by(
            AssetValuationSnapshot.position_id.asc(),
            AssetValuationSnapshot.captured_at.desc(),
            AssetValuationSnapshot.id.desc(),
        )
    )
    latest: dict[str, AssetValuationSnapshot] = {}
    for snapshot in db.scalars(statement):
        latest.setdefault(snapshot.position_id, snapshot)
    return latest


def add_asset_snapshot(
    db: Session,
    *,
    position_id: str,
    status: str,
    price: float | None = None,
    quote_currency: str | None = None,
    base_currency: str | None = None,
    fx_rate: float | None = None,
    market_value: float | None = None,
    unrealized_pnl: float | None = None,
    source: str | None = None,
    error_message: str | None = None,
    captured_at: datetime | None = None,
) -> AssetValuationSnapshot:
    snapshot = AssetValuationSnapshot(
        position_id=_require_text(position_id, "position_id"),
        status=_require_text(status, "status"),
        price=price,
        quote_currency=_normalize_upper(quote_currency),
        base_currency=_normalize_upper(base_currency),
        fx_rate=fx_rate,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        source=_normalize_optional_text(source),
        error_message=_normalize_optional_text(error_message),
        captured_at=captured_at.astimezone(timezone.utc) if captured_at is not None else _utcnow(),
    )
    db.add(snapshot)
    db.flush()
    return snapshot
