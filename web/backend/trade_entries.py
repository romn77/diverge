from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, inspect, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from tradingagents.trade_feedback import TRADE_RECORD_FILENAME
from web.backend import auth


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    candidate = str(value).strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_ticker(value: str) -> str:
    return str(value).strip().upper()


def _storage_path_for_record(record: dict, reports_dir: Path) -> str:
    reports_root = Path(reports_dir).resolve()
    record_path = (
        reports_root
        / ".trade_feedback"
        / _normalize_ticker(record["ticker"])
        / record["trade_id"]
        / TRADE_RECORD_FILENAME
    )
    return record_path.relative_to(reports_root).as_posix()


def _review_summary(reviews: Iterable[dict]) -> tuple[int, datetime | None]:
    review_items = list(reviews)
    latest_review = max(
        (
            parsed
            for parsed in (
                _parse_datetime(review.get("updated_at")) for review in review_items
            )
            if parsed is not None
        ),
        default=None,
    )
    return len(review_items), latest_review


class TradeEntry(auth.Base):
    __tablename__ = "trade_entries"
    __table_args__ = (
        Index("ix_trade_entries_tenant_updated_at", "tenant_id", "updated_at"),
        Index("ix_trade_entries_owner_updated_at", "owner_user_id", "updated_at"),
        Index(
            "ix_trade_entries_tenant_owner_ticker_updated_at",
            "tenant_id",
            "owner_user_id",
            "ticker",
            "updated_at",
        ),
    )

    trade_id: Mapped[str] = mapped_column(String(32), primary_key=True)
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
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
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


def ensure_trade_entries_table(settings: auth.AuthSettings | None = None) -> None:
    resolved_settings = settings or auth.get_auth_settings()
    if not resolved_settings.enabled:
        return

    inspector = inspect(auth.get_engine(resolved_settings))
    if not inspector.has_table("trade_entries"):
        raise RuntimeError(
            "Auth is enabled but the trade_entries table is missing. "
            "Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )


def initialize_trade_entries_runtime() -> None:
    ensure_trade_entries_table()


def upsert_trade_entry(
    db: Session,
    record: dict,
    *,
    owner_user_id: str,
    tenant_id: str | None = None,
    reports_dir: Path,
    reviews: Iterable[dict] = (),
) -> TradeEntry:
    review_count, last_review_at = _review_summary(reviews)
    now = _utcnow()
    normalized_tenant_id = tenant_id.strip() if isinstance(tenant_id, str) and tenant_id.strip() else None
    if normalized_tenant_id is None:
        owner = db.get(auth.User, owner_user_id)
        normalized_tenant_id = owner.tenant_id if owner is not None else auth.DEFAULT_TENANT_ID

    entry = db.get(TradeEntry, record["trade_id"])
    if entry is None:
        entry = TradeEntry(
            trade_id=record["trade_id"],
            tenant_id=normalized_tenant_id,
            owner_user_id=owner_user_id,
            ticker=_normalize_ticker(record["ticker"]),
            status=str(record["status"]),
            storage_path=_storage_path_for_record(record, reports_dir),
            review_count=review_count,
            last_review_at=last_review_at,
            created_at=now,
            updated_at=now,
        )
        db.add(entry)
    else:
        entry.tenant_id = normalized_tenant_id
        entry.owner_user_id = owner_user_id
        entry.ticker = _normalize_ticker(record["ticker"])
        entry.status = str(record["status"])
        entry.storage_path = _storage_path_for_record(record, reports_dir)
        entry.review_count = review_count
        entry.last_review_at = last_review_at
        entry.updated_at = now

    db.flush()
    return entry


def list_trade_entries_for_owner(
    db: Session,
    owner_user_id: str,
    *,
    tenant_id: str | None = None,
    ticker: str | None = None,
) -> list[TradeEntry]:
    statement = select(TradeEntry).where(TradeEntry.owner_user_id == owner_user_id)
    if tenant_id is not None:
        statement = statement.where(TradeEntry.tenant_id == tenant_id)
    if ticker:
        statement = statement.where(TradeEntry.ticker == _normalize_ticker(ticker))
    statement = statement.order_by(TradeEntry.updated_at.desc(), TradeEntry.trade_id.desc())
    return list(db.scalars(statement))


def list_visible_trade_ids(
    db: Session,
    owner_user_id: str,
    *,
    tenant_id: str | None = None,
    ticker: str | None = None,
) -> set[str]:
    return {
        entry.trade_id
        for entry in list_trade_entries_for_owner(
            db,
            owner_user_id,
            tenant_id=tenant_id,
            ticker=ticker,
        )
    }


def require_trade_entry_for_owner(
    db: Session,
    trade_id: str,
    owner_user_id: str,
    tenant_id: str | None = None,
) -> TradeEntry:
    entry = db.get(TradeEntry, trade_id)
    if entry is None or entry.owner_user_id != owner_user_id:
        raise ValueError(f"Trade '{trade_id}' not found")
    if tenant_id is not None and entry.tenant_id != tenant_id:
        raise ValueError(f"Trade '{trade_id}' not found")
    return entry
