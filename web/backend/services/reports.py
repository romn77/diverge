from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import HTTPException, Request

from web.backend import access, app_config, auth, report_metadata


def parse_complete_report_header(
    report_dir: Path,
) -> tuple[str | None, str | None, str | None]:
    complete = report_dir / "complete_report.md"
    if not complete.is_file():
        return None, None, None

    try:
        with complete.open(encoding="utf-8") as file_handle:
            lines = [file_handle.readline() for _ in range(4)]

        ticker: str | None = None
        date_str: str | None = None
        time_str: str | None = None

        ticker_match = re.match(r"^#\s+Trading Analysis Report:\s+(\S+)", lines[0])
        if ticker_match:
            ticker = ticker_match.group(1).strip()

        for line in lines[1:]:
            generated_match = re.match(
                r"^Generated:\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})",
                line,
            )
            if generated_match:
                date_str = generated_match.group(1)
                time_str = generated_match.group(2)
                break

        return ticker, date_str, time_str
    except (OSError, UnicodeDecodeError):
        return None, None, None


def scan_categories(report_dir: Path) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {}
    for key, dir_name in report_metadata.CATEGORY_DIR_MAP.items():
        category_dir = report_dir / dir_name
        if category_dir.is_dir():
            stems = sorted(
                path.stem
                for path in category_dir.iterdir()
                if path.suffix == ".md" and path.is_file()
            )
            if stems:
                categories[key] = stems
    return categories


def scan_artifacts(report_dir: Path) -> list[dict]:
    artifacts_dir = report_dir / "artifacts"
    if not artifacts_dir.is_dir():
        return []

    results = []
    summary_path = artifacts_dir / "summary.json"
    if summary_path.is_file():
        summary = None
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                summary = payload.get("summary")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            summary = None

        results.append(
            {
                "type": "summary",
                "path": "artifacts/summary.json",
                "summary": summary,
            }
        )

    thesis_path = artifacts_dir / "thesis.json"
    if thesis_path.is_file():
        summary = None
        try:
            payload = json.loads(thesis_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                summary = payload.get("thesis_summary")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            summary = None

        results.append(
            {
                "type": "thesis",
                "path": "artifacts/thesis.json",
                "summary": summary,
            }
        )

    trade_feedback_path = artifacts_dir / "trade_feedback.json"
    if trade_feedback_path.is_file():
        summary = None
        try:
            payload = json.loads(trade_feedback_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                review_count = len(payload.get("reviews") or [])
                summary = (
                    f"{review_count} historical review(s)"
                    if review_count
                    else "Historical feedback prompt"
                )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            summary = None

        results.append(
            {
                "type": "trade_feedback",
                "path": "artifacts/trade_feedback.json",
                "summary": summary,
            }
        )

    return results


def resolve_report_dir(report_id: str) -> Path:
    if report_id.startswith("."):
        raise HTTPException(status_code=404, detail="Report not found")
    if "/" in report_id or "\\" in report_id or ".." in report_id:
        raise HTTPException(status_code=404, detail="Report not found")

    report_dir = app_config.REPORTS_DIR / report_id
    if not report_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return report_dir


def resolve_report_dir_from_storage_path(storage_path: str) -> Path:
    report_dir = (app_config.REPORTS_DIR / storage_path).resolve()
    try:
        report_dir.relative_to(app_config.REPORTS_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    if not report_dir.is_dir():
        raise HTTPException(status_code=404, detail="Report not found")
    return report_dir


def build_report_structure_from_index(
    report_dir: Path,
    file_entries: list[report_metadata.ReportFile],
) -> dict:
    categories: dict[str, list[str]] = {}
    artifacts: list[dict] = []
    has_complete = False
    disk_artifacts = {
        artifact["path"]: artifact for artifact in scan_artifacts(report_dir)
    }

    for entry in file_entries:
        if entry.entry_type == "complete":
            has_complete = True
            continue
        if entry.entry_type == "category" and entry.category_key:
            categories.setdefault(entry.category_key, []).append(
                Path(entry.relative_path).stem
            )
            continue
        if entry.entry_type == "artifact":
            artifact_payload = {
                "type": entry.artifact_type or Path(entry.relative_path).stem,
                "path": entry.relative_path,
            }
            disk_summary = disk_artifacts.get(entry.relative_path, {}).get("summary")
            if disk_summary is not None:
                artifact_payload["summary"] = disk_summary
            artifacts.append(artifact_payload)

    return {
        "has_complete": has_complete,
        "categories": categories,
        "artifacts": artifacts,
    }


def list_reports(request: Request | None = None) -> list[dict]:
    if auth.auth_enabled() and request is not None:
        try:
            with auth.db_session() as db:
                current_user = auth.get_request_user(db, request)
                if current_user is not None:
                    owner_scope = access.owner_scope_for_user(current_user)
                    records = report_metadata.list_report_runs(
                        db,
                        owner_user_id=owner_scope,
                        include_workspace=owner_scope is not None,
                    )
                    return [
                        report_metadata.serialize_report_summary(record)
                        for record in records
                    ]
        except Exception as exc:
            raise access.translate_auth_error(exc) from exc

    if not app_config.REPORTS_DIR.is_dir():
        return []

    results = []
    for entry in app_config.REPORTS_DIR.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        report_id = entry.name
        ticker, date_str, time_str = parse_complete_report_header(entry)
        if ticker is None:
            ticker = report_id

        results.append(
            {
                "id": report_id,
                "ticker": ticker,
                "date": date_str,
                "time": time_str,
            }
        )

    results.sort(key=lambda row: (row["date"] or "", row["time"] or ""), reverse=True)
    return results


def get_structure(report_id: str, request: Request | None = None) -> dict:
    if auth.auth_enabled() and request is not None:
        try:
            with auth.db_session() as db:
                current_user = auth.get_request_user(db, request)
                if current_user is not None:
                    owner_scope = access.owner_scope_for_user(current_user)
                    record = report_metadata.get_report_run(
                        db,
                        report_id,
                        owner_user_id=owner_scope,
                        include_workspace=owner_scope is not None,
                    )
                    report_dir = resolve_report_dir_from_storage_path(record.storage_path)
                    structure = build_report_structure_from_index(
                        report_dir,
                        report_metadata.list_report_files(db, report_id),
                    )
                    return {
                        "id": record.id,
                        "ticker": record.ticker,
                        **structure,
                    }
        except Exception as exc:
            raise access.translate_auth_error(exc) from exc

    report_dir = resolve_report_dir(report_id)

    ticker, _date, _time = parse_complete_report_header(report_dir)
    if ticker is None:
        ticker = report_id

    return {
        "id": report_id,
        "ticker": ticker,
        "has_complete": (report_dir / "complete_report.md").is_file(),
        "categories": scan_categories(report_dir),
        "artifacts": scan_artifacts(report_dir),
    }


def get_content(report_id: str, path: str, request: Request | None = None) -> dict:
    if auth.auth_enabled() and request is not None:
        try:
            with auth.db_session() as db:
                current_user = auth.get_request_user(db, request)
                if current_user is not None:
                    owner_scope = access.owner_scope_for_user(current_user)
                    record = report_metadata.get_report_run(
                        db,
                        report_id,
                        owner_user_id=owner_scope,
                        include_workspace=owner_scope is not None,
                    )
                    report_metadata.get_report_file(
                        db,
                        report_id=record.id,
                        relative_path=path,
                    )
                    report_dir = resolve_report_dir_from_storage_path(record.storage_path)
                else:
                    report_dir = resolve_report_dir(report_id)
        except Exception as exc:
            raise access.translate_auth_error(exc) from exc
    else:
        report_dir = resolve_report_dir(report_id)

    report_dir_resolved = report_dir.resolve()
    target = (report_dir_resolved / path).resolve()

    try:
        target.relative_to(report_dir_resolved)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Access denied") from exc

    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"File '{path}' not found")

    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {exc}") from exc

    return {"content": content}
