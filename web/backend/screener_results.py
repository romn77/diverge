from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import HTTPException

from web.backend import access, app_config, auth, screener_runs

DEFAULT_SCREENER_KEY = "default"
WORKSPACE_OWNER_KEY = "_workspace"
CURRENT_SNAPSHOT_SLOT = "current"
PREVIOUS_SNAPSHOT_SLOT = "previous"
RECENT_RUN_LIMIT = 20
SUMMARY_TEMPLATE = {
    "entered_symbols": [],
    "exited_symbols": [],
    "rank_changed_symbols": [],
    "unchanged": 0,
}

_LOGIC_VERSION: str | None = None
_OBSERVABILITY_LOCK = Lock()
_OBSERVABILITY: dict[str, Any] = {
    "migration_seed_count": 0,
    "snapshot_rotation_total": 0,
    "hash_canonicalization_error_total": 0,
    "legacy_read_total": {
        "migration": 0,
        "admin": 0,
        "archive": 0,
        "online": 0,
    },
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_timestamp(value: datetime | None = None) -> str:
    candidate = value or _utcnow()
    return candidate.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_run_timestamp(value: datetime | None = None) -> str:
    candidate = value or _utcnow()
    return candidate.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _normalize_markets(value: list[str] | tuple[str, ...] | None) -> list[str]:
    if not value:
        return []
    normalized: list[str] = []
    for market in value:
        candidate = str(market).strip().lower()
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _normalize_reason_counts(value: dict[str, Any] | None) -> dict[str, int]:
    if not value:
        return {}
    normalized: dict[str, int] = {}
    for key, raw_count in value.items():
        name = str(key).strip()
        if not name:
            continue
        try:
            normalized[name] = int(raw_count)
        except (TypeError, ValueError):
            continue
    return normalized


def _normalize_artifact_paths(value: dict[str, Any] | None) -> dict[str, str]:
    if not value:
        return {}
    normalized: dict[str, str] = {}
    for key, raw_path in value.items():
        artifact_key = str(key).strip()
        artifact_path = str(raw_path).strip() if raw_path is not None else ""
        if artifact_key and artifact_path:
            normalized[artifact_key] = artifact_path
    return normalized


def _normalize_summary(value: dict[str, Any] | None) -> dict[str, Any]:
    normalized = deepcopy(SUMMARY_TEMPLATE)
    if not value:
        return normalized
    for key in ("entered_symbols", "exited_symbols", "rank_changed_symbols"):
        normalized[key] = [str(item) for item in value.get(key, []) if str(item).strip()]
    try:
        normalized["unchanged"] = int(value.get("unchanged", 0) or 0)
    except (TypeError, ValueError):
        normalized["unchanged"] = 0
    return normalized


def _normalize_snapshot_slot(value: str | None) -> str | None:
    candidate = _normalize_text(value)
    if candidate in {CURRENT_SNAPSHOT_SLOT, PREVIOUS_SNAPSHOT_SLOT}:
        return candidate
    return None


def _coerce_csv_value(value: str | None) -> Any:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if lowered.startswith("0") and lowered != "0" and not any(ch in lowered for ch in ".e"):
            raise ValueError
        return int(candidate)
    except ValueError:
        try:
            return float(candidate)
        except ValueError:
            return candidate


def _read_candidate_rows(candidates_path: Path) -> list[dict[str, Any]]:
    with candidates_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, Any]] = []
        for raw_row in reader:
            row = {str(key): _coerce_csv_value(value) for key, value in raw_row.items() if key}
            rows.append(row)
        return rows


def _row_symbol(row: dict[str, Any]) -> str:
    return str(row.get("symbol") or "").strip()


def _row_rank(row: dict[str, Any]) -> int:
    for field_name in ("rank", "global_rank"):
        value = row.get(field_name)
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _increment_migration_seed(count: int) -> None:
    if count <= 0:
        return
    with _OBSERVABILITY_LOCK:
        _OBSERVABILITY["migration_seed_count"] += count


def _increment_hash_canonicalization_error() -> None:
    with _OBSERVABILITY_LOCK:
        _OBSERVABILITY["hash_canonicalization_error_total"] += 1


def _row_fingerprint(row: dict[str, Any]) -> str:
    return json.dumps(_canonicalize_row(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


_MISSING = object()


def _canonical_decimal_string(value: Any) -> str:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Cannot canonicalize numeric value {value!r}") from exc
    if not decimal_value.is_finite():
        raise ValueError(f"Numeric value must be finite: {value!r}")
    normalized = decimal_value.normalize()
    if normalized == 0:
        return "0"
    rendered = format(normalized, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _canonicalize_value(value: Any) -> Any:
    if value is None:
        return _MISSING
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, Decimal)):
        try:
            return _canonical_decimal_string(value)
        except ValueError:
            _increment_hash_canonicalization_error()
            return str(value)
    if isinstance(value, dict):
        canonical: dict[str, Any] = {}
        for key in sorted(value):
            normalized = _canonicalize_value(value[key])
            if normalized is _MISSING:
                continue
            canonical[str(key)] = normalized
        return canonical
    if isinstance(value, (list, tuple, set)):
        normalized_items = []
        for item in value:
            normalized = _canonicalize_value(item)
            if normalized is _MISSING:
                continue
            normalized_items.append(normalized)
        return normalized_items
    _increment_hash_canonicalization_error()
    return repr(value)


def _canonicalize_row(row: dict[str, Any]) -> dict[str, Any]:
    canonical: dict[str, Any] = {}
    for key in sorted(row):
        if key == "matched_reason_codes":
            raw_codes = row.get(key) or []
            normalized_codes = sorted(
                {
                    str(code).strip()
                    for code in raw_codes
                    if str(code).strip()
                }
            )
            if normalized_codes:
                canonical[key] = normalized_codes
            continue
        if key == "display_metrics":
            normalized_metrics = _canonicalize_value(row.get(key) or {})
            if normalized_metrics:
                canonical[key] = normalized_metrics
            continue
        normalized = _canonicalize_value(row.get(key))
        if normalized is _MISSING:
            continue
        canonical[key] = normalized
    return canonical


def canonicalize_result_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_rows = [_canonicalize_row(dict(row)) for row in rows]
    return sorted(
        normalized_rows,
        key=lambda row: (
            str(row.get("symbol") or ""),
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        ),
    )


def result_hash(rows: list[dict[str, Any]]) -> str:
    try:
        normalized_rows = canonicalize_result_rows(rows)
        payload = json.dumps(
            normalized_rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except Exception:
        _increment_hash_canonicalization_error()
        payload = json.dumps(
            rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=repr,
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _result_hash(rows: list[dict[str, Any]]) -> str:
    return result_hash(rows)


def _resolve_logic_version() -> str:
    global _LOGIC_VERSION
    if _LOGIC_VERSION is not None:
        return _LOGIC_VERSION

    configured = _normalize_text(os.environ.get("SCREENER_LOGIC_VERSION"))
    if configured:
        _LOGIC_VERSION = configured
        return _LOGIC_VERSION

    try:
        completed = subprocess.run(
            ["git", "-C", str(app_config.PROJECT_ROOT), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        _LOGIC_VERSION = completed.stdout.strip() or "unknown"
    except Exception:
        _LOGIC_VERSION = "unknown"
    return _LOGIC_VERSION


def _manifest_version(config_payload: dict[str, Any]) -> str | None:
    manifest_paths = [
        _normalize_text(config_payload.get("cn_manifest_path")),
        _normalize_text(config_payload.get("us_manifest_path")),
    ]
    digest_parts: list[str] = []
    for manifest_path in manifest_paths:
        if not manifest_path:
            continue
        path = Path(manifest_path)
        if not path.is_file():
            digest_parts.append(manifest_path)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        digest_parts.append(f"{path.name}:{digest}")
    if not digest_parts:
        return None
    return "|".join(digest_parts)


def _build_summary(
    current_rows: list[dict[str, Any]],
    previous_rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if not previous_rows:
        return deepcopy(SUMMARY_TEMPLATE)

    current_by_symbol = {
        symbol: row for row in current_rows if (symbol := _row_symbol(row))
    }
    previous_by_symbol = {
        symbol: row for row in previous_rows if (symbol := _row_symbol(row))
    }

    current_symbols = set(current_by_symbol)
    previous_symbols = set(previous_by_symbol)

    entered_symbols = sorted(current_symbols - previous_symbols)
    exited_symbols = sorted(previous_symbols - current_symbols)

    rank_changed_symbols: list[str] = []
    unchanged = 0
    for symbol in sorted(current_symbols & previous_symbols):
        current_row = current_by_symbol[symbol]
        previous_row = previous_by_symbol[symbol]
        if _row_rank(current_row) != _row_rank(previous_row):
            rank_changed_symbols.append(symbol)
        elif _row_fingerprint(current_row) == _row_fingerprint(previous_row):
            unchanged += 1

    return {
        "entered_symbols": entered_symbols,
        "exited_symbols": exited_symbols,
        "rank_changed_symbols": rank_changed_symbols,
        "unchanged": unchanged,
    }


def _owner_directory(owner_user_id: str | None) -> str:
    return owner_user_id or WORKSPACE_OWNER_KEY


def resolve_screener_result_state_path(
    owner_user_id: str | None = None,
    screener_key: str = DEFAULT_SCREENER_KEY,
) -> Path:
    return app_config.SCREENER_STATE_DIR / _owner_directory(owner_user_id) / f"{screener_key}.json"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{hashlib.sha1(path.as_posix().encode()).hexdigest()}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _increment_legacy_read(context: str) -> None:
    with _OBSERVABILITY_LOCK:
        legacy_counts = _OBSERVABILITY["legacy_read_total"]
        legacy_counts[context] = legacy_counts.get(context, 0) + 1


def _increment_snapshot_rotation() -> None:
    with _OBSERVABILITY_LOCK:
        _OBSERVABILITY["snapshot_rotation_total"] += 1


def reset_screener_result_observability() -> None:
    with _OBSERVABILITY_LOCK:
        _OBSERVABILITY["migration_seed_count"] = 0
        _OBSERVABILITY["snapshot_rotation_total"] = 0
        _OBSERVABILITY["hash_canonicalization_error_total"] = 0
        _OBSERVABILITY["legacy_read_total"] = {
            "migration": 0,
            "admin": 0,
            "archive": 0,
            "online": 0,
        }


def get_screener_result_observability() -> dict[str, Any]:
    with _OBSERVABILITY_LOCK:
        return deepcopy(_OBSERVABILITY)


@dataclass(slots=True)
class ScreenerRunMetadata:
    id: str
    generated_at: str
    as_of_date: str | None = None
    markets: list[str] = field(default_factory=list)
    candidate_count: int = 0
    match_count: int = 0
    universe_count: int = 0
    status: str = "success"
    owner_user_id: str | None = None
    screener_key: str = DEFAULT_SCREENER_KEY
    manifest_version: str | None = None
    logic_version: str | None = None
    duration_ms: int | None = None
    filtered_count_by_reason: dict[str, int] = field(default_factory=dict)
    artifact_paths: dict[str, str] = field(default_factory=dict)
    result_hash: str = ""
    error_summary: str | None = None
    snapshot_slot: str | None = None
    snapshot_available: bool = False
    source_legacy_run_id: str | None = None


@dataclass(slots=True)
class ScreenerResultSnapshot:
    slot: str
    source_run_id: str
    generated_at: str
    updated_at: str
    source_legacy_run_id: str | None = None
    as_of_date: str | None = None
    markets: list[str] = field(default_factory=list)
    candidate_count: int = 0
    match_count: int = 0
    universe_count: int = 0
    duration_ms: int | None = None
    filtered_count_by_reason: dict[str, int] = field(default_factory=dict)
    artifact_paths: dict[str, str] = field(default_factory=dict)
    rows: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=lambda: deepcopy(SUMMARY_TEMPLATE))
    result_hash: str = ""
    manifest_version: str | None = None
    logic_version: str | None = None


@dataclass(slots=True)
class ScreenerResultState:
    screener_key: str = DEFAULT_SCREENER_KEY
    owner_user_id: str | None = None
    updated_at: str = field(default_factory=_serialize_timestamp)
    current_result: ScreenerResultSnapshot | None = None
    previous_result: ScreenerResultSnapshot | None = None
    recent_runs: list[ScreenerRunMetadata] = field(default_factory=list)


@dataclass(slots=True)
class LegacyScreenerRun:
    run_id: str
    generated_at: str
    as_of_date: str | None
    markets: list[str]
    universe_count: int
    candidate_count: int
    duration_ms: int | None
    filtered_count_by_reason: dict[str, int]
    artifact_paths: dict[str, str]
    rows: list[dict[str, Any]]
    owner_user_id: str | None
    manifest_version: str | None
    logic_version: str
    result_hash: str


@dataclass(slots=True)
class ScreenerResultCandidate:
    source_run_id: str
    generated_at: str
    source_legacy_run_id: str | None = None
    as_of_date: str | None = None
    markets: list[str] = field(default_factory=list)
    universe_count: int = 0
    match_count: int = 0
    filtered_count_by_reason: dict[str, int] = field(default_factory=dict)
    artifact_paths: dict[str, str] = field(default_factory=dict)
    rows: list[dict[str, Any]] = field(default_factory=list)
    manifest_version: str | None = None
    logic_version: str | None = None
    duration_ms: int | None = None
    result_hash: str = ""
    run_dir: Path | None = None

    def __post_init__(self) -> None:
        self.markets = _normalize_markets(self.markets)
        self.universe_count = max(int(self.universe_count or 0), 0)
        self.match_count = max(int(self.match_count or len(self.rows)), 0)
        self.filtered_count_by_reason = _normalize_reason_counts(self.filtered_count_by_reason)
        self.artifact_paths = _normalize_artifact_paths(self.artifact_paths)
        self.source_legacy_run_id = _normalize_text(self.source_legacy_run_id) or self.source_run_id
        if self.duration_ms is not None:
            self.duration_ms = max(int(self.duration_ms), 0)
        self.result_hash = self.result_hash or result_hash(self.rows)


def _snapshot_from_payload(
    payload: dict[str, Any] | None,
    *,
    slot: str,
) -> ScreenerResultSnapshot | None:
    if not payload:
        return None
    return ScreenerResultSnapshot(
        slot=slot,
        source_run_id=str(payload.get("source_run_id") or ""),
        source_legacy_run_id=_normalize_text(payload.get("source_legacy_run_id"))
        or str(payload.get("source_run_id") or ""),
        generated_at=str(payload.get("generated_at") or ""),
        updated_at=str(payload.get("updated_at") or _serialize_timestamp()),
        as_of_date=_normalize_text(payload.get("as_of_date")),
        markets=_normalize_markets(payload.get("markets")),
        candidate_count=max(int(payload.get("candidate_count") or 0), 0),
        match_count=max(int(payload.get("match_count") or payload.get("candidate_count") or 0), 0),
        universe_count=max(int(payload.get("universe_count") or 0), 0),
        duration_ms=(
            max(int(payload.get("duration_ms")), 0)
            if payload.get("duration_ms") is not None
            else None
        ),
        filtered_count_by_reason=_normalize_reason_counts(payload.get("filtered_count_by_reason")),
        artifact_paths=_normalize_artifact_paths(payload.get("artifact_paths")),
        rows=list(payload.get("rows") or []),
        summary=(
            deepcopy(SUMMARY_TEMPLATE)
            if slot == PREVIOUS_SNAPSHOT_SLOT
            else _normalize_summary(payload.get("summary"))
        ),
        result_hash=str(payload.get("result_hash") or ""),
        manifest_version=_normalize_text(payload.get("manifest_version")),
        logic_version=_normalize_text(payload.get("logic_version")),
    )


def _run_metadata_from_payload(payload: dict[str, Any] | None) -> ScreenerRunMetadata | None:
    if not payload:
        return None
    return ScreenerRunMetadata(
        id=str(payload.get("id") or ""),
        generated_at=str(payload.get("generated_at") or ""),
        as_of_date=_normalize_text(payload.get("as_of_date")),
        markets=_normalize_markets(payload.get("markets")),
        candidate_count=max(int(payload.get("candidate_count") or 0), 0),
        match_count=max(int(payload.get("match_count") or payload.get("candidate_count") or 0), 0),
        universe_count=max(int(payload.get("universe_count") or 0), 0),
        status=str(payload.get("status") or "success"),
        owner_user_id=_normalize_text(payload.get("owner_user_id")),
        screener_key=str(payload.get("screener_key") or DEFAULT_SCREENER_KEY),
        manifest_version=_normalize_text(payload.get("manifest_version")),
        logic_version=_normalize_text(payload.get("logic_version")),
        duration_ms=(
            max(int(payload.get("duration_ms")), 0)
            if payload.get("duration_ms") is not None
            else None
        ),
        filtered_count_by_reason=_normalize_reason_counts(payload.get("filtered_count_by_reason")),
        artifact_paths=_normalize_artifact_paths(payload.get("artifact_paths")),
        result_hash=str(payload.get("result_hash") or ""),
        error_summary=_normalize_text(payload.get("error_summary")),
        snapshot_slot=_normalize_text(payload.get("snapshot_slot")),
        snapshot_available=bool(payload.get("snapshot_available")),
        source_legacy_run_id=_normalize_text(payload.get("source_legacy_run_id")),
    )


def load_screener_result_state(
    owner_user_id: str | None = None,
    screener_key: str = DEFAULT_SCREENER_KEY,
) -> ScreenerResultState | None:
    state_path = resolve_screener_result_state_path(owner_user_id, screener_key)
    if not state_path.is_file():
        return None
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return ScreenerResultState(
        screener_key=str(payload.get("screener_key") or DEFAULT_SCREENER_KEY),
        owner_user_id=_normalize_text(payload.get("owner_user_id")),
        updated_at=str(payload.get("updated_at") or _serialize_timestamp()),
        current_result=_snapshot_from_payload(
            payload.get("current_result"),
            slot=CURRENT_SNAPSHOT_SLOT,
        ),
        previous_result=_snapshot_from_payload(
            payload.get("previous_result"),
            slot=PREVIOUS_SNAPSHOT_SLOT,
        ),
        recent_runs=[
            metadata
            for item in list(payload.get("recent_runs") or [])
            if (metadata := _run_metadata_from_payload(item)) is not None and metadata.id
        ],
    )


def save_screener_result_state(state: ScreenerResultState) -> None:
    state.updated_at = _serialize_timestamp()
    _write_json_atomic(
        resolve_screener_result_state_path(state.owner_user_id, state.screener_key),
        asdict(state),
    )


def _relative_screener_storage_path(path: Path) -> str:
    resolved_root = app_config.SCREENER_RESULTS_DIR.resolve()
    resolved_path = path.resolve()
    try:
        relative_path = resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError("Screener artifacts must stay under SCREENER_RESULTS_DIR") from exc
    return relative_path.as_posix()


def _build_screener_artifact_manifest(run_dir: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for artifact_key, filename in app_config.SCREENER_ARTIFACT_FILENAMES.items():
        artifact_path = run_dir / filename
        if artifact_path.is_file():
            manifest[artifact_key] = _relative_screener_storage_path(artifact_path)
    return manifest


def _read_legacy_run(run_dir: Path, owner_user_id: str | None = None) -> LegacyScreenerRun | None:
    meta_path = run_dir / "run_meta.json"
    candidates_path = run_dir / "candidates.csv"
    if not meta_path.is_file() or not candidates_path.is_file():
        return None

    _increment_legacy_read("migration")
    try:
        meta_payload = json.loads(meta_path.read_text(encoding="utf-8"))
        rows = _read_candidate_rows(candidates_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, csv.Error) as exc:
        raise RuntimeError(f"Failed to read legacy screener run '{run_dir.name}': {exc}") from exc

    config_payload = dict(meta_payload.get("config") or {})
    artifact_paths = _normalize_artifact_paths(meta_payload.get("artifact_paths"))
    if not artifact_paths:
        artifact_paths = {
            "run_meta": str(meta_path),
            "candidates": str(candidates_path),
        }

    generated_at = _normalize_text(meta_payload.get("run_timestamp")) or run_dir.name
    universe_count_by_market = dict(meta_payload.get("universe_count_by_market") or {})
    universe_count = 0
    for raw_count in universe_count_by_market.values():
        try:
            universe_count += max(int(raw_count), 0)
        except (TypeError, ValueError):
            continue
    elapsed_seconds = meta_payload.get("elapsed_seconds")
    duration_ms = None
    if elapsed_seconds is not None:
        try:
            duration_ms = max(int(float(elapsed_seconds) * 1000), 0)
        except (TypeError, ValueError):
            duration_ms = None
    return LegacyScreenerRun(
        run_id=run_dir.name,
        generated_at=generated_at,
        as_of_date=_normalize_text(meta_payload.get("as_of_date")),
        markets=_normalize_markets(config_payload.get("markets")),
        universe_count=universe_count,
        candidate_count=max(int(meta_payload.get("candidate_count") or len(rows)), 0),
        duration_ms=duration_ms,
        filtered_count_by_reason=_normalize_reason_counts(meta_payload.get("filtered_count_by_reason")),
        artifact_paths=artifact_paths,
        rows=rows,
        owner_user_id=owner_user_id,
        manifest_version=_manifest_version(config_payload),
        logic_version=_resolve_logic_version(),
        result_hash=_result_hash(rows),
    )


def _snapshot_from_legacy_run(
    legacy_run: LegacyScreenerRun,
    *,
    slot: str,
    summary: dict[str, Any] | None = None,
) -> ScreenerResultSnapshot:
    return ScreenerResultSnapshot(
        slot=slot,
        source_run_id=legacy_run.run_id,
        source_legacy_run_id=legacy_run.run_id,
        generated_at=legacy_run.generated_at,
        updated_at=_serialize_timestamp(),
        as_of_date=legacy_run.as_of_date,
        markets=list(legacy_run.markets),
        candidate_count=legacy_run.candidate_count,
        match_count=legacy_run.candidate_count,
        universe_count=legacy_run.universe_count,
        duration_ms=legacy_run.duration_ms,
        filtered_count_by_reason=dict(legacy_run.filtered_count_by_reason),
        artifact_paths=dict(legacy_run.artifact_paths),
        rows=list(legacy_run.rows),
        summary=_normalize_summary(summary),
        result_hash=legacy_run.result_hash,
        manifest_version=legacy_run.manifest_version,
        logic_version=legacy_run.logic_version,
    )


def _recent_run_from_legacy_run(
    legacy_run: LegacyScreenerRun,
    *,
    status: str = "success",
) -> ScreenerRunMetadata:
    return ScreenerRunMetadata(
        id=legacy_run.run_id,
        generated_at=legacy_run.generated_at,
        as_of_date=legacy_run.as_of_date,
        markets=list(legacy_run.markets),
        candidate_count=legacy_run.candidate_count,
        match_count=legacy_run.candidate_count,
        universe_count=legacy_run.universe_count,
        status=status,
        owner_user_id=legacy_run.owner_user_id,
        screener_key=DEFAULT_SCREENER_KEY,
        manifest_version=legacy_run.manifest_version,
        logic_version=legacy_run.logic_version,
        duration_ms=legacy_run.duration_ms,
        filtered_count_by_reason=dict(legacy_run.filtered_count_by_reason),
        artifact_paths=dict(legacy_run.artifact_paths),
        result_hash=legacy_run.result_hash,
        source_legacy_run_id=legacy_run.run_id,
    )


def _snapshot_from_candidate(
    candidate: ScreenerResultCandidate,
    *,
    slot: str,
    summary: dict[str, Any] | None = None,
) -> ScreenerResultSnapshot:
    return ScreenerResultSnapshot(
        slot=slot,
        source_run_id=candidate.source_run_id,
        source_legacy_run_id=candidate.source_legacy_run_id,
        generated_at=candidate.generated_at,
        updated_at=_serialize_timestamp(),
        as_of_date=candidate.as_of_date,
        markets=list(candidate.markets),
        candidate_count=candidate.match_count,
        match_count=candidate.match_count,
        universe_count=candidate.universe_count,
        duration_ms=candidate.duration_ms,
        filtered_count_by_reason=dict(candidate.filtered_count_by_reason),
        artifact_paths=dict(candidate.artifact_paths),
        rows=list(candidate.rows),
        summary=_normalize_summary(summary),
        result_hash=candidate.result_hash,
        manifest_version=candidate.manifest_version,
        logic_version=candidate.logic_version,
    )


def _recent_run_from_candidate(
    candidate: ScreenerResultCandidate,
    *,
    owner_user_id: str | None,
    status: str,
    error_summary: str | None = None,
) -> ScreenerRunMetadata:
    return ScreenerRunMetadata(
        id=candidate.source_run_id,
        generated_at=candidate.generated_at,
        as_of_date=candidate.as_of_date,
        markets=list(candidate.markets),
        candidate_count=candidate.match_count,
        match_count=candidate.match_count,
        universe_count=candidate.universe_count,
        status=status,
        owner_user_id=owner_user_id,
        screener_key=DEFAULT_SCREENER_KEY,
        manifest_version=candidate.manifest_version,
        logic_version=candidate.logic_version,
        duration_ms=candidate.duration_ms,
        filtered_count_by_reason=dict(candidate.filtered_count_by_reason),
        artifact_paths=dict(candidate.artifact_paths),
        result_hash=candidate.result_hash,
        source_legacy_run_id=candidate.source_legacy_run_id,
        error_summary=error_summary,
    )


def _failed_run_metadata(
    *,
    task: Any,
    owner_user_id: str | None,
    error_summary: str,
    source_run_id: str,
) -> ScreenerRunMetadata:
    request_payload = dict(getattr(task, "request_payload", {}) or {})
    config_payload = dict(getattr(task, "config_payload", {}) or {})
    as_of_date = _normalize_text(request_payload.get("as_of_date") or config_payload.get("as_of_date"))
    markets = _normalize_markets(request_payload.get("markets") or config_payload.get("markets"))
    return ScreenerRunMetadata(
        id=source_run_id,
        generated_at=_serialize_run_timestamp(),
        as_of_date=as_of_date,
        markets=markets,
        candidate_count=0,
        match_count=0,
        universe_count=0,
        status="failed",
        owner_user_id=owner_user_id,
        screener_key=DEFAULT_SCREENER_KEY,
        manifest_version=_manifest_version(config_payload),
        logic_version=_resolve_logic_version(),
        duration_ms=None,
        filtered_count_by_reason={},
        artifact_paths={},
        result_hash="",
        error_summary=error_summary,
    )


def _clear_snapshot_summary(snapshot: ScreenerResultSnapshot) -> ScreenerResultSnapshot:
    return ScreenerResultSnapshot(
        slot=PREVIOUS_SNAPSHOT_SLOT,
        source_run_id=snapshot.source_run_id,
        source_legacy_run_id=snapshot.source_legacy_run_id or snapshot.source_run_id,
        generated_at=snapshot.generated_at,
        updated_at=snapshot.updated_at,
        as_of_date=snapshot.as_of_date,
        markets=list(snapshot.markets),
        candidate_count=snapshot.candidate_count,
        match_count=snapshot.match_count,
        universe_count=snapshot.universe_count,
        duration_ms=snapshot.duration_ms,
        filtered_count_by_reason=dict(snapshot.filtered_count_by_reason),
        artifact_paths=dict(snapshot.artifact_paths),
        rows=list(snapshot.rows),
        summary=deepcopy(SUMMARY_TEMPLATE),
        result_hash=snapshot.result_hash,
        manifest_version=snapshot.manifest_version,
        logic_version=snapshot.logic_version,
    )


def _annotate_recent_runs(state: ScreenerResultState) -> None:
    current_run_id = state.current_result.source_run_id if state.current_result is not None else None
    previous_run_id = state.previous_result.source_run_id if state.previous_result is not None else None
    for recent_run in state.recent_runs:
        if current_run_id and recent_run.id == current_run_id:
            recent_run.snapshot_slot = CURRENT_SNAPSHOT_SLOT
            recent_run.snapshot_available = True
        elif previous_run_id and recent_run.id == previous_run_id:
            recent_run.snapshot_slot = PREVIOUS_SNAPSHOT_SLOT
            recent_run.snapshot_available = True
        else:
            recent_run.snapshot_slot = None
            recent_run.snapshot_available = False


def _sort_recent_runs(recent_runs: list[ScreenerRunMetadata]) -> list[ScreenerRunMetadata]:
    return sorted(
        recent_runs,
        key=lambda run: (run.generated_at or "", run.id),
        reverse=True,
    )[:RECENT_RUN_LIMIT]


def _build_state_from_legacy_runs(
    legacy_runs: list[LegacyScreenerRun],
    *,
    owner_user_id: str | None,
) -> ScreenerResultState | None:
    if not legacy_runs:
        return None

    ordered_runs = sorted(
        legacy_runs,
        key=lambda legacy_run: (legacy_run.generated_at or "", legacy_run.run_id),
        reverse=True,
    )
    current_legacy = ordered_runs[0]
    previous_legacy = ordered_runs[1] if len(ordered_runs) > 1 else None

    previous_snapshot = (
        _snapshot_from_legacy_run(previous_legacy, slot=PREVIOUS_SNAPSHOT_SLOT)
        if previous_legacy is not None
        else None
    )
    current_summary = _build_summary(
        current_legacy.rows,
        previous_snapshot.rows if previous_snapshot is not None else None,
    )
    current_snapshot = _snapshot_from_legacy_run(
        current_legacy,
        slot=CURRENT_SNAPSHOT_SLOT,
        summary=current_summary,
    )
    state = ScreenerResultState(
        owner_user_id=owner_user_id,
        current_result=current_snapshot,
        previous_result=previous_snapshot,
        recent_runs=[_recent_run_from_legacy_run(legacy_run) for legacy_run in ordered_runs[:RECENT_RUN_LIMIT]],
    )
    _increment_migration_seed(1 + int(previous_snapshot is not None))
    _annotate_recent_runs(state)
    return state


def _load_workspace_legacy_runs() -> list[LegacyScreenerRun]:
    if not app_config.SCREENER_RESULTS_DIR.is_dir():
        return []
    legacy_runs: list[LegacyScreenerRun] = []
    for entry in sorted(app_config.SCREENER_RESULTS_DIR.iterdir(), reverse=True):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        legacy_run = _read_legacy_run(entry)
        if legacy_run is not None:
            legacy_runs.append(legacy_run)
    return legacy_runs


def _load_owner_legacy_runs(owner_user_id: str) -> list[LegacyScreenerRun]:
    with auth.db_session() as db:
        records = screener_runs.list_screener_run_records(db, owner_user_id=owner_user_id)

    legacy_runs: list[LegacyScreenerRun] = []
    for record in records:
        run_dir = app_config.SCREENER_RESULTS_DIR / record.storage_path
        if not run_dir.is_dir():
            continue
        legacy_run = _read_legacy_run(run_dir, owner_user_id=record.owner_user_id)
        if legacy_run is not None:
            legacy_runs.append(legacy_run)
    return legacy_runs


def migrate_legacy_screener_results(
    owner_user_id: str | None = None,
    *,
    screener_key: str = DEFAULT_SCREENER_KEY,
    force: bool = False,
) -> ScreenerResultState | None:
    if not force:
        existing = load_screener_result_state(owner_user_id, screener_key)
        if existing is not None:
            return existing

    if auth.get_auth_settings().enabled and owner_user_id:
        legacy_runs = _load_owner_legacy_runs(owner_user_id)
    else:
        legacy_runs = _load_workspace_legacy_runs()

    state = _build_state_from_legacy_runs(legacy_runs, owner_user_id=owner_user_id)
    if state is not None:
        save_screener_result_state(state)
    return state


def migrate_all_legacy_screener_results(force: bool = False) -> int:
    app_config.SCREENER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    migrated = 0
    if not auth.get_auth_settings().enabled:
        if migrate_legacy_screener_results(force=force) is not None:
            migrated += 1
        return migrated

    with auth.db_session() as db:
        records = screener_runs.list_screener_run_records(db)

    owner_user_ids = sorted({record.owner_user_id for record in records if record.owner_user_id})
    for owner_user_id in owner_user_ids:
        if migrate_legacy_screener_results(owner_user_id, force=force) is not None:
            migrated += 1
    return migrated


def initialize_screener_result_runtime() -> None:
    app_config.SCREENER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    migrate_all_legacy_screener_results()


def _recent_runs_for_user(current_user: auth.User | None) -> list[ScreenerRunMetadata]:
    if not auth.get_auth_settings().enabled:
        state = load_screener_result_state()
        return list(state.recent_runs) if state is not None else []

    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    if access.is_admin_user(current_user):
        recent_runs: list[ScreenerRunMetadata] = []
        for state_path in app_config.SCREENER_STATE_DIR.glob("*/*.json"):
            payload = load_screener_result_state(
                None if state_path.parent.name == WORKSPACE_OWNER_KEY else state_path.parent.name,
                state_path.stem,
            )
            if payload is not None:
                recent_runs.extend(payload.recent_runs)
        return recent_runs

    state = load_screener_result_state(current_user.id)
    if state is None:
        return []
    return list(state.recent_runs)


def _snapshot_for_run_id(
    run_id: str,
    current_user: auth.User | None = None,
) -> tuple[ScreenerResultSnapshot, str]:
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=404, detail="Screener run not found")

    if not auth.get_auth_settings().enabled:
        candidate_states = [load_screener_result_state()]
    elif current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    elif access.is_admin_user(current_user):
        candidate_states = [
            load_screener_result_state(
                None if state_path.parent.name == WORKSPACE_OWNER_KEY else state_path.parent.name,
                state_path.stem,
            )
            for state_path in app_config.SCREENER_STATE_DIR.glob("*/*.json")
        ]
    else:
        candidate_states = [load_screener_result_state(current_user.id)]

    for state in candidate_states:
        if state is None:
            continue
        if state.current_result is not None and state.current_result.source_run_id == run_id:
            return state.current_result, CURRENT_SNAPSHOT_SLOT
        if state.previous_result is not None and state.previous_result.source_run_id == run_id:
            return state.previous_result, PREVIOUS_SNAPSHOT_SLOT

    raise HTTPException(status_code=404, detail=f"Screener run '{run_id}' not found")


class ScreenerResultReadService:
    def list_recent_runs(self, current_user: auth.User | None = None) -> list[dict[str, Any]]:
        recent_runs = _sort_recent_runs(_recent_runs_for_user(current_user))
        return [
            {
                "id": run_metadata.id,
                "as_of_date": run_metadata.as_of_date,
                "markets": list(run_metadata.markets),
                "candidate_count": run_metadata.candidate_count,
                "generated_at": run_metadata.generated_at,
                "status": run_metadata.status,
                "snapshot_slot": run_metadata.snapshot_slot,
                "snapshot_available": run_metadata.snapshot_available,
            }
            for run_metadata in recent_runs
        ]

    def get_run(self, run_id: str, current_user: auth.User | None = None) -> dict[str, Any]:
        snapshot, snapshot_slot = _snapshot_for_run_id(run_id, current_user)
        return {
            "id": snapshot.source_run_id,
            "as_of_date": snapshot.as_of_date,
            "markets": list(snapshot.markets),
            "candidate_count": snapshot.candidate_count,
            "generated_at": snapshot.generated_at,
            "filtered_count_by_reason": dict(snapshot.filtered_count_by_reason),
            "artifact_paths": dict(snapshot.artifact_paths),
            "summary": dict(snapshot.summary),
            "snapshot_slot": snapshot_slot,
        }

    def get_run_candidates(
        self,
        run_id: str,
        current_user: auth.User | None = None,
    ) -> list[dict[str, Any]]:
        snapshot, _ = _snapshot_for_run_id(run_id, current_user)
        return [
            {
                "breakout_type": None,
                "breakout_reason": None,
                "breakout_with_volume": None,
                "breakout_base_bonus": None,
                "breakout_volume_bonus": None,
                "breakout_bonus": None,
                "strategy_tags": "",
                "risk_flags": "",
                **dict(row),
                "strategy_tags": row.get("strategy_tags") or "",
                "risk_flags": row.get("risk_flags") or "",
            }
            for row in snapshot.rows
        ]


def record_screener_run_metadata(task: Any, result: Any) -> ScreenerResultState:
    candidate = run_screener(task, result)
    return persist_screener_run(task, candidate)


def run_screener(task: Any, result: Any) -> ScreenerResultCandidate:
    owner_user_id = getattr(task, "owner_user_id", None)
    if auth.get_auth_settings().enabled and not owner_user_id:
        raise RuntimeError("Screener task owner is required when auth is enabled")

    run_dir = Path(result.run_dir).resolve()
    legacy_run = _read_legacy_run(run_dir, owner_user_id=owner_user_id)
    if legacy_run is None:
        raise RuntimeError(f"Screener run artifacts are incomplete for '{run_dir.name}'")

    universe_count = legacy_run.universe_count
    if getattr(result, "universe_count_by_market", None):
        universe_count = sum(
            max(int(value), 0)
            for value in dict(result.universe_count_by_market).values()
        )

    return ScreenerResultCandidate(
        source_run_id=legacy_run.run_id,
        generated_at=legacy_run.generated_at,
        source_legacy_run_id=legacy_run.run_id,
        as_of_date=legacy_run.as_of_date,
        markets=list(legacy_run.markets),
        universe_count=universe_count,
        match_count=max(int(getattr(result, "candidate_count", legacy_run.candidate_count) or 0), 0),
        filtered_count_by_reason=dict(legacy_run.filtered_count_by_reason),
        artifact_paths=dict(legacy_run.artifact_paths),
        rows=list(legacy_run.rows),
        manifest_version=legacy_run.manifest_version,
        logic_version=legacy_run.logic_version,
        duration_ms=legacy_run.duration_ms,
        result_hash=legacy_run.result_hash,
        run_dir=run_dir,
    )


def persist_screener_run(
    task: Any,
    candidate: ScreenerResultCandidate | None = None,
    *,
    error_summary: str | None = None,
    source_run_id: str | None = None,
) -> ScreenerResultState:
    owner_user_id = getattr(task, "owner_user_id", None)
    if auth.get_auth_settings().enabled and not owner_user_id:
        raise RuntimeError("Screener task owner is required when auth is enabled")

    state = load_screener_result_state(owner_user_id) or ScreenerResultState(owner_user_id=owner_user_id)
    existing_current = state.current_result
    existing_previous = state.previous_result
    if candidate is None:
        failed_run_id = source_run_id or getattr(task, "run_id", None) or getattr(task, "id", "")
        run_metadata = _failed_run_metadata(
            task=task,
            owner_user_id=owner_user_id,
            error_summary=error_summary or "Screener run failed",
            source_run_id=failed_run_id or _serialize_run_timestamp(),
        )
        recent_runs = [run_metadata, *[run for run in state.recent_runs if run.id != run_metadata.id]]
        state.recent_runs = _sort_recent_runs(recent_runs)
        _annotate_recent_runs(state)
        save_screener_result_state(state)
        return state

    next_snapshot = _snapshot_from_candidate(candidate, slot=CURRENT_SNAPSHOT_SLOT)

    if existing_current is None:
        next_snapshot.summary = _build_summary(next_snapshot.rows, None)
        state.current_result = next_snapshot
        state.previous_result = (
            _clear_snapshot_summary(existing_previous)
            if existing_previous is not None
            else None
        )
        status = "success"
    elif next_snapshot.result_hash == existing_current.result_hash:
        next_snapshot.summary = dict(existing_current.summary)
        state.current_result = next_snapshot
        state.previous_result = (
            _clear_snapshot_summary(existing_previous)
            if existing_previous is not None
            else None
        )
        status = "no_change"
    else:
        _increment_snapshot_rotation()
        next_snapshot.summary = _build_summary(next_snapshot.rows, existing_current.rows)
        state.previous_result = _clear_snapshot_summary(existing_current)
        state.current_result = next_snapshot
        status = "success"

    recent_runs = [
        _recent_run_from_candidate(candidate, owner_user_id=owner_user_id, status=status),
        *[run for run in state.recent_runs if run.id != candidate.source_run_id],
    ]
    state.recent_runs = _sort_recent_runs(recent_runs)
    _annotate_recent_runs(state)
    save_screener_result_state(state)

    if auth.get_auth_settings().enabled and candidate.run_dir is not None:
        with auth.db_session() as db:
            screener_runs.upsert_screener_run(
                db,
                run_id=candidate.source_run_id,
                owner_user_id=owner_user_id,
                as_of_date=candidate.as_of_date,
                markets=candidate.markets,
                candidate_count=candidate.match_count,
                generated_at=candidate.generated_at,
                storage_path=_relative_screener_storage_path(candidate.run_dir),
                artifact_manifest=_build_screener_artifact_manifest(candidate.run_dir),
            )

    return state
