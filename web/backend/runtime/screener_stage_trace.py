from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from web.backend.runtime import task_lifecycle

SCREENER_STAGES = ("Features", "Filters", "Ranking", "Export")


AppendProgress = Callable[[dict[str, Any]], None]
CheckCanceled = Callable[[], None]


def normalize_stage(stage: str) -> str:
    normalized = str(stage or "").strip().lower()
    if normalized == "features":
        return "Features"
    if normalized == "filters":
        return "Filters"
    if normalized == "ranking":
        return "Ranking"
    if normalized == "export":
        return "Export"
    return str(stage or "")


def _empty_stage_status() -> dict[str, str]:
    return {key: "not_started" for key in SCREENER_STAGES}


def _stage_status_for(status: str, stage: str) -> dict[str, str]:
    if stage in SCREENER_STAGES:
        stage_index = SCREENER_STAGES.index(stage)
        stage_status = {
            key: (
                "processing"
                if key == stage
                else "completed"
                if SCREENER_STAGES.index(key) < stage_index
                else "not_started"
            )
            for key in SCREENER_STAGES
        }
    else:
        stage_status = _empty_stage_status()
    if status == "completed":
        return {key: "completed" for key in SCREENER_STAGES}
    if status in {"queued", "canceled"}:
        return _empty_stage_status()
    if status == "failed" and stage not in SCREENER_STAGES:
        return _empty_stage_status()
    return stage_status


def progress_event(
    *,
    status: str,
    stage: str,
    current: int,
    total: int,
    symbol: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    normalized_stage = normalize_stage(stage)
    detail = message or f"{normalized_stage} {current}/{total}"
    if symbol:
        detail = f"{detail} {symbol}"

    return {
        "timestamp": task_lifecycle.event_timestamp(),
        "status": status,
        "stage_status": _stage_status_for(status, normalized_stage),
        "agent_status": {},
        "current_agent": symbol,
        "message": detail,
    }


def _terminal_stage_status(latest_progress: Mapping[str, Any]) -> dict[str, str]:
    latest_stage_status = latest_progress.get("stage_status") or {}
    return {
        key: (
            "not_started"
            if latest_stage_status.get(key) == "processing"
            else latest_stage_status.get(key, "not_started")
        )
        for key in SCREENER_STAGES
    }


def failure_progress(
    latest_progress: Mapping[str, Any] | None,
    error: str,
) -> dict[str, Any]:
    latest = latest_progress or {}
    return {
        "timestamp": task_lifecycle.event_timestamp(),
        "status": "failed",
        "stage_status": _terminal_stage_status(latest),
        "agent_status": latest.get("agent_status") or {},
        "current_agent": latest.get("current_agent"),
        "message": f"System: {error}",
    }


def canceled_progress(
    latest_progress: Mapping[str, Any] | None,
    message: str | None = None,
) -> dict[str, Any]:
    latest = latest_progress or {}
    return {
        "timestamp": task_lifecycle.event_timestamp(),
        "status": "canceled",
        "stage_status": _terminal_stage_status(latest),
        "agent_status": latest.get("agent_status") or {},
        "current_agent": latest.get("current_agent"),
        "message": message or "Screener task canceled by request.",
    }


def cancel_requested_progress(
    latest_progress: Mapping[str, Any] | None,
) -> dict[str, Any]:
    latest = latest_progress or {}
    return {
        "timestamp": task_lifecycle.event_timestamp(),
        "status": "running",
        "stage_status": latest.get("stage_status") or _empty_stage_status(),
        "agent_status": latest.get("agent_status") or {},
        "current_agent": latest.get("current_agent"),
        "message": "Termination requested. Work will stop at the next safe step.",
    }


def waiting_for_quota_progress(
    latest_progress: Mapping[str, Any] | None,
    *,
    vendor: str,
    blocked_until: str | None,
) -> dict[str, Any]:
    latest = latest_progress or {}
    return {
        "timestamp": task_lifecycle.event_timestamp(),
        "status": "waiting_for_quota",
        "stage_status": latest.get("stage_status") or _empty_stage_status(),
        "agent_status": latest.get("agent_status") or {},
        "current_agent": latest.get("current_agent"),
        "message": (
            f"Waiting for {vendor} quota"
            + (f" until {blocked_until}" if blocked_until else "")
            + "."
        ),
    }


def pipeline_message(
    *,
    stage: str,
    current: int,
    total: int,
    symbol: str | None = None,
    status: str | None = None,
    detail: str | None = None,
) -> str:
    message = f"{stage} {current}/{total}"
    if symbol:
        message = f"{message} {symbol}"
    if status:
        message = f"{message} [{status}]"
    if detail:
        message = f"{message} {detail}"
    return message


@dataclass(frozen=True)
class ScreenerStageTrace:
    append_progress: AppendProgress
    check_canceled: CheckCanceled

    def pipeline_callback(
        self,
        stage: str,
        current: int,
        total: int,
        symbol: str | None = None,
        *,
        status: str | None = None,
        detail: str | None = None,
    ) -> None:
        normalized_stage = normalize_stage(stage)
        if normalized_stage not in SCREENER_STAGES:
            return
        self.append_progress(
            progress_event(
                status="running",
                stage=normalized_stage,
                current=current,
                total=total,
                symbol=symbol,
                message=pipeline_message(
                    stage=normalized_stage,
                    current=current,
                    total=total,
                    symbol=symbol,
                    status=status,
                    detail=detail,
                ),
            )
        )
        self.check_canceled()

    def emit_preflight(self) -> None:
        self.append_progress(
            progress_event(
                status="running",
                stage="Features",
                current=0,
                total=1,
                message="Checking cached screener data.",
            )
        )
        self.check_canceled()

    def completion_progress(self, run_id: str) -> dict[str, Any]:
        return progress_event(
            status="completed",
            stage="Export",
            current=1,
            total=1,
            message=f"Export 1/1 {run_id}",
        )
