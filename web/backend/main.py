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
from tradingagents.runner import AnalysisProgress, AnalysisRequest, run_analysis_streaming, save_report_to_disk

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPORTS_DIR = Path(os.environ.get("REPORTS_DIR", PROJECT_ROOT / "reports")).resolve()
TMP_REPORTS_DIR = REPORTS_DIR / ".tmp"

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
            "status": self.status,
            "latest_progress": self.latest_progress,
            "report_id": self.report_id,
            "error": self.error,
        }


tasks: dict[str, Task] = {}
tasks_lock = threading.Lock()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="TradingAgents Report Viewer", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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


def _resolve_report_dir(report_id: str) -> Path:
    if report_id == ".tmp":
        raise HTTPException(status_code=404, detail="Report not found")
    if "/" in report_id or "\\" in report_id or ".." in report_id:
        raise HTTPException(status_code=404, detail="Report not found")

    report_dir = REPORTS_DIR / report_id
    if not report_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return report_dir


def _get_task(task_id: str) -> Task:
    with tasks_lock:
        task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


def _append_progress(task_id: str, progress: AnalysisProgress) -> None:
    event_payload = progress.to_dict()
    with tasks_lock:
        task = tasks[task_id]
        task.latest_progress = event_payload
        task.progress_events.append(event_payload)


def _set_task_status(task_id: str, status: str, error: Optional[str] = None) -> None:
    with tasks_lock:
        task = tasks[task_id]
        task.status = status
        if error is not None:
            task.error = error


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


def _start_task_thread(task_id: str) -> threading.Thread:
    thread = threading.Thread(target=_run_task, args=(task_id,), daemon=True)
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

    with tasks_lock:
        active_task_count = sum(
            1 for task in tasks.values() if task.status in {"pending", "running"}
        )
        if active_task_count >= 2:
            raise HTTPException(
                status_code=409,
                detail="Task queue is full. Wait for the active tasks to finish.",
            )

    task_id = uuid.uuid4().hex
    task = Task(id=task_id, request=request)

    with tasks_lock:
        tasks[task_id] = task

    _start_task_thread(task_id)
    return {"task_id": task_id, "status": "pending"}


@app.get("/api/tasks")
def list_tasks() -> list[dict]:
    with tasks_lock:
        return [task.to_dict() for task in tasks.values()]


@app.get("/api/tasks/{task_id}")
def get_task_status(task_id: str) -> dict:
    return _get_task(task_id).to_dict()


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


# ---------------------------------------------------------------------------
# Config endpoint
# ---------------------------------------------------------------------------


@app.get("/api/config/options")
def get_config_options() -> dict:
    return _get_config_options_payload()
