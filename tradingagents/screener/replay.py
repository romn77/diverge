from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .filters import HARD_FILTER_DROP_REASONS, apply_hard_filters
from .schema import ScreenRunConfig


COMPARISON_COLUMNS = ("symbol", "market", "drop_reason")


@dataclass(slots=True)
class HardFilterReplayResult:
    run_dir: Path
    features_count: int
    kept_count: int
    replay_filtered_count_by_reason: dict[str, int]
    saved_filtered_count_by_reason: dict[str, int]
    new_drops: list[dict] = field(default_factory=list)
    missing_drops: list[dict] = field(default_factory=list)
    saved_filtered_out_present: bool = False
    exported_filtered_out_path: Path | None = None

    @property
    def matches_saved(self) -> bool:
        return not self.new_drops and not self.missing_drops


def _count_by_reason(df: pd.DataFrame) -> dict[str, int]:
    if df.empty or "drop_reason" not in df.columns:
        return {}
    return {
        str(key): int(value)
        for key, value in df["drop_reason"].value_counts().sort_index().to_dict().items()
    }


def _resolve_artifact_path(
    run_dir: Path,
    run_meta: dict,
    artifact_key: str,
    filename: str,
    *,
    required: bool = True,
) -> Path | None:
    candidates: list[Path] = [run_dir / filename]
    artifact_path = run_meta.get("artifact_paths", {}).get(artifact_key)
    if artifact_path:
        candidate = Path(str(artifact_path)).expanduser()
        if not candidate.is_absolute():
            candidate = run_dir / candidate
        candidates.append(candidate)

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.is_file():
            return candidate

    if required:
        raise FileNotFoundError(f"Missing {filename} in screener run: {run_dir}")
    return None


def _load_run_meta(run_dir: Path) -> dict:
    run_meta_path = run_dir / "run_meta.json"
    if not run_meta_path.is_file():
        raise FileNotFoundError(f"Missing run_meta.json in screener run: {run_dir}")
    try:
        return json.loads(run_meta_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to read run_meta.json: {exc}") from exc


def _load_config(run_meta: dict) -> ScreenRunConfig:
    config_payload = run_meta.get("config")
    if not isinstance(config_payload, dict):
        raise ValueError("run_meta.json is missing a valid config snapshot")
    try:
        return ScreenRunConfig(**config_payload)
    except TypeError as exc:
        raise ValueError(f"run_meta.json config snapshot is invalid: {exc}") from exc


def _hard_filter_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "drop_reason" not in df.columns:
        return pd.DataFrame(columns=list(df.columns))
    return df[df["drop_reason"].isin(HARD_FILTER_DROP_REASONS)].copy()


def _comparison_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    available_columns = [column for column in COMPARISON_COLUMNS if column in df.columns]
    if not available_columns:
        return []

    comparable = df.loc[:, available_columns].copy()
    for column in available_columns:
        comparable[column] = comparable[column].fillna("").astype(str)

    comparable = comparable.drop_duplicates().sort_values(available_columns).reset_index(drop=True)
    return comparable.to_dict(orient="records")


def _comparison_key(record: dict) -> tuple[str, ...]:
    return tuple(str(record[column]) for column in COMPARISON_COLUMNS if column in record)


def replay_screen_hard_filters(
    run_dir: str | Path,
    *,
    export_filtered_out_path: str | Path | None = None,
) -> HardFilterReplayResult:
    resolved_run_dir = Path(run_dir).expanduser().resolve()
    if not resolved_run_dir.is_dir():
        raise FileNotFoundError(f"Screener run directory not found: {resolved_run_dir}")

    run_meta = _load_run_meta(resolved_run_dir)
    config = _load_config(run_meta)

    features_path = _resolve_artifact_path(resolved_run_dir, run_meta, "features", "features.csv")
    assert features_path is not None
    features_df = pd.read_csv(features_path)

    kept_df, replay_filtered_out_df = apply_hard_filters(features_df, config)

    filtered_out_path = _resolve_artifact_path(
        resolved_run_dir,
        run_meta,
        "filtered_out",
        "filtered_out.csv",
        required=False,
    )
    if filtered_out_path is not None:
        saved_filtered_out_df = pd.read_csv(filtered_out_path)
        saved_hard_filter_df = _hard_filter_rows(saved_filtered_out_df)
        saved_filtered_out_present = True
    else:
        saved_hard_filter_df = pd.DataFrame(columns=list(replay_filtered_out_df.columns))
        saved_filtered_out_present = False

    if saved_filtered_out_present:
        replay_records = _comparison_records(replay_filtered_out_df)
        saved_records = _comparison_records(saved_hard_filter_df)

        replay_keys = {_comparison_key(record) for record in replay_records}
        saved_keys = {_comparison_key(record) for record in saved_records}
        replay_by_key = {_comparison_key(record): record for record in replay_records}
        saved_by_key = {_comparison_key(record): record for record in saved_records}

        new_drops = [replay_by_key[key] for key in sorted(replay_keys - saved_keys)]
        missing_drops = [saved_by_key[key] for key in sorted(saved_keys - replay_keys)]
    else:
        new_drops = []
        missing_drops = []

    exported_filtered_out_path: Path | None = None
    if export_filtered_out_path is not None:
        exported_filtered_out_path = Path(export_filtered_out_path).expanduser()
        exported_filtered_out_path.parent.mkdir(parents=True, exist_ok=True)
        replay_filtered_out_df.to_csv(exported_filtered_out_path, index=False)

    return HardFilterReplayResult(
        run_dir=resolved_run_dir,
        features_count=int(len(features_df)),
        kept_count=int(len(kept_df)),
        replay_filtered_count_by_reason=_count_by_reason(replay_filtered_out_df),
        saved_filtered_count_by_reason=_count_by_reason(saved_hard_filter_df),
        new_drops=new_drops,
        missing_drops=missing_drops,
        saved_filtered_out_present=saved_filtered_out_present,
        exported_filtered_out_path=exported_filtered_out_path,
    )
