"""
TradingAgents Report Viewer backend.

Endpoints:
  GET  /api/reports
  GET  /api/reports/{report_id}/structure
  GET  /api/reports/{report_id}/content?path=...
  POST /api/tasks
  GET  /api/tasks
  GET  /api/tasks/{task_id}
  GET  /api/tasks/{task_id}/stream
  GET  /api/config/options
"""

import asyncio
import json
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

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from cli.utils import ANALYST_ORDER
from tradingagents.llm_clients.model_config import (
    DEEP_MODEL_OPTIONS,
    PROVIDER_OPTIONS,
    QUICK_MODEL_OPTIONS,
)
from tradingagents.screener.pipeline import run_screen
from tradingagents.screener.schema import ScreenRunConfig
from tradingagents.runner import AnalysisProgress, AnalysisRequest, run_analysis_streaming, save_report_to_disk

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


class ScreenTaskCreatePayload(BaseModel):
    markets: list[str]
    as_of_date: str
    top_k: int
    cn_data_source: str = "tushare"


@dataclass
class Task:
    id: str
    request: AnalysisRequest
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
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

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

    return results


def _resolve_report_dir(report_id: str) -> Path:
    if report_id == ".tmp":
        raise HTTPException(status_code=404, detail="Report not found")
    if "/" in report_id or "\\" in report_id or ".." in report_id:
        raise HTTPException(status_code=404, detail="Report not found")

    report_dir = REPORTS_DIR / report_id
    if not report_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return report_dir


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

        progress_stream = run_analysis_streaming(task.request, temp_dir)
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
        def progress_callback(stage: str, current: int, total: int, symbol: str | None = None) -> None:
            normalized_stage = stage.capitalize()
            progress = _build_screener_progress(
                status="running",
                stage=normalized_stage,
                current=current,
                total=total,
                symbol=symbol,
            )
            _append_screener_progress(task_id, progress)

        result = run_screen(ScreenRunConfig(**task.config_payload), progress_callback=progress_callback)

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
        "defaults": {
            "cn_data_source": "tushare",
            "top_k": 500,
        },
    }


def _resolve_screener_run_dir(run_id: str) -> Path:
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=404, detail="Screener run not found")
    run_dir = SCREENER_RESULTS_DIR / run_id
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Screener run '{run_id}' not found")
    return run_dir


def list_screener_runs() -> list[dict]:
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


def get_screener_run(run_id: str) -> dict:
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


def get_screener_run_candidates(run_id: str) -> list[dict]:
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
# Report endpoints
# ---------------------------------------------------------------------------


@app.get("/api/reports")
def list_reports() -> list[dict]:
    if not REPORTS_DIR.is_dir():
        return []

    results = []
    for entry in REPORTS_DIR.iterdir():
        if not entry.is_dir() or entry.name == ".tmp":
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


@app.get("/api/reports/{report_id}/structure")
def get_structure(report_id: str) -> dict:
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


@app.get("/api/reports/{report_id}/content")
def get_content(report_id: str, path: str) -> dict:
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
# Task endpoints
# ---------------------------------------------------------------------------


@app.post("/api/tasks")
def create_task(payload: TaskCreatePayload) -> dict:
    request = AnalysisRequest(**payload.model_dump())
    _hydrate_provider_credentials(request.llm_provider)
    provider_availability = _get_provider_availability(request.llm_provider)
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
    task = Task(id=task_id, request=request)

    with tasks_lock:
        tasks[task_id] = task

    _persist_task_snapshot(task_id)
    _start_task_thread(task_id)
    return {"task_id": task_id, "status": "pending"}


@app.post("/api/screener/tasks")
def create_screener_task(payload: ScreenTaskCreatePayload) -> dict:
    if _combined_active_task_count() >= 2:
        raise HTTPException(
            status_code=409,
            detail="Task queue is full. Wait for the active tasks to finish.",
        )

    request_payload = payload.model_dump()
    config_payload = dict(request_payload)
    config_payload["output_dir"] = str(SCREENER_RESULTS_DIR)
    if "us" in request_payload["markets"]:
        manifest_path = os.environ.get("SCREEN_US_MANIFEST_PATH")
        if not manifest_path:
            raise HTTPException(
                status_code=400,
                detail="Configure SCREEN_US_MANIFEST_PATH on the backend before launching US screening tasks.",
            )
        config_payload["us_manifest_path"] = manifest_path

    task_id = uuid.uuid4().hex
    task = ScreenerTask(
        id=task_id,
        request_payload=request_payload,
        config_payload=config_payload,
    )

    with tasks_lock:
        screener_tasks[task_id] = task

    _persist_screener_task_snapshot(task_id)
    _start_screener_task_thread(task_id)
    return {"task_id": task_id, "status": "pending"}


@app.get("/api/tasks")
def list_tasks() -> list[dict]:
    with tasks_lock:
        return [task.to_dict() for task in tasks.values()]


@app.get("/api/screener/tasks")
def list_screener_tasks() -> list[dict]:
    with tasks_lock:
        return [task.to_dict() for task in screener_tasks.values()]


@app.get("/api/tasks/{task_id}")
def get_task_status(task_id: str) -> dict:
    return _get_task(task_id).to_dict()


@app.get("/api/screener/tasks/{task_id}")
def get_screener_task_status(task_id: str) -> dict:
    return _get_screener_task(task_id).to_dict()


@app.get("/api/tasks/{task_id}/stream")
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


@app.get("/api/screener/tasks/{task_id}/stream")
async def stream_screener_task(task_id: str, request: Request) -> StreamingResponse:
    _get_screener_task(task_id)

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


@app.get("/api/screener/runs")
def list_screener_runs_endpoint() -> list[dict]:
    return list_screener_runs()


@app.get("/api/screener/runs/{run_id}")
def get_screener_run_endpoint(run_id: str) -> dict:
    return get_screener_run(run_id)


@app.get("/api/screener/runs/{run_id}/candidates")
def get_screener_run_candidates_endpoint(run_id: str) -> list[dict]:
    return get_screener_run_candidates(run_id)


# ---------------------------------------------------------------------------
# Config endpoint
# ---------------------------------------------------------------------------


@app.get("/api/config/options")
def get_config_options() -> dict:
    return _get_config_options_payload()


@app.get("/api/screener/config/options")
def get_screener_config_options() -> dict:
    return _get_screener_config_options_payload()
