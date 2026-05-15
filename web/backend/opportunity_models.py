from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    inspect,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from web.backend import auth


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OpportunityRun(auth.Base):
    __tablename__ = "opportunity_runs"
    __table_args__ = (
        Index("ix_opportunity_runs_tenant_trade_date", "tenant_id", "trade_date"),
        Index(
            "ix_opportunity_runs_config",
            "tenant_id",
            "market",
            "trade_date",
            "config_hash",
        ),
        Index("ix_opportunity_runs_generated_at", "generated_at"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True
    )
    owner_user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    market: Mapped[str] = mapped_column(String(16), nullable=False)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    artifact_manifest: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class BacktestRun(auth.Base):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_runs_tenant_strategy", "tenant_id", "strategy_id"),
        Index("ix_backtest_runs_generated_at", "generated_at"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True
    )
    owner_user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    strategy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="cn")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    artifact_manifest: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class WatchlistItem(auth.Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        Index(
            "ix_watchlist_items_owner_symbol", "owner_user_id", "symbol", unique=True
        ),
        Index("ix_watchlist_items_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="cn")
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    theme_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


def ensure_opportunity_tables(settings: auth.AuthSettings | None = None) -> None:
    resolved_settings = settings or auth.get_auth_settings()
    if not resolved_settings.enabled:
        return
    inspector = inspect(auth.get_engine(resolved_settings))
    missing = [
        name
        for name in ("opportunity_runs", "backtest_runs", "watchlist_items")
        if not inspector.has_table(name)
    ]
    if missing:
        raise RuntimeError(
            "Auth is enabled but opportunity tables are missing. Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )


def initialize_opportunity_runtime() -> None:
    ensure_opportunity_tables()


def upsert_opportunity_run(
    db: Session,
    *,
    run_id: str,
    tenant_id: str | None,
    owner_user_id: str | None,
    market: str,
    trade_date: str,
    config_hash: str,
    revision: int,
    status: str,
    candidate_count: int,
    generated_at: str,
    storage_path: str,
    artifact_manifest: dict[str, str],
) -> OpportunityRun:
    record = db.get(OpportunityRun, run_id)
    if record is None:
        record = OpportunityRun(id=run_id)
        db.add(record)
    record.tenant_id = tenant_id
    record.owner_user_id = owner_user_id
    record.market = market
    record.trade_date = trade_date
    record.config_hash = config_hash
    record.revision = revision
    record.status = status
    record.candidate_count = int(candidate_count)
    record.generated_at = generated_at
    record.storage_path = storage_path
    record.artifact_manifest = dict(artifact_manifest or {})
    record.updated_at = _utcnow()
    db.flush()
    return record
