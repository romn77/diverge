from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_DATA_DIR = "./data"
DEFAULT_EVAL_RESULTS_DIR = f"{DEFAULT_DATA_DIR}/eval_results"
DEFAULT_REPORTS_DIR = f"{DEFAULT_DATA_DIR}/reports"
DEFAULT_SCREENER_RUNS_DIR = f"{DEFAULT_DATA_DIR}/screener/runs"
DEFAULT_SCREENER_STATE_DIR = f"{DEFAULT_DATA_DIR}/screener/state"
DEFAULT_SCREENER_TASKS_DIR = f"{DEFAULT_DATA_DIR}/screener/tasks"
DEFAULT_SCREENER_CACHE_DIR = f"{DEFAULT_DATA_DIR}/cache/screener"
DEFAULT_HISTORY_DIR = f"{DEFAULT_DATA_DIR}/history"
DEFAULT_FUNDAMENTALS_DIR = f"{DEFAULT_DATA_DIR}/fundamentals"
DEFAULT_MANIFEST_DIR = f"{DEFAULT_DATA_DIR}/manifest"
DEFAULT_DATA_CACHE_DIR = f"{DEFAULT_DATA_DIR}/data_cache"
DEFAULT_DATA_SOURCE_USAGE_PATH = f"{DEFAULT_DATA_DIR}/data_source_usage.json"


def _resolve_project_root(project_root: Path | None = None) -> Path:
    if project_root is not None:
        return Path(project_root).resolve()
    return PROJECT_ROOT.resolve()


def resolve_data_dir(project_root: Path | None = None) -> Path:
    configured = os.environ.get("DATA_DIR")
    if configured:
        return Path(configured).resolve()
    return (_resolve_project_root(project_root) / "data").resolve()


def _data_path(project_root: Path | None, *parts: str) -> Path:
    return resolve_data_dir(project_root).joinpath(*parts).resolve()


def resolve_reports_dir(project_root: Path | None = None) -> Path:
    return _data_path(project_root, "reports")


def resolve_eval_results_dir(project_root: Path | None = None) -> Path:
    return _data_path(project_root, "eval_results")


def resolve_screener_runs_dir(project_root: Path | None = None) -> Path:
    return _data_path(project_root, "screener", "runs")


def resolve_screener_state_dir(project_root: Path | None = None) -> Path:
    return _data_path(project_root, "screener", "state")


def resolve_screener_tasks_dir(project_root: Path | None = None) -> Path:
    return _data_path(project_root, "screener", "tasks")


def resolve_screener_cache_dir(project_root: Path | None = None) -> Path:
    return _data_path(project_root, "cache", "screener")


def resolve_history_dir(project_root: Path | None = None) -> Path:
    return _data_path(project_root, "history")


def resolve_fundamentals_dir(project_root: Path | None = None) -> Path:
    return _data_path(project_root, "fundamentals")


def resolve_manifest_dir(project_root: Path | None = None) -> Path:
    return _data_path(project_root, "manifest")


def resolve_tmp_reports_dir(project_root: Path | None = None) -> Path:
    return (resolve_reports_dir(project_root) / ".tmp").resolve()


def resolve_data_cache_dir(project_root: Path | None = None) -> Path:
    return _data_path(project_root, "data_cache")


def resolve_data_source_usage_path(project_root: Path | None = None) -> Path:
    return _data_path(project_root, "data_source_usage.json")


def default_manifest_path(market: str, project_root: Path | None = None) -> Path:
    normalized_market = str(market).strip().lower()
    if normalized_market not in {"cn", "us"}:
        raise ValueError("market must be one of cn or us")
    return (resolve_manifest_dir(project_root) / f"{normalized_market}.csv").resolve()


def resolve_manifest_path(
    market: str,
    project_root: Path | None = None,
    *,
    require_exists: bool = False,
) -> Path | None:
    normalized_market = str(market).strip().lower()
    env_name = f"SCREEN_{normalized_market.upper()}_MANIFEST_PATH"
    configured = os.environ.get(env_name)
    if configured and configured.strip():
        configured_path = Path(configured).resolve()
        if require_exists and not configured_path.is_file():
            return None
        return configured_path

    default_path = default_manifest_path(normalized_market, project_root)
    if default_path.is_file():
        return default_path
    return None


@dataclass(frozen=True, slots=True)
class DataPaths:
    data_dir: Path
    reports_dir: Path
    tmp_reports_dir: Path
    eval_results_dir: Path
    screener_runs_dir: Path
    screener_state_dir: Path
    screener_tasks_dir: Path
    screener_cache_dir: Path
    history_dir: Path
    fundamentals_dir: Path
    manifest_dir: Path
    cn_manifest_path: Path
    us_manifest_path: Path
    data_cache_dir: Path
    data_source_usage_path: Path
    storage_local_root: Path


def get_data_paths(project_root: Path | None = None) -> DataPaths:
    data_dir = resolve_data_dir(project_root)
    reports_dir = (data_dir / "reports").resolve()
    manifest_dir = (data_dir / "manifest").resolve()
    return DataPaths(
        data_dir=data_dir,
        reports_dir=reports_dir,
        tmp_reports_dir=(reports_dir / ".tmp").resolve(),
        eval_results_dir=(data_dir / "eval_results").resolve(),
        screener_runs_dir=(data_dir / "screener" / "runs").resolve(),
        screener_state_dir=(data_dir / "screener" / "state").resolve(),
        screener_tasks_dir=(data_dir / "screener" / "tasks").resolve(),
        screener_cache_dir=(data_dir / "cache" / "screener").resolve(),
        history_dir=(data_dir / "history").resolve(),
        fundamentals_dir=(data_dir / "fundamentals").resolve(),
        manifest_dir=manifest_dir,
        cn_manifest_path=(manifest_dir / "cn.csv").resolve(),
        us_manifest_path=(manifest_dir / "us.csv").resolve(),
        data_cache_dir=(data_dir / "data_cache").resolve(),
        data_source_usage_path=(data_dir / "data_source_usage.json").resolve(),
        storage_local_root=data_dir,
    )


__all__ = [
    "DEFAULT_DATA_DIR",
    "DEFAULT_DATA_CACHE_DIR",
    "DEFAULT_DATA_SOURCE_USAGE_PATH",
    "DEFAULT_EVAL_RESULTS_DIR",
    "DEFAULT_HISTORY_DIR",
    "DEFAULT_FUNDAMENTALS_DIR",
    "DEFAULT_MANIFEST_DIR",
    "DEFAULT_REPORTS_DIR",
    "DEFAULT_SCREENER_CACHE_DIR",
    "DEFAULT_SCREENER_RUNS_DIR",
    "DEFAULT_SCREENER_STATE_DIR",
    "DEFAULT_SCREENER_TASKS_DIR",
    "DataPaths",
    "default_manifest_path",
    "get_data_paths",
    "resolve_data_cache_dir",
    "resolve_data_dir",
    "resolve_data_source_usage_path",
    "resolve_eval_results_dir",
    "resolve_history_dir",
    "resolve_fundamentals_dir",
    "resolve_manifest_dir",
    "resolve_manifest_path",
    "resolve_reports_dir",
    "resolve_screener_cache_dir",
    "resolve_screener_runs_dir",
    "resolve_screener_state_dir",
    "resolve_screener_tasks_dir",
    "resolve_tmp_reports_dir",
]
