from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from diverge.common.json_io import write_json_atomic
from diverge.config.paths import resolve_data_dir


def opportunity_runs_dir(project_root: Path | None = None) -> Path:
    return (resolve_data_dir(project_root) / "opportunity" / "runs").resolve()


def prepare_run_dir(run_id: str, *, project_root: Path | None = None) -> Path:
    run_dir = opportunity_runs_dir(project_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    try:
        import numpy as np  # type: ignore

        if isinstance(value, np.generic):
            return _json_safe(value.item())
    except Exception:
        pass
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, _json_safe(payload))
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_ndjson(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
    return path


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_table(path: Path, frame: pd.DataFrame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        try:
            frame.to_parquet(path, index=False)
            return path
        except Exception:
            fallback = path.with_suffix(".csv")
            frame.to_csv(fallback, index=False)
            return fallback
    frame.to_csv(path, index=False)
    return path


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def artifact_manifest(run_dir: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in sorted(run_dir.iterdir() if run_dir.is_dir() else []):
        if path.is_file():
            manifest[path.stem] = path.name
    return manifest
