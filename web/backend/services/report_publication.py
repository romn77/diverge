from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from diverge.common.json_io import write_json_atomic
from diverge.decision_card.builder import (
    build_decision_card as default_build_decision_card,
    build_fallback_decision_card as default_build_fallback_decision_card,
)
from diverge.decision_card.delta import (
    build_decision_delta,
    find_previous_decision_card,
    save_decision_delta,
)
from diverge.decision_card.storage import (
    save_decision_card as default_save_decision_card,
)
from diverge.research.search.evidence import build_search_evidence_artifact
from diverge.research.search.session import search_sessions
from diverge.runner import (
    AnalysisRequest,
    save_report_to_disk as default_save_report_to_disk,
)
from web.backend import access, app_config, auth, report_metadata, storage

logger = logging.getLogger(__name__)


SaveReportToDisk = Callable[[Any, str, Path], object]
BuildDecisionCard = Callable[..., Any]
SaveDecisionCard = Callable[[Any, Path], object]
WriteSearchEvidence = Callable[[str, Path], Path | None]
WriteDecisionDelta = Callable[..., None]
CheckCanceled = Callable[[], None]
Now = Callable[[], datetime]
UploadDirectory = Callable[[Path, str], object]


def _noop() -> None:
    return None


def storage_backend_is_remote() -> bool:
    return os.environ.get("STORAGE_BACKEND", "local").strip().lower() != "local"


def report_output_dir(report_id: str) -> Path:
    reports_root = app_config.REPORTS_DIR.resolve()
    report_dir = (app_config.REPORTS_DIR / report_id).resolve()
    try:
        report_dir.relative_to(reports_root)
    except ValueError as exc:
        raise ValueError(
            "Report output directory must remain inside the reports root"
        ) from exc
    return report_dir


def _local_previous_report_dirs(
    *,
    owner_user_id: str | None,
    tenant_id: str | None,
    current_report_id: str,
) -> list[Path]:
    if not app_config.REPORTS_DIR.is_dir():
        return []

    if auth.auth_enabled() and owner_user_id:
        try:
            with auth.db_session() as db:
                user = db.get(auth.User, owner_user_id)
                owner_scope = access.owner_scope_for_user(user)
                records = report_metadata.list_report_runs(
                    db,
                    tenant_id=tenant_id,
                    owner_user_id=owner_scope,
                    include_workspace=owner_scope is not None,
                )
        except Exception:
            logger.exception(
                "Failed to list previous report metadata for decision delta."
            )
            return []

        report_dirs = []
        for record in records:
            if record.id == current_report_id:
                continue
            report_dir = app_config.REPORTS_DIR / record.storage_path
            if report_dir.is_dir():
                report_dirs.append(report_dir)
        return report_dirs

    return [
        path
        for path in app_config.REPORTS_DIR.iterdir()
        if path.is_dir()
        and not path.name.startswith(".")
        and path.name != current_report_id
    ]


def write_decision_delta_if_available(
    *,
    owner_user_id: str | None,
    tenant_id: str | None,
    current_report_id: str,
    current_report_dir: Path,
    decision_card: Any,
    output_language: str,
) -> None:
    try:
        previous_card = find_previous_decision_card(
            current_card=decision_card,
            candidate_report_dirs=_local_previous_report_dirs(
                owner_user_id=owner_user_id,
                tenant_id=tenant_id,
                current_report_id=current_report_id,
            ),
            current_report_id=current_report_id,
        )
        if previous_card is None:
            return
        delta = build_decision_delta(
            current_card=decision_card,
            previous_card=previous_card,
            current_report_id=current_report_id,
            output_language=output_language,
        )
        save_decision_delta(delta, current_report_dir)
    except Exception:
        logger.exception("Failed to build decision delta for %s", current_report_id)


def write_search_evidence_artifact(task_id: str, report_dir: Path) -> Path | None:
    session = search_sessions.get(task_id)
    if session is None:
        return None
    artifact = build_search_evidence_artifact(session)
    if artifact is None:
        return None
    artifact_path = report_dir / "artifacts" / "search_evidence.json"
    write_json_atomic(artifact_path, artifact)
    return artifact_path


def _raw_signal_from_final_state(final_state: Any) -> str | None:
    if not isinstance(final_state, Mapping):
        return None
    raw_signal = final_state.get("final_trade_decision")
    return raw_signal if isinstance(raw_signal, str) else None


def _report_id_for_request(request: AnalysisRequest, now: Now) -> str:
    timestamp = now().strftime("%H%M%S")
    analysis_date = str(request.analysis_date).replace("-", "")
    return f"{request.ticker}_{analysis_date}_{timestamp}"


@dataclass(frozen=True)
class ReportPublicationRequest:
    task_id: str
    request: AnalysisRequest
    final_state: Any
    temp_dir: Path
    owner_user_id: str | None
    tenant_id: str | None
    report_visibility: str


@dataclass(frozen=True)
class ReportPublicationResult:
    report_id: str
    report_dir: Path


@dataclass(frozen=True)
class ReportPublicationAdapters:
    save_report_to_disk: SaveReportToDisk = default_save_report_to_disk
    build_decision_card: BuildDecisionCard = default_build_decision_card
    build_fallback_decision_card: BuildDecisionCard = (
        default_build_fallback_decision_card
    )
    save_decision_card: SaveDecisionCard = default_save_decision_card
    write_search_evidence: WriteSearchEvidence = write_search_evidence_artifact
    write_decision_delta: WriteDecisionDelta = write_decision_delta_if_available
    storage_backend_is_remote: Callable[[], bool] = storage_backend_is_remote
    upload_directory: UploadDirectory = storage.upload_directory
    check_canceled: CheckCanceled = _noop
    now: Now = datetime.now


def publish_analysis_report(
    publication: ReportPublicationRequest,
    *,
    adapters: ReportPublicationAdapters | None = None,
) -> ReportPublicationResult:
    resolved_adapters = adapters or ReportPublicationAdapters()
    request = publication.request
    report_id = _report_id_for_request(request, resolved_adapters.now)

    resolved_adapters.check_canceled()
    resolved_adapters.save_report_to_disk(
        publication.final_state,
        request.ticker,
        publication.temp_dir,
    )

    resolved_adapters.check_canceled()
    resolved_adapters.write_search_evidence(
        publication.task_id,
        publication.temp_dir,
    )
    try:
        decision_card = resolved_adapters.build_decision_card(
            final_state=publication.final_state,
            symbol=request.ticker,
            report_id=report_id,
            analysis_date=str(request.analysis_date),
            output_language=request.output_language,
        )
        resolved_adapters.save_decision_card(decision_card, publication.temp_dir)
        resolved_adapters.write_decision_delta(
            owner_user_id=publication.owner_user_id,
            tenant_id=publication.tenant_id,
            current_report_id=report_id,
            current_report_dir=publication.temp_dir,
            decision_card=decision_card,
            output_language=request.output_language,
        )
    except Exception as exc:
        logger.exception("Failed to build decision card for %s", report_id)
        fallback_card = resolved_adapters.build_fallback_decision_card(
            symbol=request.ticker,
            report_id=report_id,
            analysis_date=str(request.analysis_date),
            raw_signal=_raw_signal_from_final_state(publication.final_state),
            error=str(exc),
            output_language=request.output_language,
        )
        resolved_adapters.save_decision_card(fallback_card, publication.temp_dir)

    resolved_adapters.check_canceled()
    app_config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    final_report_dir = report_output_dir(report_id)
    publication.temp_dir.replace(final_report_dir)

    if auth.auth_enabled() and publication.owner_user_id:
        metadata_payload = report_metadata.build_report_metadata(
            final_report_dir,
            report_id=report_id,
        )
        file_entries = report_metadata.build_report_file_index(final_report_dir)
        with auth.db_session() as db:
            report_metadata.upsert_report_run(
                db,
                report_id=report_id,
                owner_user_id=publication.owner_user_id,
                tenant_id=publication.tenant_id,
                visibility=publication.report_visibility,
                ticker=str(metadata_payload["ticker"] or request.ticker),
                generated_at=metadata_payload["generated_at"],
                storage_path=str(metadata_payload["storage_path"] or report_id),
                file_entries=file_entries,
            )

    if resolved_adapters.storage_backend_is_remote():
        resolved_adapters.upload_directory(final_report_dir, f"reports/{report_id}")

    return ReportPublicationResult(report_id=report_id, report_dir=final_report_dir)
