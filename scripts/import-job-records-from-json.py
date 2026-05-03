#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web.backend import app_config, auth, job_records
from web.backend.runtime import analysis_tasks, data_sync_tasks, screener_tasks


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _analysis_paths() -> Iterable[Path]:
    yield from sorted(analysis_tasks.active_tasks_dir().glob("*/task.json"))


def _screener_paths() -> Iterable[Path]:
    yield from sorted(screener_tasks.active_screener_tasks_dir().glob("*/task.json"))


def _data_sync_paths() -> Iterable[Path]:
    yield from sorted((app_config.SCREENER_STATE_DIR / "data_sync").glob("*.json"))


def _status_for_import(status: str) -> tuple[str, str | None]:
    if status == "running":
        return "failed", app_config.RECOVERED_TASK_ERROR
    return status, None


def _import_analysis(payload: dict[str, Any], *, dry_run: bool) -> str | None:
    task = analysis_tasks.task_from_snapshot(payload)
    status, recovered_error = _status_for_import(task.status)
    task.status = status
    if recovered_error:
        task.error = recovered_error
        task.finished_at = task.finished_at or analysis_tasks._utc_iso()
    if not dry_run:
        job_records.upsert_job_record(
            kind="analysis",
            task_id=task.id,
            status=task.status,
            request_payload=task.to_dict().get("request_payload"),
            result_summary={"report_id": task.report_id} if task.report_id else None,
            error=task.error,
            owner_user_id=task.owner_user_id,
            tenant_id=task.tenant_id,
            created_at=task.created_at,
            queued_at=task.queued_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
        )
    return task.id


def _import_screener(payload: dict[str, Any], *, dry_run: bool) -> str | None:
    task = screener_tasks.screener_task_from_payload(payload)
    status, recovered_error = _status_for_import(task.status)
    task.status = status
    if recovered_error:
        task.error = recovered_error
        task.finished_at = task.finished_at or screener_tasks._utc_iso()
    if not dry_run:
        job_records.upsert_job_record(
            kind="screener",
            task_id=task.id,
            status=task.status,
            request_payload=task.request_payload,
            result_summary={"run_id": task.run_id} if task.run_id else None,
            error=task.error,
            owner_user_id=task.owner_user_id,
            tenant_id=task.tenant_id,
            created_at=task.created_at,
            queued_at=task.queued_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
        )
    return task.id


def _import_data_sync(payload: dict[str, Any], *, dry_run: bool) -> str | None:
    task = data_sync_tasks.data_sync_task_from_payload(payload)
    status, recovered_error = _status_for_import(task.status)
    task.status = status
    if recovered_error:
        task.error = recovered_error
        task.finished_at = task.finished_at or data_sync_tasks._utc_iso()
    if not dry_run:
        job_records.upsert_job_record(
            kind="data_sync",
            task_id=task.id,
            status=task.status,
            request_payload=task.request_payload,
            result_summary=task.result,
            error=task.error,
            owner_user_id=task.owner_user_id,
            tenant_id=task.tenant_id,
            created_at=task.created_at,
            queued_at=task.queued_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
        )
    return task.id


def import_records(*, dry_run: bool = False) -> dict[str, int]:
    if not dry_run:
        auth.initialize_auth_runtime()
        job_records.initialize_job_record_runtime()
    importers = {
        "analysis": (_analysis_paths(), _import_analysis),
        "screener": (_screener_paths(), _import_screener),
        "data_sync": (_data_sync_paths(), _import_data_sync),
    }
    counts = {kind: 0 for kind in importers}
    for kind, (paths, importer) in importers.items():
        for path in paths:
            payload = _read_json(path)
            if not payload:
                continue
            try:
                task_id = importer(payload, dry_run=dry_run)
            except (KeyError, TypeError, ValueError, RuntimeError):
                continue
            if task_id:
                counts[kind] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import local task JSON snapshots into job_records."
    )
    parser.add_argument("--dry-run", action="store_true", help="Count importable records without writing DB.")
    args = parser.parse_args()
    counts = import_records(dry_run=args.dry_run)
    mode = "would import" if args.dry_run else "imported"
    print(
        f"{mode}: analysis={counts['analysis']} screener={counts['screener']} "
        f"data_sync={counts['data_sync']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
