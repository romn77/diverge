"""
TradingAgents Report Viewer backend.

Endpoints:
  GET  /api/healthz
  GET  /api/auth/me
  POST /api/auth/login
  POST /api/auth/logout
  POST /api/auth/change-password
  GET  /api/admin/users
  GET  /api/admin/users/{user_id}
  POST /api/admin/users
  PUT  /api/admin/users/{user_id}
  DELETE /api/admin/users/{user_id}
  POST /api/admin/users/{user_id}/reset-password
  GET  /api/reports
  GET  /api/reports/{report_id}/structure
  GET  /api/reports/{report_id}/content?path=...
  GET  /api/trades
  POST /api/trades
  GET  /api/trades/{trade_id}
  PUT  /api/trades/{trade_id}
  GET  /api/trades/{trade_id}/reviews
  POST /api/trades/{trade_id}/reviews
  PUT  /api/trades/{trade_id}/reviews/{review_type}
  GET  /api/trade-feedback/{ticker}
  POST /api/tasks
  GET  /api/tasks
  GET  /api/tasks/{task_id}
  GET  /api/tasks/{task_id}/stream
  GET  /api/config/options
"""

import asyncio
import json
import logging
import os
import re
import shutil
import sys
import threading
import uuid
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from dotenv import dotenv_values, load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(PROJECT_ENV_FILE)  # Load project .env if present
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from cli.utils import ANALYST_ORDER
from tradingagents.llm_clients.model_config import (
    DEEP_MODEL_OPTIONS,
    PROVIDER_OPTIONS,
    QUICK_MODEL_OPTIONS,
)
from tradingagents.screener.pipeline import run_screen
from tradingagents.screener.schema import ScreenRunConfig
from tradingagents.runner import AnalysisProgress, AnalysisRequest, run_analysis_streaming, save_report_to_disk
from tradingagents.trade_feedback import (
    create_trade_record as create_trade_record_file,
    generate_trade_review as generate_trade_review_file,
    get_trade_feedback_payload as get_trade_feedback_payload_file,
    get_trade_record as get_trade_record_file,
    list_trade_records as list_trade_records_file,
    list_trade_reviews as list_trade_reviews_file,
    save_trade_review as save_trade_review_file,
    update_trade_record as update_trade_record_file,
)
from web.backend import auth, report_metadata, screener_runs, trade_entries

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPORTS_DIR = Path(os.environ.get("REPORTS_DIR", PROJECT_ROOT / "reports")).resolve()
TMP_REPORTS_DIR = REPORTS_DIR / ".tmp"
SCREENER_RESULTS_DIR = Path(
    os.environ.get("SCREENER_RESULTS_DIR", PROJECT_ROOT / "results" / "screener")
).resolve()
TASKS_STATE_DIRNAME = ".tasks"
SCREENER_TASKS_STATE_DIRNAME = ".screener_tasks"
ACTIVE_TASKS_DIRNAME = "active"
RECOVERED_TASK_ERROR = "Service restarted before task completion."

CATEGORY_DIR_MAP: dict[str, str] = {
    "analysts": "1_analysts",
    "research": "2_research",
    "trading": "3_trading",
    "risk": "4_risk",
    "portfolio": "5_portfolio",
}
RESEARCH_DEPTH_OPTIONS = [
    {
        "label": "Shallow",
        "value": 1,
        "description": "Quick research with minimal debate rounds",
    },
    {
        "label": "Medium",
        "value": 3,
        "description": "Balanced debate depth and strategy discussion",
    },
    {
        "label": "Deep",
        "value": 5,
        "description": "Comprehensive debate and risk discussion",
    },
]
OUTPUT_LANGUAGE_OPTIONS = [
    {"label": "English (en)", "value": "en"},
    {"label": "简体中文 (cn)", "value": "cn"},
]
OPENAI_REASONING_OPTIONS = [
    {"label": "Medium", "value": "medium"},
    {"label": "High", "value": "high"},
    {"label": "Low", "value": "low"},
]
GOOGLE_THINKING_OPTIONS = [
    {"label": "Enable Thinking", "value": "high"},
    {"label": "Minimal Thinking", "value": "minimal"},
]
TERMINAL_TASK_STATUSES = {"completed", "failed"}
SCREENER_ARTIFACT_FILENAMES = {
    "run_meta": "run_meta.json",
    "universe": "universe.csv",
    "features": "features.csv",
    "filtered_out": "filtered_out.csv",
    "candidates": "candidates.csv",
    "llm_pool": "llm_pool.json",
}
PROVIDER_API_KEY_ENV_VARS: dict[str, str | None] = {
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "xai": "XAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "ollama": None,
    "xiaohumini": "XIAOHUMINI_API_KEY",
}

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TaskCreatePayload(BaseModel):
    ticker: str
    analysis_date: str
    analysts: list[str]
    research_depth: int
    llm_provider: str
    quick_think_llm: str
    deep_think_llm: str
    output_language: str
    google_thinking_level: Optional[str] = None
    openai_reasoning_effort: Optional[str] = None


class AnalysisReferencePayload(BaseModel):
    analysis_date: str
    report_path: str
    full_state_log_path: str


class TradeRecordCreatePayload(BaseModel):
    ticker: str
    exchange_or_market: str
    side: str
    status: str
    entry_timestamp: Optional[str] = None
    entry_price: Optional[float] = None
    exit_timestamp: Optional[str] = None
    exit_price: Optional[float] = None
    size: Optional[float] = None
    initial_thesis: str
    planned_horizon: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: str = ""
    analysis_references: list[AnalysisReferencePayload] = Field(default_factory=list)


class TradeRecordUpdatePayload(BaseModel):
    ticker: Optional[str] = None
    exchange_or_market: Optional[str] = None
    side: Optional[str] = None
    status: Optional[str] = None
    entry_timestamp: Optional[str] = None
    entry_price: Optional[float] = None
    exit_timestamp: Optional[str] = None
    exit_price: Optional[float] = None
    size: Optional[float] = None
    initial_thesis: Optional[str] = None
    planned_horizon: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: Optional[str] = None
    analysis_references: Optional[list[AnalysisReferencePayload]] = None


class TradeReviewCreatePayload(BaseModel):
    review_type: str
    llm_provider: str
    model: str
    output_language: str = "en"
    google_thinking_level: Optional[str] = None
    openai_reasoning_effort: Optional[str] = None
    analysis_date: Optional[str] = None
    analysis_references: Optional[list[AnalysisReferencePayload]] = None


class TradeReviewSavePayload(BaseModel):
    thesis_assessment: str
    timing_assessment: str
    sizing_assessment: str
    discipline_assessment: str
    outcome_summary: str
    improvement_actions: str | list[str]
    ticker_specific_lessons: str | list[str]
    cross_ticker_tags: str | list[str]
    analysis_date: Optional[str] = None
    analysis_references: Optional[list[AnalysisReferencePayload]] = None


class ScreenTaskCreatePayload(BaseModel):
    markets: list[str]
    as_of_date: str
    top_k: int
    cn_data_source: str = "tushare"
    breakout_types: list[str] = Field(default_factory=list)


class LoginPayload(BaseModel):
    email: str
    password: str


class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str


class AdminUserCreatePayload(BaseModel):
    email: str
    display_name: str
    password: str
    role: auth.UserRole = auth.UserRole.VIEWER
    status: auth.UserStatus = auth.UserStatus.ACTIVE
    must_change_password: bool = True


class AdminUserUpdatePayload(BaseModel):
    display_name: Optional[str] = None
    role: Optional[auth.UserRole] = None
    status: Optional[auth.UserStatus] = None
    must_change_password: Optional[bool] = None


class AdminUserResetPasswordPayload(BaseModel):
    new_password: str
    must_change_password: bool = True


@dataclass
class Task:
    id: str
    request: AnalysisRequest
    owner_user_id: Optional[str] = None
    status: str = "pending"
    latest_progress: Optional[dict] = None
    progress_events: list[dict] = field(default_factory=list)
    report_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticker": self.request.ticker,
            "analysis_date": self.request.analysis_date,
            "analysts": list(self.request.analysts),
            "request_payload": asdict(self.request),
            "owner_user_id": self.owner_user_id,
            "status": self.status,
            "latest_progress": self.latest_progress,
            "report_id": self.report_id,
            "error": self.error,
        }


@dataclass
class ScreenerTask:
    id: str
    request_payload: dict
    config_payload: dict
    owner_user_id: Optional[str] = None
    status: str = "pending"
    latest_progress: Optional[dict] = None
    progress_events: list[dict] = field(default_factory=list)
    run_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "request_payload": self.request_payload,
            "config_payload": self.config_payload,
            "owner_user_id": self.owner_user_id,
            "status": self.status,
            "latest_progress": self.latest_progress,
            "progress_events": self.progress_events,
            "run_id": self.run_id,
            "error": self.error,
        }


tasks: dict[str, Task] = {}
screener_tasks: dict[str, ScreenerTask] = {}
tasks_lock = threading.Lock()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


def _get_frontend_origins() -> list[str]:
    raw_value = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
    origins = [origin.strip() for origin in raw_value.split(",") if origin.strip()]
    return origins or ["http://localhost:3000"]


@asynccontextmanager
async def _app_lifespan(_: FastAPI):
    auth.initialize_auth_runtime()
    report_metadata.initialize_report_metadata_runtime()
    screener_runs.initialize_screener_runtime()
    trade_entries.initialize_trade_entries_runtime()
    _restore_persisted_active_tasks()
    _restore_persisted_screener_tasks()
    yield


app = FastAPI(
    title="TradingAgents Report Viewer",
    version="1.1.0",
    lifespan=_app_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH_API_DEPENDENCIES = [Depends(auth.enforce_authenticated_api_access)]
ADMIN_API_DEPENDENCIES = [Depends(auth.enforce_admin_api_access)]
SCREENER_API_DEPENDENCIES = [Depends(auth.enforce_operator_api_access)]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_complete_report_header(
    report_dir: Path,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    complete = report_dir / "complete_report.md"
    if not complete.is_file():
        return None, None, None

    try:
        with complete.open(encoding="utf-8") as file_handle:
            lines = [file_handle.readline() for _ in range(4)]

        ticker: Optional[str] = None
        date_str: Optional[str] = None
        time_str: Optional[str] = None

        ticker_match = re.match(r"^#\s+Trading Analysis Report:\s+(\S+)", lines[0])
        if ticker_match:
            ticker = ticker_match.group(1).strip()

        for line in lines[1:]:
            generated_match = re.match(
                r"^Generated:\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})", line
            )
            if generated_match:
                date_str = generated_match.group(1)
                time_str = generated_match.group(2)
                break

        return ticker, date_str, time_str
    except (OSError, UnicodeDecodeError):
        return None, None, None


def _scan_categories(report_dir: Path) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {}
    for key, dir_name in CATEGORY_DIR_MAP.items():
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


def _scan_artifacts(report_dir: Path) -> list[dict]:
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

    trade_feedback_path = artifacts_dir / "trade_feedback.json"
    if trade_feedback_path.is_file():
        summary = None
        try:
            payload = json.loads(trade_feedback_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                review_count = len(payload.get("reviews") or [])
                summary = f"{review_count} historical review(s)" if review_count else "Historical feedback prompt"
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


def _resolve_report_dir(report_id: str) -> Path:
    if report_id.startswith("."):
        raise HTTPException(status_code=404, detail="Report not found")
    if "/" in report_id or "\\" in report_id or ".." in report_id:
        raise HTTPException(status_code=404, detail="Report not found")

    report_dir = REPORTS_DIR / report_id
    if not report_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return report_dir


def _resolve_report_dir_from_storage_path(storage_path: str) -> Path:
    report_dir = (REPORTS_DIR / storage_path).resolve()
    try:
        report_dir.relative_to(REPORTS_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    if not report_dir.is_dir():
        raise HTTPException(status_code=404, detail="Report not found")
    return report_dir


def _build_report_structure_from_index(
    report_dir: Path,
    file_entries: list[report_metadata.ReportFile],
) -> dict:
    categories: dict[str, list[str]] = {}
    artifacts: list[dict] = []
    has_complete = False
    disk_artifacts = {
        artifact["path"]: artifact for artifact in _scan_artifacts(report_dir)
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


def _translate_trade_feedback_error(exc: Exception) -> HTTPException:
    detail = str(exc)
    status_code = 404 if "not found" in detail.lower() else 400
    return HTTPException(status_code=status_code, detail=detail)


def _translate_auth_error(exc: Exception) -> HTTPException:
    if isinstance(exc, auth.AuthNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, auth.AuthConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, auth.AuthPermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, auth.AuthDisabledError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, auth.AuthValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


def _require_trade_request_user(db, request: Request | None) -> auth.User | None:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        return None
    if request is None:
        raise HTTPException(status_code=500, detail="Trade request context is missing")

    user = auth.get_request_user(db, request, settings=settings)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _sync_trade_entry_metadata(db, record: dict, owner_user_id: str) -> None:
    reviews = list_trade_reviews_file(record["trade_id"], reports_dir=REPORTS_DIR)
    trade_entries.upsert_trade_entry(
        db,
        record,
        owner_user_id=owner_user_id,
        reports_dir=REPORTS_DIR,
        reviews=reviews,
    )


def _load_owner_scoped_trade_records(
    db,
    owner_user_id: str,
    *,
    ticker: str | None = None,
) -> list[dict]:
    records: list[dict] = []
    for entry in trade_entries.list_trade_entries_for_owner(
        db,
        owner_user_id,
        ticker=ticker,
    ):
        try:
            records.append(get_trade_record_file(entry.trade_id, reports_dir=REPORTS_DIR))
        except ValueError:
            continue
    return records


def _resolve_task_owner_user_id(request: Request | None) -> str | None:
    settings = auth.get_auth_settings()
    if not settings.enabled or request is None:
        return None

    with auth.db_session() as db:
        user = auth.get_request_user(db, request, settings=settings)
        return user.id if user is not None else None


def _visible_trade_ids_for_task(task: Task) -> set[str] | None:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        return None
    if not task.owner_user_id:
        return set()

    with auth.db_session() as db:
        return trade_entries.list_visible_trade_ids(
            db,
            task.owner_user_id,
            ticker=task.request.ticker,
        )


def _require_screener_user(request: Request | None) -> auth.User | None:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        return None
    if request is None:
        raise HTTPException(status_code=500, detail="Request context is required")
    with auth.db_session() as db:
        return auth.require_request_user_role(
            db,
            request,
            (auth.UserRole.ADMIN.value, auth.UserRole.OPERATOR.value),
        )


def _is_admin_user(user: auth.User | None) -> bool:
    return user is not None and user.role == auth.UserRole.ADMIN.value


def _owner_scope_for_user(user: auth.User | None) -> str | None:
    if user is None or _is_admin_user(user):
        return None
    return user.id


def _can_access_screener_owner(user: auth.User | None, owner_user_id: str | None) -> bool:
    if user is None:
        return True
    if _is_admin_user(user):
        return True
    return owner_user_id is not None and owner_user_id == user.id


def _relative_screener_storage_path(path: Path) -> str:
    resolved_root = SCREENER_RESULTS_DIR.resolve()
    resolved_path = path.resolve()
    try:
        relative_path = resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError("Screener artifacts must stay under SCREENER_RESULTS_DIR") from exc
    return relative_path.as_posix()


def _build_screener_artifact_manifest(run_dir: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for artifact_key, filename in SCREENER_ARTIFACT_FILENAMES.items():
        artifact_path = run_dir / filename
        if artifact_path.is_file():
            manifest[artifact_key] = _relative_screener_storage_path(artifact_path)
    return manifest


def _resolve_screener_run_dir_from_record(record: screener_runs.ScreenerRun) -> Path:
    run_dir = (SCREENER_RESULTS_DIR / record.storage_path).resolve()
    try:
        run_dir.relative_to(SCREENER_RESULTS_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Screener run not found") from exc
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Screener run '{record.id}' not found")
    return run_dir


def _resolve_screener_artifact_path(
    record: screener_runs.ScreenerRun,
    artifact_key: str,
    default_filename: str,
) -> Path:
    relative_path = (record.artifact_manifest or {}).get(artifact_key)
    if not relative_path:
        relative_path = f"{record.storage_path}/{default_filename}"
    artifact_path = (SCREENER_RESULTS_DIR / relative_path).resolve()
    try:
        artifact_path.relative_to(SCREENER_RESULTS_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Screener artifact not found") from exc
    return artifact_path


def _get_authorized_screener_task(
    task_id: str,
    current_user: auth.User | None = None,
) -> ScreenerTask:
    task = _get_screener_task(task_id)
    if not _can_access_screener_owner(current_user, task.owner_user_id):
        raise HTTPException(status_code=404, detail=f"Screener task '{task_id}' not found")
    return task


def _active_tasks_dir() -> Path:
    return REPORTS_DIR / TASKS_STATE_DIRNAME / ACTIVE_TASKS_DIRNAME


def _task_snapshot_path(task_id: str) -> Path:
    return _active_tasks_dir() / task_id / "task.json"


def _active_screener_tasks_dir() -> Path:
    return SCREENER_RESULTS_DIR / SCREENER_TASKS_STATE_DIRNAME / ACTIVE_TASKS_DIRNAME


def _screener_task_snapshot_path(task_id: str) -> Path:
    return _active_screener_tasks_dir() / task_id / "task.json"


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _delete_task_snapshot(task_id: str) -> None:
    snapshot_path = _task_snapshot_path(task_id)
    with suppress(FileNotFoundError):
        snapshot_path.unlink()

    for directory in (snapshot_path.parent, _active_tasks_dir(), _active_tasks_dir().parent):
        with suppress(OSError):
            directory.rmdir()


def _persist_task_snapshot(task_id: str) -> None:
    task = _get_task(task_id)
    snapshot = task.to_dict()
    if snapshot["status"] in TERMINAL_TASK_STATUSES:
        _delete_task_snapshot(task_id)
        return
    _write_json_atomic(_task_snapshot_path(task_id), snapshot)


def _delete_screener_task_snapshot(task_id: str) -> None:
    snapshot_path = _screener_task_snapshot_path(task_id)
    with suppress(FileNotFoundError):
        snapshot_path.unlink()

    for directory in (
        snapshot_path.parent,
        _active_screener_tasks_dir(),
        _active_screener_tasks_dir().parent,
    ):
        with suppress(OSError):
            directory.rmdir()


def _persist_screener_task_snapshot(task_id: str) -> None:
    task = _get_screener_task(task_id)
    snapshot = task.to_dict()
    if snapshot["status"] in TERMINAL_TASK_STATUSES:
        _delete_screener_task_snapshot(task_id)
        return
    _write_json_atomic(_screener_task_snapshot_path(task_id), snapshot)


def _task_from_snapshot(payload: dict) -> Task:
    request_payload = payload.get("request_payload")
    if not isinstance(request_payload, dict):
        raise ValueError("Persisted task snapshot is missing request_payload")

    return Task(
        id=str(payload["id"]),
        request=AnalysisRequest(**request_payload),
        owner_user_id=payload.get("owner_user_id"),
        status=str(payload.get("status") or "pending"),
        latest_progress=payload.get("latest_progress"),
        report_id=payload.get("report_id"),
        error=payload.get("error"),
    )


def _get_task(task_id: str) -> Task:
    with tasks_lock:
        task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


def _get_screener_task(task_id: str) -> ScreenerTask:
    with tasks_lock:
        task = screener_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Screener task '{task_id}' not found")
    return task


def _append_progress(task_id: str, progress: AnalysisProgress) -> None:
    event_payload = progress.to_dict()
    with tasks_lock:
        task = tasks[task_id]
        task.latest_progress = event_payload
        task.progress_events.append(event_payload)
    _persist_task_snapshot(task_id)


def _append_screener_progress(task_id: str, progress: dict) -> None:
    with tasks_lock:
        task = screener_tasks[task_id]
        task.latest_progress = progress
        task.progress_events.append(progress)
    _persist_screener_task_snapshot(task_id)


def _set_task_status(task_id: str, status: str, error: Optional[str] = None) -> None:
    with tasks_lock:
        task = tasks[task_id]
        task.status = status
        if error is not None:
            task.error = error
    _persist_task_snapshot(task_id)


def _set_screener_task_status(task_id: str, status: str, error: Optional[str] = None) -> None:
    with tasks_lock:
        task = screener_tasks[task_id]
        task.status = status
        if error is not None:
            task.error = error
    _persist_screener_task_snapshot(task_id)


def _build_failure_progress(task: Task, error: str) -> dict:
    latest_progress = task.latest_progress or {
        "stage_status": {
            "Analysts": "not_started",
            "Research": "not_started",
            "Trading": "not_started",
            "Risk": "not_started",
            "Portfolio": "not_started",
        },
        "agent_status": {},
        "current_agent": None,
    }
    failure_progress = AnalysisProgress(
        timestamp=datetime.now().strftime("%H:%M:%S"),
        status="failed",
        stage_status=latest_progress["stage_status"],
        agent_status=latest_progress["agent_status"],
        current_agent=latest_progress["current_agent"],
        message=f"System: {error}",
    )
    return failure_progress.to_dict()


SCREENER_STAGES = ["Universe", "History", "Features", "Filters", "Ranking", "Export"]


def _build_screener_progress(
    *,
    status: str,
    stage: str,
    current: int,
    total: int,
    symbol: str | None = None,
    message: str | None = None,
) -> dict:
    stage_status = {
        key: (
            "processing"
            if key == stage
            else "completed"
            if SCREENER_STAGES.index(key) < SCREENER_STAGES.index(stage)
            else "not_started"
        )
        for key in SCREENER_STAGES
    }
    if status == "completed":
        stage_status = {key: "completed" for key in SCREENER_STAGES}
    if status == "failed" and stage not in SCREENER_STAGES:
        stage_status = {key: "not_started" for key in SCREENER_STAGES}

    detail = message or f"{stage} {current}/{total}"
    if symbol:
        detail = f"{detail} {symbol}"

    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "status": status,
        "stage_status": stage_status,
        "agent_status": {},
        "current_agent": symbol,
        "message": detail,
    }


def _build_screener_failure_progress(task: ScreenerTask, error: str) -> dict:
    latest_progress = task.latest_progress or {}
    latest_stage_status = latest_progress.get("stage_status") or {}
    stage_status = {
        key: (
            "not_started"
            if latest_stage_status.get(key) == "processing"
            else latest_stage_status.get(key, "not_started")
        )
        for key in SCREENER_STAGES
    }

    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "status": "failed",
        "stage_status": stage_status,
        "agent_status": latest_progress.get("agent_status") or {},
        "current_agent": latest_progress.get("current_agent"),
        "message": f"System: {error}",
    }


def _combined_active_task_count() -> int:
    with tasks_lock:
        analysis_active = sum(1 for task in tasks.values() if task.status in {"pending", "running"})
        screener_active = sum(
            1 for task in screener_tasks.values() if task.status in {"pending", "running"}
        )
    return analysis_active + screener_active


def _restore_persisted_active_tasks() -> None:
    active_dir = _active_tasks_dir()
    if not active_dir.is_dir():
        return

    for snapshot_path in sorted(active_dir.glob("*/task.json")):
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            task = _task_from_snapshot(payload)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            _delete_task_snapshot(snapshot_path.parent.name)
            continue

        if task.status in TERMINAL_TASK_STATUSES:
            _delete_task_snapshot(task.id)
            continue

        task.status = "failed"
        task.error = RECOVERED_TASK_ERROR
        failure_progress = _build_failure_progress(task, RECOVERED_TASK_ERROR)
        task.latest_progress = failure_progress
        task.progress_events = [failure_progress]

        with tasks_lock:
            tasks[task.id] = task

        _delete_task_snapshot(task.id)


def _restore_persisted_screener_tasks() -> None:
    active_dir = _active_screener_tasks_dir()
    if not active_dir.is_dir():
        return

    for snapshot_path in sorted(active_dir.glob("*/task.json")):
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            task = ScreenerTask(
                id=str(payload["id"]),
                request_payload=dict(payload.get("request_payload") or {}),
                config_payload=dict(payload.get("config_payload") or {}),
                owner_user_id=(
                    str(payload["owner_user_id"]).strip()
                    if payload.get("owner_user_id")
                    else None
                ),
                status=str(payload.get("status") or "pending"),
                latest_progress=payload.get("latest_progress"),
                progress_events=list(payload.get("progress_events") or []),
                run_id=payload.get("run_id"),
                error=payload.get("error"),
            )
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            _delete_screener_task_snapshot(snapshot_path.parent.name)
            continue

        if task.status in TERMINAL_TASK_STATUSES:
            _delete_screener_task_snapshot(task.id)
            continue

        task.status = "failed"
        task.error = RECOVERED_TASK_ERROR
        task.latest_progress = _build_screener_failure_progress(task, RECOVERED_TASK_ERROR)
        task.progress_events = [task.latest_progress]

        with tasks_lock:
            screener_tasks[task.id] = task

        _delete_screener_task_snapshot(task.id)


def _start_task_thread(task_id: str) -> threading.Thread:
    thread = threading.Thread(target=_run_task, args=(task_id,), daemon=True)
    thread.start()
    return thread


def _start_screener_task_thread(task_id: str) -> threading.Thread:
    thread = threading.Thread(target=_run_screener_task, args=(task_id,), daemon=True)
    thread.start()
    return thread


def _run_task(task_id: str) -> None:
    task = _get_task(task_id)
    temp_dir = TMP_REPORTS_DIR / task_id

    _set_task_status(task_id, "running")

    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        visible_trade_ids = _visible_trade_ids_for_task(task)
        progress_stream = run_analysis_streaming(
            task.request,
            temp_dir,
            reports_dir=REPORTS_DIR,
            visible_trade_ids=visible_trade_ids,
        )
        final_state = None
        while True:
            try:
                progress = next(progress_stream)
            except StopIteration as stop:
                final_state = stop.value
                break

            _append_progress(task_id, progress)

        if final_state is None:
            raise RuntimeError("Analysis did not return a final state")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_id = f"{task.request.ticker}_{timestamp}"
        save_report_to_disk(final_state, task.request.ticker, temp_dir)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        final_report_dir = REPORTS_DIR / report_id
        temp_dir.replace(final_report_dir)
        if auth.auth_enabled() and task.owner_user_id:
            metadata_payload = report_metadata.build_report_metadata(
                final_report_dir,
                report_id=report_id,
            )
            file_entries = report_metadata.build_report_file_index(final_report_dir)
            with auth.db_session() as db:
                report_metadata.upsert_report_run(
                    db,
                    report_id=report_id,
                    owner_user_id=task.owner_user_id,
                    visibility=report_metadata.REPORT_VISIBILITY_PRIVATE,
                    ticker=str(metadata_payload["ticker"] or task.request.ticker),
                    generated_at=metadata_payload["generated_at"],
                    storage_path=str(metadata_payload["storage_path"] or report_id),
                    file_entries=file_entries,
                )

        with tasks_lock:
            current_task = tasks[task_id]
            current_task.status = "completed"
            current_task.report_id = report_id
            if current_task.latest_progress is not None:
                current_task.latest_progress["status"] = "completed"
        _persist_task_snapshot(task_id)
    except Exception as exc:  # pragma: no cover - covered through task failure path
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

        with tasks_lock:
            current_task = tasks[task_id]
            current_task.status = "failed"
            current_task.error = str(exc)
            failure_progress = _build_failure_progress(current_task, str(exc))
            current_task.latest_progress = failure_progress
            current_task.progress_events.append(failure_progress)
        _persist_task_snapshot(task_id)


def _run_screener_task(task_id: str) -> None:
    task = _get_screener_task(task_id)
    _set_screener_task_status(task_id, "running")

    try:
        def progress_callback(
            stage: str,
            current: int,
            total: int,
            symbol: str | None = None,
            *,
            status: str | None = None,
            detail: str | None = None,
        ) -> None:
            normalized_stage = stage.capitalize()
            message = f"{normalized_stage} {current}/{total}"
            if symbol:
                message = f"{message} {symbol}"
            if status:
                message = f"{message} [{status}]"
            if detail:
                message = f"{message} {detail}"
            progress = _build_screener_progress(
                status="running",
                stage=normalized_stage,
                current=current,
                total=total,
                symbol=symbol,
                message=message,
            )
            _append_screener_progress(task_id, progress)

        result = run_screen(ScreenRunConfig(**task.config_payload), progress_callback=progress_callback)

        current_task = _get_screener_task(task_id)
        _record_screener_run_metadata(current_task, result)

        with tasks_lock:
            current_task = screener_tasks[task_id]
            current_task.status = "completed"
            current_task.run_id = Path(result.run_dir).name
            current_task.latest_progress = _build_screener_progress(
                status="completed",
                stage="Export",
                current=1,
                total=1,
                message=f"Export 1/1 {current_task.run_id}",
            )
            current_task.progress_events.append(current_task.latest_progress)
        _persist_screener_task_snapshot(task_id)
    except Exception as exc:  # pragma: no cover
        with tasks_lock:
            current_task = screener_tasks[task_id]
            current_task.status = "failed"
            current_task.error = str(exc)
            failure_progress = _build_screener_failure_progress(current_task, str(exc))
            current_task.latest_progress = failure_progress
            current_task.progress_events.append(failure_progress)
        _persist_screener_task_snapshot(task_id)


def _record_screener_run_metadata(task: ScreenerTask, result) -> None:
    if not auth.get_auth_settings().enabled:
        return
    if not task.owner_user_id:
        raise RuntimeError("Screener task owner is required when auth is enabled")

    run_dir = Path(result.run_dir).resolve()
    run_id = run_dir.name
    with auth.db_session() as db:
        screener_runs.upsert_screener_run(
            db,
            run_id=run_id,
            owner_user_id=task.owner_user_id,
            as_of_date=str(task.request_payload.get("as_of_date") or "").strip() or None,
            markets=list(task.request_payload.get("markets") or []),
            candidate_count=int(getattr(result, "candidate_count", 0) or 0),
            generated_at=run_id,
            storage_path=_relative_screener_storage_path(run_dir),
            artifact_manifest=_build_screener_artifact_manifest(run_dir),
        )


def _serialize_sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _read_project_env_values() -> dict[str, str]:
    if not PROJECT_ENV_FILE.is_file():
        return {}
    return {
        key: value.strip()
        for key, value in dotenv_values(PROJECT_ENV_FILE).items()
        if isinstance(value, str) and value.strip()
    }


def _get_project_secret(secret_name: str) -> str | None:
    return _read_project_env_values().get(secret_name)


def _hydrate_provider_credentials(provider: str) -> None:
    secret_name = PROVIDER_API_KEY_ENV_VARS.get(provider)
    if not secret_name:
        return

    secret_value = _get_project_secret(secret_name)
    if secret_value and not os.environ.get(secret_name):
        os.environ[secret_name] = secret_value


def _get_provider_availability(provider: str) -> dict[str, str | bool | None]:
    api_key_env = PROVIDER_API_KEY_ENV_VARS.get(provider)
    if api_key_env is None:
        return {"enabled": True, "disabled_reason": None}

    if _get_project_secret(api_key_env):
        return {"enabled": True, "disabled_reason": None}

    return {
        "enabled": False,
        "disabled_reason": f"Configure API key {api_key_env} to use this provider in web tasks.",
    }


def _get_config_options_payload() -> dict:
    provider_options = [
        {
            "label": label,
            "value": provider,
            **_get_provider_availability(provider),
        }
        for provider, label, _base_url in PROVIDER_OPTIONS
    ]
    model_options = {
        provider: {
            "quick": [
                {"label": label, "value": model_id}
                for label, model_id in QUICK_MODEL_OPTIONS[provider]
            ],
            "deep": [
                {"label": label, "value": model_id}
                for label, model_id in DEEP_MODEL_OPTIONS[provider]
            ],
        }
        for provider, _label, _base_url in PROVIDER_OPTIONS
    }
    analyst_options = [
        {"label": label, "value": value.value}
        for label, value in ANALYST_ORDER
    ]

    return {
        "providers": provider_options,
        "models": model_options,
        "analysts": analyst_options,
        "research_depth": RESEARCH_DEPTH_OPTIONS,
        "output_languages": OUTPUT_LANGUAGE_OPTIONS,
        "provider_settings": {
            "openai": {"openai_reasoning_effort": OPENAI_REASONING_OPTIONS},
            "google": {"google_thinking_level": GOOGLE_THINKING_OPTIONS},
        },
    }


def _get_screener_config_options_payload() -> dict:
    return {
        "markets": [
            {"label": "A-Share (cn)", "value": "cn", "enabled": True},
            {
                "label": "US Equities (us)",
                "value": "us",
                "enabled": bool(os.environ.get("SCREEN_US_MANIFEST_PATH")),
                "disabled_reason": None
                if os.environ.get("SCREEN_US_MANIFEST_PATH")
                else "Configure SCREEN_US_MANIFEST_PATH on the backend to enable US screening.",
            },
        ],
        "cn_data_sources": [
            {"label": "Tushare", "value": "tushare"},
            {"label": "AkShare", "value": "akshare"},
        ],
        "breakout_types": [
            {"label": "Platform Breakout", "value": "platform_breakout"},
            {"label": "Box Breakout", "value": "box_breakout"},
            {"label": "Wedge Breakout", "value": "wedge_breakout"},
        ],
        "defaults": {
            "cn_data_source": "tushare",
            "top_k": 500,
            "breakout_types": [],
        },
    }


def _resolve_screener_run_dir(run_id: str) -> Path:
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=404, detail="Screener run not found")
    run_dir = SCREENER_RESULTS_DIR / run_id
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Screener run '{run_id}' not found")
    return run_dir


def _list_screener_runs_from_disk() -> list[dict]:
    if not SCREENER_RESULTS_DIR.is_dir():
        return []

    runs: list[dict] = []
    for entry in SCREENER_RESULTS_DIR.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        meta_path = entry / "run_meta.json"
        if not meta_path.is_file():
            continue
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue

        runs.append(
            {
                "id": entry.name,
                "as_of_date": payload.get("as_of_date"),
                "markets": payload.get("config", {}).get("markets", []),
                "candidate_count": payload.get("candidate_count", 0),
                "generated_at": payload.get("run_timestamp", entry.name),
            }
        )

    runs.sort(key=lambda row: row["generated_at"] or "", reverse=True)
    return runs


def list_screener_runs(current_user: auth.User | None = None) -> list[dict]:
    if not auth.get_auth_settings().enabled:
        return _list_screener_runs_from_disk()
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    with auth.db_session() as db:
        owner_scope = _owner_scope_for_user(current_user)
        return [
            screener_runs.serialize_screener_run_summary(record)
            for record in screener_runs.list_screener_run_records(db, owner_user_id=owner_scope)
        ]


def get_screener_run(run_id: str, current_user: auth.User | None = None) -> dict:
    if auth.get_auth_settings().enabled:
        if current_user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        try:
            with auth.db_session() as db:
                owner_scope = _owner_scope_for_user(current_user)
                record = screener_runs.get_screener_run_record(
                    db,
                    run_id,
                    owner_user_id=owner_scope,
                )
                payload = screener_runs.serialize_screener_run_detail(record)
        except Exception as exc:
            raise _translate_auth_error(exc) from exc

        _resolve_screener_run_dir_from_record(record)
        meta_path = _resolve_screener_artifact_path(record, "run_meta", "run_meta.json")
        if not meta_path.is_file():
            raise HTTPException(status_code=404, detail=f"Screener run '{run_id}' not found")
        try:
            file_payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to read screener run: {exc}") from exc

        payload["filtered_count_by_reason"] = file_payload.get("filtered_count_by_reason", {})
        return payload

    run_dir = _resolve_screener_run_dir(run_id)
    meta_path = run_dir / "run_meta.json"
    if not meta_path.is_file():
        raise HTTPException(status_code=404, detail=f"Screener run '{run_id}' not found")
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read screener run: {exc}") from exc

    return {
        "id": run_id,
        "as_of_date": payload.get("as_of_date"),
        "markets": payload.get("config", {}).get("markets", []),
        "candidate_count": payload.get("candidate_count", 0),
        "generated_at": payload.get("run_timestamp"),
        "filtered_count_by_reason": payload.get("filtered_count_by_reason", {}),
        "artifact_paths": payload.get("artifact_paths", {}),
    }


def get_screener_run_candidates(
    run_id: str,
    current_user: auth.User | None = None,
) -> list[dict]:
    if auth.get_auth_settings().enabled:
        if current_user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        try:
            with auth.db_session() as db:
                owner_scope = _owner_scope_for_user(current_user)
                record = screener_runs.get_screener_run_record(
                    db,
                    run_id,
                    owner_user_id=owner_scope,
                )
        except Exception as exc:
            raise _translate_auth_error(exc) from exc

        candidates_path = _resolve_screener_artifact_path(record, "candidates", "candidates.csv")
    else:
        run_dir = _resolve_screener_run_dir(run_id)
        candidates_path = run_dir / "candidates.csv"

    if not candidates_path.is_file():
        raise HTTPException(status_code=404, detail=f"Candidates for run '{run_id}' not found")
    try:
        import pandas as pd

        df = pd.read_csv(candidates_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read candidates: {exc}") from exc
    return df.where(pd.notna(df), None).to_dict(orient="records")


# ---------------------------------------------------------------------------
# Health and auth endpoints
# ---------------------------------------------------------------------------


@app.get("/api/healthz")
def healthz() -> dict:
    settings = auth.get_auth_settings()
    return {"status": "ok", "auth": {"enabled": settings.enabled, "mode": settings.mode}}


@app.get("/api/auth/me")
def get_current_auth_state(request: Request) -> dict:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        return auth.build_auth_state_payload(None)

    with auth.db_session() as db:
        user = auth.get_request_user(db, request, settings=settings)
        return auth.build_auth_state_payload(user)


@app.post("/api/auth/login")
def login(payload: LoginPayload, request: Request, response: Response) -> dict:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        raise HTTPException(status_code=409, detail="Auth is disabled")
    client_ip = request.client.host if request.client else None

    try:
        with auth.db_session() as db:
            user = auth.authenticate_user(
                db,
                email=payload.email,
                password=payload.password,
            )
            session_token = auth.create_user_session(
                db,
                user,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                settings=settings,
            )
            result = auth.build_auth_state_payload(user)
    except auth.AuthValidationError as exc:
        logger.warning(
            "login failed email=%s ip=%s reason=%s",
            payload.email.strip().lower(),
            client_ip,
            exc,
        )
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except auth.AuthPermissionError as exc:
        logger.warning(
            "login denied email=%s ip=%s reason=%s",
            payload.email.strip().lower(),
            client_ip,
            exc,
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise _translate_auth_error(exc) from exc

    auth.set_session_cookie(response, session_token)
    logger.info(
        "login success user_id=%s email=%s role=%s ip=%s",
        user.id,
        user.email,
        user.role,
        client_ip,
    )
    return result


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict:
    settings = auth.get_auth_settings()
    if settings.enabled:
        with auth.db_session() as db:
            auth.revoke_session_token(db, auth.current_session_token(request))
    auth.clear_session_cookie(response)
    return auth.build_auth_state_payload(None)


@app.post("/api/auth/change-password")
def change_password(
    payload: ChangePasswordPayload,
    request: Request,
    response: Response,
) -> dict:
    settings = auth.get_auth_settings()
    if not settings.enabled:
        raise HTTPException(status_code=409, detail="Auth is disabled")

    try:
        with auth.db_session() as db:
            user = auth.require_request_user(db, request)
            auth.change_user_password(
                db,
                user,
                current_password=payload.current_password,
                new_password=payload.new_password,
            )
            session_token = auth.create_user_session(
                db,
                user,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                settings=settings,
            )
            result = auth.build_auth_state_payload(user)
    except Exception as exc:
        raise _translate_auth_error(exc) from exc

    auth.set_session_cookie(response, session_token)
    return result


# ---------------------------------------------------------------------------
# Admin user endpoints
# ---------------------------------------------------------------------------


@app.get("/api/admin/users", dependencies=ADMIN_API_DEPENDENCIES)
def list_admin_users() -> list[dict]:
    try:
        with auth.db_session() as db:
            return [auth.serialize_user(user) for user in auth.list_users(db)]
    except Exception as exc:
        raise _translate_auth_error(exc) from exc


@app.get("/api/admin/users/{user_id}", dependencies=ADMIN_API_DEPENDENCIES)
def get_admin_user(user_id: str) -> dict:
    try:
        with auth.db_session() as db:
            return auth.serialize_user(auth.get_user_by_id(db, user_id))
    except Exception as exc:
        raise _translate_auth_error(exc) from exc


@app.post("/api/admin/users", dependencies=ADMIN_API_DEPENDENCIES)
def create_admin_user(payload: AdminUserCreatePayload, request: Request) -> dict:
    try:
        with auth.db_session() as db:
            actor = auth.require_request_user(db, request)
            user = auth.create_user(
                db,
                email=payload.email,
                display_name=payload.display_name,
                password=payload.password,
                role=payload.role,
                status=payload.status,
                must_change_password=payload.must_change_password,
            )
            result = auth.serialize_user(user)
    except Exception as exc:
        raise _translate_auth_error(exc) from exc
    logger.info(
        "admin user created actor_user_id=%s target_user_id=%s role=%s status=%s",
        actor.id,
        user.id,
        user.role,
        user.status,
    )
    return result


@app.put("/api/admin/users/{user_id}", dependencies=ADMIN_API_DEPENDENCIES)
def update_admin_user(
    user_id: str,
    payload: AdminUserUpdatePayload,
    request: Request,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = auth.require_request_user(db, request)
            user = auth.update_user(
                db,
                user_id,
                display_name=payload.display_name,
                role=payload.role,
                status=payload.status,
                must_change_password=payload.must_change_password,
            )
            result = auth.serialize_user(user)
    except Exception as exc:
        raise _translate_auth_error(exc) from exc
    logger.info(
        "admin user updated actor_user_id=%s target_user_id=%s role=%s status=%s",
        actor.id,
        user.id,
        user.role,
        user.status,
    )
    return result


@app.delete("/api/admin/users/{user_id}", dependencies=ADMIN_API_DEPENDENCIES)
def delete_admin_user(user_id: str, request: Request) -> dict:
    try:
        with auth.db_session() as db:
            actor = auth.require_request_user(db, request)
            auth.delete_user(db, user_id)
            result = {"deleted": True, "user_id": user_id}
    except Exception as exc:
        raise _translate_auth_error(exc) from exc
    logger.info(
        "admin user deleted actor_user_id=%s target_user_id=%s",
        actor.id,
        user_id,
    )
    return result


@app.post("/api/admin/users/{user_id}/reset-password", dependencies=ADMIN_API_DEPENDENCIES)
def reset_admin_user_password(
    user_id: str,
    payload: AdminUserResetPasswordPayload,
    request: Request,
) -> dict:
    try:
        with auth.db_session() as db:
            actor = auth.require_request_user(db, request)
            user = auth.reset_user_password(
                db,
                user_id,
                new_password=payload.new_password,
                must_change_password=payload.must_change_password,
            )
            result = auth.serialize_user(user)
    except Exception as exc:
        raise _translate_auth_error(exc) from exc
    logger.info(
        "admin user password reset actor_user_id=%s target_user_id=%s",
        actor.id,
        user.id,
    )
    return result


# ---------------------------------------------------------------------------
# Report endpoints
# ---------------------------------------------------------------------------


@app.get("/api/reports", dependencies=AUTH_API_DEPENDENCIES)
def list_reports(request: Request = None) -> list[dict]:
    if auth.auth_enabled() and request is not None:
        try:
            with auth.db_session() as db:
                current_user = auth.get_request_user(db, request)
                if current_user is not None:
                    owner_scope = _owner_scope_for_user(current_user)
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
            raise _translate_auth_error(exc) from exc

    if not REPORTS_DIR.is_dir():
        return []

    results = []
    for entry in REPORTS_DIR.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        report_id = entry.name
        ticker, date_str, time_str = _parse_complete_report_header(entry)
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


@app.get("/api/reports/{report_id}/structure", dependencies=AUTH_API_DEPENDENCIES)
def get_structure(report_id: str, request: Request = None) -> dict:
    if auth.auth_enabled() and request is not None:
        try:
            with auth.db_session() as db:
                current_user = auth.get_request_user(db, request)
                if current_user is not None:
                    owner_scope = _owner_scope_for_user(current_user)
                    record = report_metadata.get_report_run(
                        db,
                        report_id,
                        owner_user_id=owner_scope,
                        include_workspace=owner_scope is not None,
                    )
                    report_dir = _resolve_report_dir_from_storage_path(record.storage_path)
                    structure = _build_report_structure_from_index(
                        report_dir,
                        report_metadata.list_report_files(db, report_id),
                    )
                    return {
                        "id": record.id,
                        "ticker": record.ticker,
                        **structure,
                    }
        except Exception as exc:
            raise _translate_auth_error(exc) from exc

    report_dir = _resolve_report_dir(report_id)

    ticker, _date, _time = _parse_complete_report_header(report_dir)
    if ticker is None:
        ticker = report_id

    return {
        "id": report_id,
        "ticker": ticker,
        "has_complete": (report_dir / "complete_report.md").is_file(),
        "categories": _scan_categories(report_dir),
        "artifacts": _scan_artifacts(report_dir),
    }


@app.get("/api/reports/{report_id}/content", dependencies=AUTH_API_DEPENDENCIES)
def get_content(report_id: str, path: str, request: Request = None) -> dict:
    if auth.auth_enabled() and request is not None:
        try:
            with auth.db_session() as db:
                current_user = auth.get_request_user(db, request)
                if current_user is not None:
                    owner_scope = _owner_scope_for_user(current_user)
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
                    report_dir = _resolve_report_dir_from_storage_path(record.storage_path)
                else:
                    report_dir = _resolve_report_dir(report_id)
        except Exception as exc:
            raise _translate_auth_error(exc) from exc
    else:
        report_dir = _resolve_report_dir(report_id)

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
        raise HTTPException(
            status_code=500, detail=f"Failed to read file: {exc}"
        ) from exc

    return {"content": content}


# ---------------------------------------------------------------------------
# Trade feedback endpoints
# ---------------------------------------------------------------------------


@app.get("/api/trades", dependencies=AUTH_API_DEPENDENCIES)
def list_trades(ticker: Optional[str] = None, request: Request = None) -> list[dict]:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = _require_trade_request_user(db, request)
                assert user is not None
                return _load_owner_scoped_trade_records(db, user.id, ticker=ticker)
        return list_trade_records_file(ticker=ticker, reports_dir=REPORTS_DIR)
    except HTTPException:
        raise
    except ValueError as exc:
        raise _translate_trade_feedback_error(exc) from exc


@app.post("/api/trades", dependencies=AUTH_API_DEPENDENCIES)
def create_trade(payload: TradeRecordCreatePayload, request: Request = None) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = _require_trade_request_user(db, request)
                assert user is not None
                record = create_trade_record_file(
                    payload.model_dump(),
                    reports_dir=REPORTS_DIR,
                )
                _sync_trade_entry_metadata(db, record, user.id)
                return record
        return create_trade_record_file(payload.model_dump(), reports_dir=REPORTS_DIR)
    except HTTPException:
        raise
    except ValueError as exc:
        raise _translate_trade_feedback_error(exc) from exc


@app.get("/api/trades/{trade_id}", dependencies=AUTH_API_DEPENDENCIES)
def get_trade(trade_id: str, request: Request = None) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = _require_trade_request_user(db, request)
                assert user is not None
                trade_entries.require_trade_entry_for_owner(db, trade_id, user.id)
                return {
                    "record": get_trade_record_file(trade_id, reports_dir=REPORTS_DIR),
                    "reviews": list_trade_reviews_file(trade_id, reports_dir=REPORTS_DIR),
                }
        return {
            "record": get_trade_record_file(trade_id, reports_dir=REPORTS_DIR),
            "reviews": list_trade_reviews_file(trade_id, reports_dir=REPORTS_DIR),
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise _translate_trade_feedback_error(exc) from exc


@app.put("/api/trades/{trade_id}", dependencies=AUTH_API_DEPENDENCIES)
def update_trade(
    trade_id: str,
    payload: TradeRecordUpdatePayload,
    request: Request = None,
) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = _require_trade_request_user(db, request)
                assert user is not None
                trade_entries.require_trade_entry_for_owner(db, trade_id, user.id)
                record = update_trade_record_file(
                    trade_id,
                    payload.model_dump(exclude_unset=True),
                    reports_dir=REPORTS_DIR,
                )
                _sync_trade_entry_metadata(db, record, user.id)
                return record
        return update_trade_record_file(
            trade_id,
            payload.model_dump(exclude_unset=True),
            reports_dir=REPORTS_DIR,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise _translate_trade_feedback_error(exc) from exc


@app.get("/api/trades/{trade_id}/reviews", dependencies=AUTH_API_DEPENDENCIES)
def get_trade_reviews(trade_id: str, request: Request = None) -> list[dict]:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = _require_trade_request_user(db, request)
                assert user is not None
                trade_entries.require_trade_entry_for_owner(db, trade_id, user.id)
                return list_trade_reviews_file(trade_id, reports_dir=REPORTS_DIR)
        return list_trade_reviews_file(trade_id, reports_dir=REPORTS_DIR)
    except HTTPException:
        raise
    except ValueError as exc:
        raise _translate_trade_feedback_error(exc) from exc


@app.post("/api/trades/{trade_id}/reviews", dependencies=AUTH_API_DEPENDENCIES)
def create_trade_review(
    trade_id: str,
    payload: TradeReviewCreatePayload,
    request: Request = None,
) -> dict:
    _hydrate_provider_credentials(payload.llm_provider)
    provider_availability = _get_provider_availability(payload.llm_provider)
    if not provider_availability["enabled"]:
        raise HTTPException(
            status_code=400,
            detail=str(provider_availability["disabled_reason"]),
        )

    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = _require_trade_request_user(db, request)
                assert user is not None
                trade_entries.require_trade_entry_for_owner(db, trade_id, user.id)
                review = generate_trade_review_file(
                    trade_id,
                    review_type=payload.review_type,
                    llm_provider=payload.llm_provider,
                    model=payload.model,
                    output_language=payload.output_language,
                    google_thinking_level=payload.google_thinking_level,
                    openai_reasoning_effort=payload.openai_reasoning_effort,
                    analysis_date=payload.analysis_date,
                    analysis_references=(
                        payload.model_dump()["analysis_references"]
                        if payload.analysis_references is not None
                        else None
                    ),
                    reports_dir=REPORTS_DIR,
                )
                record = get_trade_record_file(trade_id, reports_dir=REPORTS_DIR)
                _sync_trade_entry_metadata(db, record, user.id)
                return review
        return generate_trade_review_file(
            trade_id,
            review_type=payload.review_type,
            llm_provider=payload.llm_provider,
            model=payload.model,
            output_language=payload.output_language,
            google_thinking_level=payload.google_thinking_level,
            openai_reasoning_effort=payload.openai_reasoning_effort,
            analysis_date=payload.analysis_date,
            analysis_references=(
                payload.model_dump()["analysis_references"]
                if payload.analysis_references is not None
                else None
            ),
            reports_dir=REPORTS_DIR,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise _translate_trade_feedback_error(exc) from exc


@app.put("/api/trades/{trade_id}/reviews/{review_type}", dependencies=AUTH_API_DEPENDENCIES)
def save_trade_review(
    trade_id: str,
    review_type: str,
    payload: TradeReviewSavePayload,
    request: Request = None,
) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = _require_trade_request_user(db, request)
                assert user is not None
                trade_entries.require_trade_entry_for_owner(db, trade_id, user.id)
                review = save_trade_review_file(
                    trade_id,
                    review_type=review_type,
                    payload=payload.model_dump(
                        exclude={"analysis_date", "analysis_references"}
                    ),
                    analysis_date=payload.analysis_date,
                    analysis_references=(
                        payload.model_dump()["analysis_references"]
                        if payload.analysis_references is not None
                        else None
                    ),
                    reports_dir=REPORTS_DIR,
                )
                record = get_trade_record_file(trade_id, reports_dir=REPORTS_DIR)
                _sync_trade_entry_metadata(db, record, user.id)
                return review
        return save_trade_review_file(
            trade_id,
            review_type=review_type,
            payload=payload.model_dump(
                exclude={"analysis_date", "analysis_references"}
            ),
            analysis_date=payload.analysis_date,
            analysis_references=(
                payload.model_dump()["analysis_references"]
                if payload.analysis_references is not None
                else None
            ),
            reports_dir=REPORTS_DIR,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise _translate_trade_feedback_error(exc) from exc


@app.get("/api/trade-feedback/{ticker}", dependencies=AUTH_API_DEPENDENCIES)
def get_ticker_trade_feedback(
    ticker: str,
    limit: int = 3,
    analysis_date: Optional[str] = None,
    request: Request = None,
) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = _require_trade_request_user(db, request)
                assert user is not None
                visible_trade_ids = trade_entries.list_visible_trade_ids(
                    db,
                    user.id,
                    ticker=ticker,
                )
                return get_trade_feedback_payload_file(
                    ticker,
                    reports_dir=REPORTS_DIR,
                    limit=limit,
                    analysis_date=analysis_date,
                    visible_trade_ids=visible_trade_ids,
                )
        return get_trade_feedback_payload_file(
            ticker,
            reports_dir=REPORTS_DIR,
            limit=limit,
            analysis_date=analysis_date,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise _translate_trade_feedback_error(exc) from exc


# ---------------------------------------------------------------------------
# Task endpoints
# ---------------------------------------------------------------------------


@app.post("/api/tasks", dependencies=AUTH_API_DEPENDENCIES)
def create_task(payload: TaskCreatePayload, request: Request = None) -> dict:
    analysis_request = AnalysisRequest(**payload.model_dump())
    _hydrate_provider_credentials(analysis_request.llm_provider)
    provider_availability = _get_provider_availability(analysis_request.llm_provider)
    if not provider_availability["enabled"]:
        raise HTTPException(
            status_code=400,
            detail=str(provider_availability["disabled_reason"]),
        )

    if _combined_active_task_count() >= 2:
        raise HTTPException(
            status_code=409,
            detail="Task queue is full. Wait for the active tasks to finish.",
        )

    task_id = uuid.uuid4().hex
    task = Task(
        id=task_id,
        request=analysis_request,
        owner_user_id=_resolve_task_owner_user_id(request),
    )

    with tasks_lock:
        tasks[task_id] = task

    _persist_task_snapshot(task_id)
    _start_task_thread(task_id)
    return {"task_id": task_id, "status": "pending"}


@app.post("/api/screener/tasks", dependencies=SCREENER_API_DEPENDENCIES)
def create_screener_task(
    payload: ScreenTaskCreatePayload,
    request: Request = None,
) -> dict:
    current_user = _require_screener_user(request)
    if _combined_active_task_count() >= 2:
        raise HTTPException(
            status_code=409,
            detail="Task queue is full. Wait for the active tasks to finish.",
        )

    request_payload = payload.model_dump()
    config_payload = dict(request_payload)
    config_payload["output_dir"] = str(SCREENER_RESULTS_DIR)
    if "cn" in request_payload["markets"]:
        manifest_path = os.environ.get("SCREEN_CN_MANIFEST_PATH")
        if manifest_path:
            config_payload["cn_manifest_path"] = manifest_path
    if "us" in request_payload["markets"]:
        manifest_path = os.environ.get("SCREEN_US_MANIFEST_PATH")
        if not manifest_path:
            raise HTTPException(
                status_code=400,
                detail="Configure SCREEN_US_MANIFEST_PATH on the backend before launching US screening tasks.",
            )
        config_payload["us_manifest_path"] = manifest_path

    try:
        ScreenRunConfig(**config_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task_id = uuid.uuid4().hex
    task = ScreenerTask(
        id=task_id,
        request_payload=request_payload,
        config_payload=config_payload,
        owner_user_id=current_user.id if current_user is not None else None,
    )

    with tasks_lock:
        screener_tasks[task_id] = task

    _persist_screener_task_snapshot(task_id)
    _start_screener_task_thread(task_id)
    return {"task_id": task_id, "status": "pending"}


@app.get("/api/tasks", dependencies=AUTH_API_DEPENDENCIES)
def list_tasks() -> list[dict]:
    with tasks_lock:
        return [task.to_dict() for task in tasks.values()]


@app.get("/api/screener/tasks", dependencies=SCREENER_API_DEPENDENCIES)
def list_screener_tasks(request: Request = None) -> list[dict]:
    current_user = _require_screener_user(request)
    with tasks_lock:
        return [
            task.to_dict()
            for task in screener_tasks.values()
            if _can_access_screener_owner(current_user, task.owner_user_id)
        ]


@app.get("/api/tasks/{task_id}", dependencies=AUTH_API_DEPENDENCIES)
def get_task_status(task_id: str) -> dict:
    return _get_task(task_id).to_dict()


@app.get("/api/screener/tasks/{task_id}", dependencies=SCREENER_API_DEPENDENCIES)
def get_screener_task_status(task_id: str, request: Request = None) -> dict:
    current_user = _require_screener_user(request)
    return _get_authorized_screener_task(task_id, current_user).to_dict()


@app.get("/api/tasks/{task_id}/stream", dependencies=AUTH_API_DEPENDENCIES)
async def stream_task(task_id: str, request: Request) -> StreamingResponse:
    _get_task(task_id)

    async def event_generator():
        cursor = 0

        while True:
            if await request.is_disconnected():
                break

            with tasks_lock:
                task = tasks.get(task_id)
                if task is None:
                    break
                pending_events = task.progress_events[cursor:]
                task_status = task.status

            for event in pending_events:
                cursor += 1
                yield _serialize_sse_event(event)

            if task_status in TERMINAL_TASK_STATUSES and not pending_events:
                break

            await asyncio.sleep(0.25)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/screener/tasks/{task_id}/stream", dependencies=SCREENER_API_DEPENDENCIES)
async def stream_screener_task(task_id: str, request: Request) -> StreamingResponse:
    current_user = _require_screener_user(request)
    _get_authorized_screener_task(task_id, current_user)

    async def event_generator():
        cursor = 0

        while True:
            if await request.is_disconnected():
                break

            with tasks_lock:
                task = screener_tasks.get(task_id)
                if task is None:
                    break
                pending_events = task.progress_events[cursor:]
                task_status = task.status

            for event in pending_events:
                cursor += 1
                yield _serialize_sse_event(event)

            if task_status in TERMINAL_TASK_STATUSES and not pending_events:
                break

            await asyncio.sleep(0.25)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/screener/runs", dependencies=SCREENER_API_DEPENDENCIES)
def list_screener_runs_endpoint(request: Request) -> list[dict]:
    current_user = _require_screener_user(request)
    return list_screener_runs(current_user)


@app.get("/api/screener/runs/{run_id}", dependencies=SCREENER_API_DEPENDENCIES)
def get_screener_run_endpoint(run_id: str, request: Request) -> dict:
    current_user = _require_screener_user(request)
    return get_screener_run(run_id, current_user)


@app.get("/api/screener/runs/{run_id}/candidates", dependencies=SCREENER_API_DEPENDENCIES)
def get_screener_run_candidates_endpoint(run_id: str, request: Request) -> list[dict]:
    current_user = _require_screener_user(request)
    return get_screener_run_candidates(run_id, current_user)


# ---------------------------------------------------------------------------
# Config endpoint
# ---------------------------------------------------------------------------


@app.get("/api/config/options", dependencies=AUTH_API_DEPENDENCIES)
def get_config_options() -> dict:
    return _get_config_options_payload()


@app.get("/api/screener/config/options", dependencies=AUTH_API_DEPENDENCIES)
def get_screener_config_options() -> dict:
    return _get_screener_config_options_payload()
