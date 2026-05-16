from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Request

from diverge.market_brief.schema import PremarketBrief
from diverge.market_brief.storage import save_market_brief_report
from web.backend import app_config, auth, report_metadata, storage
from web.backend.services import reports as report_service


MARKET_BRIEF_ARTIFACT_PATH = "artifacts/premarket_brief.json"
MARKET_BRIEF_RETENTION_DAYS = 7
MARKET_BRIEF_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _today_in_market_timezone() -> date:
    return datetime.now(MARKET_BRIEF_TIMEZONE).date()


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None

    candidate = value.strip()
    if not candidate:
        return None

    for pattern in ("%Y-%m-%d", "%Y%m%d"):
        try:
            source = candidate[:10] if pattern == "%Y-%m-%d" else candidate[:8]
            return datetime.strptime(source, pattern).date()
        except ValueError:
            continue

    match = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", candidate)
    if not match:
        return None

    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _string_value(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _string_list(value: Any, *, limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []

    results: list[str] = []
    for item in value:
        text = _string_value(item)
        if text is None and isinstance(item, dict):
            for key in ("title", "name", "theme", "signal", "risk", "summary"):
                text = _string_value(item.get(key))
                if text:
                    break
        if text:
            results.append(text)
        if len(results) >= limit:
            break
    return results


def _first_string(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _string_value(payload.get(key))
        if value:
            return value
    return None


def _source_count(payload: dict[str, Any]) -> int:
    for key in ("sources", "citations", "source_links"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


def _report_date(
    report: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> date | None:
    for value in (report.get("date"), report.get("id")):
        parsed = _parse_date(value)
        if parsed:
            return parsed

    if payload:
        for key in (
            "trading_day",
            "generated_at",
            "information_cutoff_at",
            "brief_id",
        ):
            parsed = _parse_date(payload.get(key))
            if parsed:
                return parsed
    return None


def _brief_summary_from_payload(
    report: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    brief_date = _report_date(report, payload)
    if brief_date is None:
        return None

    markets = _string_list(payload.get("markets"), limit=4)
    main_themes = _string_list(payload.get("main_themes"), limit=4)
    risks = _string_list(payload.get("risks"), limit=4)
    validation_signals = _string_list(
        payload.get("opening_validation_signals"), limit=4
    )
    quality_warnings = _string_list(payload.get("quality_warnings"), limit=4)
    summary = _first_string(
        payload,
        ("summary", "executive_summary", "one_line_summary", "overview"),
    )
    if summary is None and main_themes:
        summary = " / ".join(main_themes[:2])

    return {
        "type": "premarket_brief",
        "report_id": report.get("id"),
        "brief_id": _first_string(payload, ("brief_id",)) or report.get("id"),
        "date": brief_date.isoformat(),
        "time": report.get("time"),
        "title": _first_string(payload, ("title", "headline", "brief_title"))
        or "Premarket Brief",
        "summary": summary,
        "markets": markets,
        "trading_day": _first_string(payload, ("trading_day",)),
        "generated_at": _first_string(payload, ("generated_at",)),
        "information_cutoff_at": _first_string(payload, ("information_cutoff_at",)),
        "data_quality_level": _first_string(payload, ("data_quality_level",)),
        "main_themes": main_themes,
        "risks": risks,
        "opening_validation_signals": validation_signals,
        "quality_warnings": quality_warnings,
        "source_count": _source_count(payload),
        "artifact_path": MARKET_BRIEF_ARTIFACT_PATH,
    }


def _load_market_brief_payload(
    report_id: str,
    request: Request | None,
) -> dict[str, Any] | None:
    try:
        structure = report_service.get_structure(report_id, request)
    except Exception:
        return None

    artifacts = structure.get("artifacts") if isinstance(structure, dict) else None
    if not isinstance(artifacts, list):
        return None

    has_market_brief = any(
        isinstance(artifact, dict)
        and artifact.get("path") == MARKET_BRIEF_ARTIFACT_PATH
        for artifact in artifacts
    )
    if not has_market_brief:
        return None

    try:
        content = report_service.get_content(
            report_id,
            MARKET_BRIEF_ARTIFACT_PATH,
            request,
        )
    except Exception:
        return None

    raw_content = content.get("content") if isinstance(content, dict) else None
    if not isinstance(raw_content, str):
        return None

    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def list_market_briefs(
    request: Request | None = None,
    *,
    today: date | None = None,
    retention_days: int = MARKET_BRIEF_RETENTION_DAYS,
) -> dict[str, Any]:
    current_day = today or _today_in_market_timezone()
    cutoff_day = current_day - timedelta(days=max(retention_days, 1) - 1)
    summaries: list[dict[str, Any]] = []

    for report in report_service.list_reports(request, include_market_briefs=True):
        if not isinstance(report, dict):
            continue

        report_id = _string_value(report.get("id"))
        if not report_id:
            continue

        report_day = _report_date(report)
        if report_day and report_day < cutoff_day:
            continue

        payload = _load_market_brief_payload(report_id, request)
        if payload is None:
            continue

        summary = _brief_summary_from_payload(report, payload)
        if summary is None:
            continue
        summary_day = _parse_date(summary["date"])
        if summary_day is None or summary_day < cutoff_day:
            continue
        summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            item.get("date") or "",
            item.get("time") or "",
            item.get("report_id") or "",
        ),
        reverse=True,
    )

    return {
        "retention_days": retention_days,
        "today": current_day.isoformat(),
        "cutoff_date": cutoff_day.isoformat(),
        "latest": summaries[0] if summaries else None,
        "briefs": summaries,
    }


def publish_market_brief(
    brief: PremarketBrief,
    *,
    owner_user_id: str | None,
    tenant_id: str | None,
    report_visibility: str,
) -> dict[str, Any]:
    result = save_market_brief_report(
        brief,
        reports_dir=app_config.REPORTS_DIR,
        tmp_reports_dir=app_config.tmp_reports_dir(),
    )

    if auth.auth_enabled() and owner_user_id:
        metadata_payload = report_metadata.build_report_metadata(
            result.report_dir,
            report_id=result.report_id,
        )
        file_entries = report_metadata.build_report_file_index(result.report_dir)
        with auth.db_session() as db:
            report_metadata.upsert_report_run(
                db,
                report_id=result.report_id,
                owner_user_id=owner_user_id,
                tenant_id=tenant_id,
                visibility=report_visibility,
                ticker=str(metadata_payload["ticker"] or "MARKET_BRIEF"),
                generated_at=metadata_payload["generated_at"],
                storage_path=str(metadata_payload["storage_path"] or result.report_id),
                file_entries=file_entries,
            )

    if report_service.storage_backend_is_remote():
        storage.upload_directory(result.report_dir, f"reports/{result.report_id}")

    return {
        "report_id": result.report_id,
        "report_dir": str(result.report_dir),
        "artifact_path": "artifacts/premarket_brief.json",
        "markets": list(brief.markets),
        "trading_day": brief.trading_day,
        "data_quality_level": brief.data_quality_level,
        "source_count": len(brief.sources),
        "quality_warnings": list(brief.quality_warnings),
    }
