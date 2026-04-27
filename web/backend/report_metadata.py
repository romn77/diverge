from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, and_, inspect, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from web.backend import auth

REPORT_VISIBILITY_PRIVATE = "private"
REPORT_VISIBILITY_WORKSPACE = "workspace"
VALID_REPORT_VISIBILITIES = {
    REPORT_VISIBILITY_PRIVATE,
    REPORT_VISIBILITY_WORKSPACE,
}
CATEGORY_DIR_MAP: dict[str, str] = {
    "analysts": "1_analysts",
    "research": "2_research",
    "trading": "3_trading",
    "risk": "4_risk",
    "portfolio": "5_portfolio",
}
_REPORT_ID_TIMESTAMP_PATTERN = re.compile(r".*_(\d{8}_\d{6})$")
_GENERATED_LINE_PATTERN = re.compile(
    r"^Generated:\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})"
)
_TITLE_PATTERN = re.compile(r"^#\s+Trading Analysis Report:\s+(\S+)")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise auth.AuthValidationError(f"{field_name} is required")
    return value.strip()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


def _normalize_visibility(value: str | None) -> str:
    candidate = (value or REPORT_VISIBILITY_PRIVATE).strip().lower()
    if candidate not in VALID_REPORT_VISIBILITIES:
        raise auth.AuthValidationError(
            "visibility must be one of private or workspace"
        )
    return candidate


def parse_complete_report_header_text(
    content: str,
) -> tuple[str | None, str | None, str | None]:
    lines = content.splitlines()[:4]
    while len(lines) < 4:
        lines.append("")

    ticker: str | None = None
    date_str: str | None = None
    time_str: str | None = None

    title_match = _TITLE_PATTERN.match(lines[0])
    if title_match:
        ticker = title_match.group(1).strip()

    for line in lines[1:]:
        generated_match = _GENERATED_LINE_PATTERN.match(line)
        if generated_match:
            date_str = generated_match.group(1)
            time_str = generated_match.group(2)
            break

    return ticker, date_str, time_str


def _artifact_type_for_path(relative_path: str) -> str:
    filename = Path(relative_path).name
    if "." not in filename:
        return filename
    return filename.rsplit(".", 1)[0]


def _parse_complete_report_header(
    report_dir: Path,
) -> tuple[str | None, str | None, str | None]:
    complete_path = report_dir / "complete_report.md"
    if not complete_path.is_file():
        return None, None, None

    try:
        content = complete_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, None, None

    return parse_complete_report_header_text(content)


def _generated_at_from_report_id(report_id: str) -> str | None:
    match = _REPORT_ID_TIMESTAMP_PATTERN.match(report_id)
    if not match:
        return None
    timestamp = match.group(1)
    try:
        parsed = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
    except ValueError:
        return None
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def build_report_file_index(report_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    complete_path = report_dir / "complete_report.md"
    if complete_path.is_file():
        entries.append(
            {
                "relative_path": "complete_report.md",
                "entry_type": "complete",
                "category_key": None,
                "artifact_type": None,
                "sort_order": 0,
                "is_primary": True,
            }
        )

    sort_order = 1
    for category_key, directory_name in CATEGORY_DIR_MAP.items():
        category_dir = report_dir / directory_name
        if not category_dir.is_dir():
            continue
        for markdown_path in sorted(category_dir.glob("*.md")):
            entries.append(
                {
                    "relative_path": markdown_path.relative_to(report_dir).as_posix(),
                    "entry_type": "category",
                    "category_key": category_key,
                    "artifact_type": None,
                    "sort_order": sort_order,
                    "is_primary": False,
                }
            )
            sort_order += 1

    artifact_dir = report_dir / "artifacts"
    if artifact_dir.is_dir():
        for artifact_path in sorted(path for path in artifact_dir.iterdir() if path.is_file()):
            relative_path = artifact_path.relative_to(report_dir).as_posix()
            entries.append(
                {
                    "relative_path": relative_path,
                    "entry_type": "artifact",
                    "category_key": None,
                    "artifact_type": _artifact_type_for_path(relative_path),
                    "sort_order": sort_order,
                    "is_primary": False,
                }
            )
            sort_order += 1

    return entries


def build_report_metadata(
    report_dir: Path,
    *,
    report_id: str | None = None,
) -> dict[str, str | None]:
    resolved_report_id = report_id or report_dir.name
    ticker, generated_date, generated_time = _parse_complete_report_header(report_dir)
    generated_at = (
        f"{generated_date} {generated_time}"
        if generated_date and generated_time
        else _generated_at_from_report_id(resolved_report_id)
    )
    return {
        "report_id": resolved_report_id,
        "ticker": ticker or resolved_report_id,
        "generated_at": generated_at,
        "storage_path": report_dir.name,
    }


def split_generated_at(value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    candidate = value.strip()
    if not candidate:
        return None, None
    if "T" in candidate:
        date_str, time_str = candidate.split("T", 1)
    elif " " in candidate:
        date_str, time_str = candidate.split(" ", 1)
    else:
        return candidate, None
    return date_str, time_str


class ReportRun(auth.Base):
    __tablename__ = "report_runs"
    __table_args__ = (
        Index("ix_report_runs_tenant_generated_at", "tenant_id", "generated_at"),
        Index("ix_report_runs_owner_generated_at", "owner_user_id", "generated_at"),
        Index("ix_report_runs_tenant_visibility_generated_at", "tenant_id", "visibility", "generated_at"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
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
    visibility: Mapped[str] = mapped_column(String(32), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    generated_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
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


class ReportFile(auth.Base):
    __tablename__ = "report_files"
    __table_args__ = (
        Index("ix_report_files_report_sort_order", "report_id", "sort_order"),
        Index(
            "ix_report_files_report_relative_path",
            "report_id",
            "relative_path",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid.uuid4().hex,
    )
    report_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("report_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    relative_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    category_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    artifact_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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


def ensure_report_metadata_tables(settings: auth.AuthSettings | None = None) -> None:
    resolved_settings = settings or auth.get_auth_settings()
    if not resolved_settings.enabled:
        return

    inspector = inspect(auth.get_engine(resolved_settings))
    required_tables = ("report_runs", "report_files")
    missing_tables = [
        table_name for table_name in required_tables if not inspector.has_table(table_name)
    ]
    if missing_tables:
        joined = ", ".join(missing_tables)
        raise RuntimeError(
            "Auth is enabled but the following report metadata tables are missing: "
            f"{joined}. Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )


def initialize_report_metadata_runtime() -> None:
    ensure_report_metadata_tables()


def upsert_report_run(
    db: Session,
    *,
    report_id: str,
    owner_user_id: str,
    tenant_id: str | None = None,
    visibility: str,
    ticker: str,
    generated_at: str | None,
    storage_path: str,
    file_entries: list[dict[str, Any]],
) -> ReportRun:
    normalized_report_id = _normalize_text(report_id, "report_id")
    normalized_owner_user_id = _normalize_text(owner_user_id, "owner_user_id")
    normalized_tenant_id = _normalize_optional_text(tenant_id)
    if normalized_tenant_id is None:
        owner = db.get(auth.User, normalized_owner_user_id)
        normalized_tenant_id = owner.tenant_id if owner is not None else auth.DEFAULT_TENANT_ID
    normalized_visibility = _normalize_visibility(visibility)
    normalized_ticker = _normalize_text(ticker, "ticker").upper()
    normalized_storage_path = _normalize_text(storage_path, "storage_path")
    normalized_generated_at = _normalize_optional_text(generated_at)

    record = db.get(ReportRun, normalized_report_id)
    now = _utcnow()
    if record is None:
        record = ReportRun(
            id=normalized_report_id,
            tenant_id=normalized_tenant_id,
            owner_user_id=normalized_owner_user_id,
            visibility=normalized_visibility,
            ticker=normalized_ticker,
            generated_at=normalized_generated_at,
            storage_path=normalized_storage_path,
            created_at=now,
            updated_at=now,
        )
        db.add(record)
    else:
        record.tenant_id = normalized_tenant_id
        record.owner_user_id = normalized_owner_user_id
        record.visibility = normalized_visibility
        record.ticker = normalized_ticker
        record.generated_at = normalized_generated_at
        record.storage_path = normalized_storage_path
        record.updated_at = now

    db.flush()
    db.query(ReportFile).filter(ReportFile.report_id == normalized_report_id).delete()
    for entry in file_entries:
        db.add(
            ReportFile(
                report_id=normalized_report_id,
                relative_path=_normalize_text(entry.get("relative_path"), "relative_path"),
                entry_type=_normalize_text(entry.get("entry_type"), "entry_type"),
                category_key=_normalize_optional_text(entry.get("category_key")),
                artifact_type=_normalize_optional_text(entry.get("artifact_type")),
                sort_order=int(entry.get("sort_order", 0)),
                is_primary=bool(entry.get("is_primary", False)),
            )
        )
    db.flush()
    return record


def list_report_runs(
    db: Session,
    *,
    tenant_id: str | None = None,
    owner_user_id: str | None = None,
    include_workspace: bool = False,
) -> list[ReportRun]:
    statement = select(ReportRun)
    if tenant_id is not None:
        normalized_tenant_id = _normalize_text(tenant_id, "tenant_id")
        statement = statement.where(
            or_(ReportRun.tenant_id == normalized_tenant_id, ReportRun.tenant_id.is_(None))
        )
    if owner_user_id is not None:
        if include_workspace:
            statement = statement.where(
                or_(
                    ReportRun.owner_user_id == owner_user_id,
                    ReportRun.visibility == REPORT_VISIBILITY_WORKSPACE,
                )
            )
        else:
            statement = statement.where(ReportRun.owner_user_id == owner_user_id)
    statement = statement.order_by(ReportRun.generated_at.desc(), ReportRun.id.desc())
    return list(db.scalars(statement))


def get_report_run(
    db: Session,
    report_id: str,
    *,
    tenant_id: str | None = None,
    owner_user_id: str | None = None,
    include_workspace: bool = False,
) -> ReportRun:
    statement = select(ReportRun).where(ReportRun.id == report_id)
    if tenant_id is not None:
        normalized_tenant_id = _normalize_text(tenant_id, "tenant_id")
        statement = statement.where(
            or_(ReportRun.tenant_id == normalized_tenant_id, ReportRun.tenant_id.is_(None))
        )
    if owner_user_id is not None:
        if include_workspace:
            statement = statement.where(
                or_(
                    ReportRun.owner_user_id == owner_user_id,
                    ReportRun.visibility == REPORT_VISIBILITY_WORKSPACE,
                )
            )
        else:
            statement = statement.where(ReportRun.owner_user_id == owner_user_id)
    record = db.scalar(statement)
    if record is None:
        raise auth.AuthNotFoundError(f"Report '{report_id}' not found")
    return record


def list_report_files(db: Session, report_id: str) -> list[ReportFile]:
    statement = (
        select(ReportFile)
        .where(ReportFile.report_id == report_id)
        .order_by(ReportFile.sort_order.asc(), ReportFile.relative_path.asc())
    )
    return list(db.scalars(statement))


def get_report_file(
    db: Session,
    *,
    report_id: str,
    relative_path: str,
) -> ReportFile:
    statement = select(ReportFile).where(
        and_(
            ReportFile.report_id == report_id,
            ReportFile.relative_path == relative_path,
        )
    )
    record = db.scalar(statement)
    if record is None:
        raise auth.AuthNotFoundError(
            f"File '{relative_path}' not found for report '{report_id}'"
        )
    return record


def serialize_report_summary(record: ReportRun) -> dict[str, Any]:
    date_str, time_str = split_generated_at(record.generated_at)
    return {
        "id": record.id,
        "ticker": record.ticker,
        "date": date_str,
        "time": time_str,
        "visibility": record.visibility,
        "tenant_id": record.tenant_id,
        "owner_user_id": record.owner_user_id,
    }
