from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DATA_DIR = "./data"
DEFAULT_EVAL_RESULTS_DIR = f"{DEFAULT_DATA_DIR}/eval_results"
DEFAULT_REPORTS_DIR = f"{DEFAULT_DATA_DIR}/reports"
DEFAULT_SCREENER_RUNS_DIR = f"{DEFAULT_DATA_DIR}/screener/runs"
DEFAULT_SCREENER_STATE_DIR = f"{DEFAULT_DATA_DIR}/screener/state"
DEFAULT_SCREENER_TASKS_DIR = f"{DEFAULT_DATA_DIR}/screener/tasks"
DEFAULT_SCREENER_CACHE_DIR = f"{DEFAULT_DATA_DIR}/cache/screener"
DEFAULT_HISTORY_DIR = f"{DEFAULT_DATA_DIR}/history"
DEFAULT_FUNDAMENTALS_DIR = f"{DEFAULT_DATA_DIR}/fundamentals"


def _resolve_project_root(project_root: Path | None = None) -> Path:
    if project_root is not None:
        return Path(project_root).resolve()
    return PROJECT_ROOT.resolve()


def resolve_data_dir(project_root: Path | None = None) -> Path:
    configured = os.environ.get("DATA_DIR")
    if configured:
        return Path(configured).resolve()
    return (_resolve_project_root(project_root) / "data").resolve()


def resolve_reports_dir(project_root: Path | None = None) -> Path:
    configured = os.environ.get("REPORTS_DIR")
    if configured:
        return Path(configured).resolve()
    return (resolve_data_dir(project_root) / "reports").resolve()


def resolve_eval_results_dir(project_root: Path | None = None) -> Path:
    configured = os.environ.get("DIVERGE_EVAL_RESULTS_DIR")
    if configured:
        return Path(configured).resolve()
    return (resolve_data_dir(project_root) / "eval_results").resolve()


def resolve_screener_runs_dir(project_root: Path | None = None) -> Path:
    configured = os.environ.get("SCREENER_RUNS_DIR")
    if configured:
        return Path(configured).resolve()
    return (resolve_data_dir(project_root) / "screener" / "runs").resolve()


def resolve_screener_state_dir(project_root: Path | None = None) -> Path:
    configured = os.environ.get("SCREENER_STATE_DIR")
    if configured:
        return Path(configured).resolve()
    return (resolve_data_dir(project_root) / "screener" / "state").resolve()


def resolve_screener_tasks_dir(project_root: Path | None = None) -> Path:
    configured = os.environ.get("SCREENER_TASKS_DIR")
    if configured:
        return Path(configured).resolve()
    return (resolve_data_dir(project_root) / "screener" / "tasks").resolve()


def resolve_screener_cache_dir(project_root: Path | None = None) -> Path:
    configured = os.environ.get("SCREENER_CACHE_DIR")
    if configured:
        return Path(configured).resolve()
    return (resolve_data_dir(project_root) / "cache" / "screener").resolve()


def resolve_history_dir(project_root: Path | None = None) -> Path:
    configured = os.environ.get("STOCK_HISTORY_DIR")
    if configured:
        return Path(configured).resolve()
    return (resolve_data_dir(project_root) / "history").resolve()


def resolve_fundamentals_dir(project_root: Path | None = None) -> Path:
    configured = os.environ.get("FUNDAMENTALS_DIR")
    if configured:
        return Path(configured).resolve()
    return (resolve_data_dir(project_root) / "fundamentals").resolve()


__all__ = [
    "DEFAULT_DATA_DIR",
    "DEFAULT_EVAL_RESULTS_DIR",
    "DEFAULT_HISTORY_DIR",
    "DEFAULT_FUNDAMENTALS_DIR",
    "DEFAULT_REPORTS_DIR",
    "DEFAULT_SCREENER_CACHE_DIR",
    "DEFAULT_SCREENER_RUNS_DIR",
    "DEFAULT_SCREENER_STATE_DIR",
    "DEFAULT_SCREENER_TASKS_DIR",
    "resolve_data_dir",
    "resolve_eval_results_dir",
    "resolve_history_dir",
    "resolve_fundamentals_dir",
    "resolve_reports_dir",
    "resolve_screener_cache_dir",
    "resolve_screener_runs_dir",
    "resolve_screener_state_dir",
    "resolve_screener_tasks_dir",
]
