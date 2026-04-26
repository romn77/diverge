from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from tradingagents.data_layout import (
    resolve_history_dir,
    resolve_reports_dir,
    resolve_screener_cache_dir,
    resolve_screener_runs_dir,
    resolve_screener_state_dir,
    resolve_screener_tasks_dir,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(PROJECT_ENV_FILE)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPORTS_DIR = resolve_reports_dir(PROJECT_ROOT)
SCREENER_RESULTS_DIR = resolve_screener_runs_dir(PROJECT_ROOT)
SCREENER_STATE_DIR = resolve_screener_state_dir(PROJECT_ROOT)
SCREENER_TASKS_DIR = resolve_screener_tasks_dir(PROJECT_ROOT)
SCREENER_CACHE_DIR = resolve_screener_cache_dir(PROJECT_ROOT)
STOCK_HISTORY_DIR = resolve_history_dir(PROJECT_ROOT)
TMP_REPORTS_DIR = REPORTS_DIR / ".tmp"

TASKS_STATE_DIRNAME = ".tasks"
ACTIVE_TASKS_DIRNAME = "active"
RECOVERED_TASK_ERROR = "Service restarted before task completion."
TERMINAL_TASK_STATUSES = {"completed", "failed", "canceled"}
SCREENER_ARTIFACT_FILENAMES = {
    "run_meta": "run_meta.json",
    "universe": "universe.csv",
    "features": "features.csv",
    "filtered_out": "filtered_out.csv",
    "candidates": "candidates.csv",
    "llm_pool": "llm_pool.json",
}


def get_frontend_origins() -> list[str]:
    raw_value = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
    origins = [origin.strip() for origin in raw_value.split(",") if origin.strip()]
    return origins or ["http://localhost:3000"]


def tmp_reports_dir() -> Path:
    return TMP_REPORTS_DIR
