from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import select

from tradingagents.trade_feedback import (
    list_trade_records as list_trade_records_file,
    list_trade_reviews as list_trade_reviews_file,
)
from tradingagents.data_layout import resolve_reports_dir, resolve_screener_runs_dir
from web.backend import auth, report_metadata, screener_results, screener_runs, trade_entries

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = resolve_reports_dir(PROJECT_ROOT)
SCREENER_RUNS_DIR = resolve_screener_runs_dir(PROJECT_ROOT)
SCREENER_ARTIFACT_FILENAMES = {
    "run_meta": "run_meta.json",
    "universe": "universe.csv",
    "features": "features.csv",
    "filtered_out": "filtered_out.csv",
    "candidates": "candidates.csv",
    "llm_pool": "llm_pool.json",
}

logger = logging.getLogger(__name__)


@dataclass
class BackfillSummary:
    reports: int = 0
    report_files: int = 0
    trades: int = 0
    screener_runs: int = 0


def _configure_logging() -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _resolve_historical_owner(db) -> auth.User:
    settings = auth.get_auth_settings()
    auth.ensure_bootstrap_admin(db, settings)

    if settings.bootstrap_admin_email:
        user = auth.get_user_by_email(db, settings.bootstrap_admin_email)
        if user is not None:
            return user

    user = db.scalar(
        select(auth.User).where(
            auth.User.role == auth.UserRole.ADMIN.value,
            auth.User.status == auth.UserStatus.ACTIVE.value,
        ).order_by(auth.User.created_at.asc(), auth.User.email.asc())
    )
    if user is None:
        raise RuntimeError(
            "No active admin user exists for historical metadata ownership"
        )
    return user


def _relative_screener_storage_path(path: Path) -> str:
    resolved_root = SCREENER_RUNS_DIR.resolve()
    resolved_path = path.resolve()
    return resolved_path.relative_to(resolved_root).as_posix()


def _build_screener_artifact_manifest(run_dir: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for artifact_key, filename in SCREENER_ARTIFACT_FILENAMES.items():
        artifact_path = run_dir / filename
        if artifact_path.is_file():
            manifest[artifact_key] = _relative_screener_storage_path(artifact_path)
    return manifest


def _backfill_reports(db, owner_user_id: str) -> tuple[int, int]:
    if not REPORTS_DIR.is_dir():
        return 0, 0

    report_count = 0
    file_count = 0
    for report_dir in sorted(REPORTS_DIR.iterdir()):
        if not report_dir.is_dir() or report_dir.name.startswith("."):
            continue

        metadata_payload = report_metadata.build_report_metadata(
            report_dir,
            report_id=report_dir.name,
        )
        file_entries = report_metadata.build_report_file_index(report_dir)
        report_metadata.upsert_report_run(
            db,
            report_id=str(metadata_payload["report_id"] or report_dir.name),
            owner_user_id=owner_user_id,
            visibility=report_metadata.REPORT_VISIBILITY_WORKSPACE,
            ticker=str(metadata_payload["ticker"] or report_dir.name),
            generated_at=metadata_payload["generated_at"],
            storage_path=str(metadata_payload["storage_path"] or report_dir.name),
            file_entries=file_entries,
        )
        report_count += 1
        file_count += len(file_entries)
    return report_count, file_count


def _backfill_trades(db, owner_user_id: str) -> int:
    trade_count = 0
    for record in list_trade_records_file(reports_dir=REPORTS_DIR):
        reviews = list_trade_reviews_file(record["trade_id"], reports_dir=REPORTS_DIR)
        trade_entries.upsert_trade_entry(
            db,
            record,
            owner_user_id=owner_user_id,
            reports_dir=REPORTS_DIR,
            reviews=reviews,
        )
        trade_count += 1
    return trade_count


def _backfill_screener_runs(db, owner_user_id: str) -> int:
    if not SCREENER_RUNS_DIR.is_dir():
        return 0

    run_count = 0
    for run_dir in sorted(SCREENER_RUNS_DIR.iterdir()):
        if not run_dir.is_dir() or run_dir.name.startswith("."):
            continue

        run_meta_path = run_dir / "run_meta.json"
        if not run_meta_path.is_file():
            continue
        try:
            payload = json.loads(run_meta_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("Skipping unreadable screener metadata for %s", run_dir.name)
            continue

        screener_runs.upsert_screener_run(
            db,
            run_id=run_dir.name,
            owner_user_id=owner_user_id,
            as_of_date=str(payload.get("as_of_date") or "").strip() or None,
            markets=list(payload.get("config", {}).get("markets") or []),
            candidate_count=int(payload.get("candidate_count") or 0),
            generated_at=str(payload.get("run_timestamp") or run_dir.name),
            storage_path=_relative_screener_storage_path(run_dir),
            artifact_manifest=_build_screener_artifact_manifest(run_dir),
        )
        run_count += 1
    return run_count


def backfill_all_metadata() -> BackfillSummary:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        raise RuntimeError(
            "Auth must be enabled to backfill metadata. "
            "Use AUTH_ENABLED=true and run this before exposing the authenticated workbench."
        )

    auth.initialize_auth_runtime()
    trade_entries.initialize_trade_entries_runtime()
    screener_runs.initialize_screener_runtime()
    report_metadata.initialize_report_metadata_runtime()

    summary = BackfillSummary()
    with auth.db_session() as db:
        owner_user = _resolve_historical_owner(db)
        summary.reports, summary.report_files = _backfill_reports(db, owner_user.id)
        summary.trades = _backfill_trades(db, owner_user.id)
        summary.screener_runs = _backfill_screener_runs(db, owner_user.id)
    screener_results.migrate_all_legacy_screener_results(force=True)

    logger.info(
        "metadata backfill complete owner_user_id=%s reports=%d report_files=%d trades=%d screener_runs=%d",
        owner_user.id,
        summary.reports,
        summary.report_files,
        summary.trades,
        summary.screener_runs,
    )
    return summary


def main() -> None:
    _configure_logging()
    summary = backfill_all_metadata()
    print(json.dumps(asdict(summary), sort_keys=True))


if __name__ == "__main__":
    main()
