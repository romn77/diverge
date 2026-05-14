from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from diverge.config.paths import (
    default_manifest_path as default_manifest_path,
    get_data_paths,
    resolve_manifest_path as _resolve_manifest_path,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(PROJECT_ENV_FILE)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_PATHS = get_data_paths(PROJECT_ROOT)
REPORTS_DIR = DATA_PATHS.reports_dir
SCREENER_RESULTS_DIR = DATA_PATHS.screener_runs_dir
SCREENER_STATE_DIR = DATA_PATHS.screener_state_dir
SCREENER_TASKS_DIR = DATA_PATHS.screener_tasks_dir
SCREENER_CACHE_DIR = DATA_PATHS.screener_cache_dir
STOCK_HISTORY_DIR = DATA_PATHS.history_dir
FUNDAMENTALS_DIR = DATA_PATHS.fundamentals_dir
MANIFEST_DIR = DATA_PATHS.manifest_dir
TMP_REPORTS_DIR = DATA_PATHS.tmp_reports_dir

TASKS_STATE_DIRNAME = ".tasks"
ACTIVE_TASKS_DIRNAME = "active"
RECOVERED_TASK_ERROR = "Service restarted before task completion."
TERMINAL_TASK_STATUSES = {"completed", "failed", "canceled"}
SCREENER_ARTIFACT_FILENAMES = {
    "run_meta": "run_meta.json",
    "universe": "universe.csv",
    "features": "features.csv",
    "filtered_out": "filtered_out.csv",
    "pruned_symbols": "pruned_symbols.csv",
    "candidates": "candidates.csv",
    "llm_pool": "llm_pool.json",
}

DEFAULT_FRONTEND_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def resolve_manifest_path(
    market: str,
    project_root: Path | None = None,
    *,
    require_exists: bool = False,
) -> Path | None:
    return _resolve_manifest_path(
        market,
        project_root,
        require_exists=require_exists,
    )


def get_frontend_origins() -> list[str]:
    raw_value = os.environ.get("FRONTEND_ORIGIN")
    if raw_value is None:
        return list(DEFAULT_FRONTEND_ORIGINS)
    origins = [origin.strip() for origin in raw_value.split(",") if origin.strip()]
    return origins or list(DEFAULT_FRONTEND_ORIGINS)


def tmp_reports_dir() -> Path:
    return TMP_REPORTS_DIR
