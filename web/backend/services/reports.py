from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from fastapi import HTTPException, Request
from web.backend import access, app_config, audit, auth, report_metadata, storage

logger = logging.getLogger(__name__)
MARKET_BRIEF_REPORT_ID_PREFIX = "MARKET_BRIEF_"
MARKET_BRIEF_REPORT_TICKER = "MARKET_BRIEF"


def is_market_brief_report_summary(report: dict) -> bool:
    report_id = str(report.get("id") or "").strip().upper()
    ticker = str(report.get("ticker") or "").strip().upper()
    return (
        report_id.startswith(MARKET_BRIEF_REPORT_ID_PREFIX)
        or ticker == MARKET_BRIEF_REPORT_TICKER
    )


def parse_complete_report_header(
    report_dir: Path,
) -> tuple[str | None, str | None, str | None]:
    complete = report_dir / "complete_report.md"
    if not complete.is_file():
        return None, None, None
    try:
        return parse_complete_report_header_text(complete.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None, None, None


def parse_complete_report_header_text(
    content: str,
) -> tuple[str | None, str | None, str | None]:
    return report_metadata.parse_complete_report_header_text(content)


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

    decision_card_path = artifacts_dir / "decision_card.json"
    if decision_card_path.is_file():
        summary = None
        try:
            payload = json.loads(decision_card_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                summary = payload.get("one_line_summary")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            summary = None

        results.append(
            {
                "type": "decision_card",
                "path": "artifacts/decision_card.json",
                "summary": summary,
            }
        )

    decision_delta_path = artifacts_dir / "decision_delta.json"
    if decision_delta_path.is_file():
        summary = None
        try:
            payload = json.loads(decision_delta_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                summary = payload.get("summary")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            summary = None

        results.append(
            {
                "type": "decision_delta",
                "path": "artifacts/decision_delta.json",
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

    premarket_brief_path = artifacts_dir / "premarket_brief.json"
    if premarket_brief_path.is_file():
        summary = None
        try:
            payload = json.loads(premarket_brief_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                summary = (
                    payload.get("summary")
                    or payload.get("executive_summary")
                    or payload.get("one_line_summary")
                )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            summary = None

        results.append(
            {
                "type": "premarket_brief",
                "path": "artifacts/premarket_brief.json",
                "summary": summary,
            }
        )

    search_evidence_path = artifacts_dir / "search_evidence.json"
    if search_evidence_path.is_file():
        summary = None
        try:
            payload = json.loads(search_evidence_path.read_text(encoding="utf-8"))
            calls = payload.get("calls") if isinstance(payload, dict) else []
            if isinstance(calls, list):
                result_count = sum(
                    len(call.get("results") or [])
                    for call in calls
                    if isinstance(call, dict)
                )
                summary = f"{len(calls)} web search call(s), {result_count} result(s)"
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            summary = None

        results.append(
            {
                "type": "search_evidence",
                "path": "artifacts/search_evidence.json",
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
    if not report_dir.is_dir() and storage_backend_is_remote():
        storage.download_prefix(f"reports/{report_id}", report_dir)
    if not report_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return report_dir


def resolve_report_dir_from_storage_path(storage_path: str) -> Path:
    report_dir = _resolve_report_storage_dir(storage_path)
    if not report_dir.is_dir() and storage_backend_is_remote():
        storage.download_prefix(f"reports/{storage_path}", report_dir)
    if not report_dir.is_dir():
        raise HTTPException(status_code=404, detail="Report not found")
    return report_dir


def _resolve_report_storage_dir(storage_path: str) -> Path:
    report_dir = (app_config.REPORTS_DIR / storage_path).resolve()
    try:
        report_dir.relative_to(app_config.REPORTS_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    return report_dir


def storage_backend_is_remote() -> bool:
    return storage.os.environ.get("STORAGE_BACKEND", "local").strip().lower() != "local"


def list_reports_from_storage(*, include_market_briefs: bool = False) -> list[dict]:
    report_ids: set[str] = set()
    for key in storage.get_storage().list("reports"):
        parts = key.split("/")
        if len(parts) >= 3 and parts[0] == "reports":
            report_ids.add(parts[1])

    results: list[dict] = []
    for report_id in sorted(report_ids):
        ticker = report_id
        date_str = None
        time_str = None
        try:
            content = storage.get_storage().get_text(
                f"reports/{report_id}/complete_report.md"
            )
            parsed_ticker, date_str, time_str = parse_complete_report_header_text(
                content
            )
            if parsed_ticker:
                ticker = parsed_ticker
        except Exception:
            pass
        summary = {
            "id": report_id,
            "ticker": ticker,
            "date": date_str,
            "time": time_str,
        }
        if include_market_briefs or not is_market_brief_report_summary(summary):
            results.append(summary)
    results.sort(key=lambda row: (row["date"] or "", row["time"] or ""), reverse=True)
    return results


def _require_report_user(db, request: Request | None) -> auth.User:
    if request is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    current_user = access.require_permission(
        db,
        request,
        auth.PERMISSION_ANALYSIS_READ,
    )
    assert current_user is not None
    return current_user


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


def list_reports(
    request: Request | None = None,
    *,
    include_market_briefs: bool = False,
) -> list[dict]:
    if auth.auth_enabled():
        try:
            with auth.db_session() as db:
                current_user = _require_report_user(db, request)
                owner_scope = access.owner_scope_for_user(current_user)
                records = report_metadata.list_report_runs(
                    db,
                    tenant_id=current_user.tenant_id,
                    owner_user_id=owner_scope,
                    include_workspace=owner_scope is not None,
                )
                results = [
                    report_metadata.serialize_report_summary(record)
                    for record in records
                ]
                if include_market_briefs:
                    return results
                return [
                    report
                    for report in results
                    if not is_market_brief_report_summary(report)
                ]
        except HTTPException:
            raise
        except Exception as exc:
            raise access.translate_auth_error(exc) from exc

    if not app_config.REPORTS_DIR.is_dir():
        if storage_backend_is_remote():
            return list_reports_from_storage(
                include_market_briefs=include_market_briefs
            )
        return []

    results = []
    for entry in app_config.REPORTS_DIR.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        report_id = entry.name
        ticker, date_str, time_str = parse_complete_report_header(entry)
        if ticker is None:
            ticker = report_id

        summary = {
            "id": report_id,
            "ticker": ticker,
            "date": date_str,
            "time": time_str,
        }
        if include_market_briefs or not is_market_brief_report_summary(summary):
            results.append(summary)

    results.sort(key=lambda row: (row["date"] or "", row["time"] or ""), reverse=True)
    return results


def get_structure(report_id: str, request: Request | None = None) -> dict:
    if auth.auth_enabled():
        try:
            with auth.db_session() as db:
                current_user = _require_report_user(db, request)
                owner_scope = access.owner_scope_for_user(current_user)
                record = report_metadata.get_report_run(
                    db,
                    report_id,
                    tenant_id=current_user.tenant_id,
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
                    **report_metadata.serialize_report_summary(record),
                    **structure,
                }
        except HTTPException:
            raise
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
    if auth.auth_enabled():
        try:
            with auth.db_session() as db:
                current_user = _require_report_user(db, request)
                owner_scope = access.owner_scope_for_user(current_user)
                record = report_metadata.get_report_run(
                    db,
                    report_id,
                    tenant_id=current_user.tenant_id,
                    owner_user_id=owner_scope,
                    include_workspace=owner_scope is not None,
                )
                report_metadata.get_report_file(
                    db,
                    report_id=record.id,
                    relative_path=path,
                )
                report_dir = resolve_report_dir_from_storage_path(record.storage_path)
        except HTTPException:
            raise
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
        logger.exception(
            "failed to read report file report_id=%s path=%s",
            report_id,
            path,
        )
        raise HTTPException(
            status_code=500, detail="Failed to read report file"
        ) from exc

    return {"content": content}


def update_report_visibility(
    report_id: str,
    visibility: str,
    request: Request | None = None,
) -> dict:
    if not auth.auth_enabled():
        raise HTTPException(status_code=409, detail="Auth is disabled")
    try:
        with auth.db_session() as db:
            current_user = _require_report_user(db, request)
            record = report_metadata.get_report_run(
                db,
                report_id,
                tenant_id=current_user.tenant_id,
            )
            is_owner = record.owner_user_id == current_user.id
            is_admin = access.is_admin_user(current_user)
            if not is_owner and not is_admin:
                raise auth.AuthPermissionError(
                    "Only owner or admin can update visibility"
                )

            old_visibility = record.visibility
            new_visibility = report_metadata._normalize_visibility(visibility)
            record.visibility = new_visibility
            record.visibility_updated_by_user_id = current_user.id
            record.visibility_updated_at = report_metadata._utcnow()
            record.visibility_admin_override = bool(is_admin and not is_owner)
            db.flush()
            audit.record_audit_event_safely(
                db,
                tenant_id=current_user.tenant_id,
                actor_user_id=current_user.id,
                action="report.visibility.updated",
                resource_type="report",
                resource_id=record.id,
                metadata={
                    "old_visibility": old_visibility,
                    "new_visibility": new_visibility,
                    "owner_user_id": record.owner_user_id,
                    "admin_override": record.visibility_admin_override,
                },
                request=request,
            )
            payload = report_metadata.serialize_report_summary(record)
            db.commit()
            return payload
    except HTTPException:
        raise
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc


def delete_report_artifacts(
    report_id: str,
    request: Request | None = None,
) -> dict:
    if not auth.auth_enabled():
        raise HTTPException(status_code=409, detail="Auth is disabled")
    try:
        with auth.db_session() as db:
            current_user = _require_report_user(db, request)
            if not access.is_admin_user(current_user):
                raise auth.AuthPermissionError("Only admin can delete reports")

            record = report_metadata.get_report_run(
                db,
                report_id,
                tenant_id=current_user.tenant_id,
            )
            payload = report_metadata.serialize_report_summary(record)
            if is_market_brief_report_summary(payload):
                raise auth.AuthPermissionError(
                    "Market brief reports cannot be deleted from the analysis library"
                )

            storage_path = record.storage_path
            report_dir = _resolve_report_storage_dir(storage_path)
            if report_dir.exists():
                if not report_dir.is_dir():
                    raise HTTPException(status_code=409, detail="Report path is invalid")
                shutil.rmtree(report_dir)
            deleted_storage_keys: list[str] = []
            if storage_backend_is_remote():
                deleted_storage_keys = storage.delete_prefix(f"reports/{storage_path}")

            audit.record_audit_event_safely(
                db,
                tenant_id=current_user.tenant_id,
                actor_user_id=current_user.id,
                action="report.deleted",
                resource_type="report",
                resource_id=record.id,
                metadata={
                    "ticker": record.ticker,
                    "owner_user_id": record.owner_user_id,
                    "visibility": record.visibility,
                    "storage_path": storage_path,
                },
                request=request,
            )
            db.query(report_metadata.ReportFile).filter(
                report_metadata.ReportFile.report_id == record.id
            ).delete(synchronize_session=False)
            db.delete(record)
            db.commit()
            return {
                "deleted": True,
                "report_id": report_id,
                "storage_path": storage_path,
                "deleted_storage_keys": len(deleted_storage_keys),
            }
    except HTTPException:
        raise
    except Exception as exc:
        raise access.translate_auth_error(exc) from exc
