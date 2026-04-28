from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from web.backend import app_config
from web.backend.schemas.screeners import ScreenTaskCreatePayload

PRESETS_DIRNAME = "presets"
WORKSPACE_OWNER_ID = "workspace"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _owner_key(owner_user_id: str | None) -> str:
    value = str(owner_user_id or WORKSPACE_OWNER_ID).strip()
    return value or WORKSPACE_OWNER_ID


def _presets_dir() -> Path:
    return app_config.SCREENER_STATE_DIR / PRESETS_DIRNAME


def _preset_path(owner_user_id: str | None) -> Path:
    return _presets_dir() / f"{_owner_key(owner_user_id)}.json"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _normalize_preset_item(
    item: dict[str, Any],
    *,
    owner_user_id: str | None,
    tenant_id: str | None,
) -> dict[str, Any]:
    raw_config = item.get("config")
    if not isinstance(raw_config, dict):
        raise ValueError("preset config is required")
    try:
        config = ScreenTaskCreatePayload(**raw_config).model_dump()
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    now = _utc_iso()
    preset_id = str(item.get("id") or uuid.uuid4().hex).strip() or uuid.uuid4().hex
    preset_name = str(item.get("name") or "Saved Screen").strip() or "Saved Screen"
    return {
        "id": preset_id,
        "name": preset_name,
        "fingerprint": str(item.get("fingerprint") or "").strip(),
        "config": config,
        "created_at": str(item.get("created_at") or now),
        "updated_at": str(item.get("updated_at") or now),
        "owner_user_id": owner_user_id,
        "tenant_id": tenant_id,
    }


def load_screener_presets(owner_user_id: str | None) -> list[dict[str, Any]]:
    path = _preset_path(owner_user_id)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    items = payload.get("items")
    return list(items) if isinstance(items, list) else []


def save_screener_presets(
    owner_user_id: str | None,
    presets: list[dict[str, Any]],
    *,
    tenant_id: str | None = None,
) -> list[dict[str, Any]]:
    normalized_items = [
        _normalize_preset_item(item, owner_user_id=owner_user_id, tenant_id=tenant_id)
        for item in presets
        if isinstance(item, dict)
    ]
    _write_json_atomic(
        _preset_path(owner_user_id),
        {
            "owner_user_id": owner_user_id,
            "tenant_id": tenant_id,
            "items": normalized_items,
            "updated_at": _utc_iso(),
        },
    )
    return normalized_items


def list_all_screener_preset_configs() -> list[dict[str, Any]]:
    presets_dir = _presets_dir()
    if not presets_dir.is_dir():
        return []

    configs: list[dict[str, Any]] = []
    for path in sorted(presets_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        owner_user_id = payload.get("owner_user_id")
        tenant_id = payload.get("tenant_id")
        for item in payload.get("items") or []:
            if not isinstance(item, dict) or not isinstance(item.get("config"), dict):
                continue
            configs.append(
                {
                    "preset_id": item.get("id"),
                    "name": item.get("name"),
                    "config": dict(item["config"]),
                    "owner_user_id": owner_user_id,
                    "tenant_id": tenant_id,
                }
            )
    return configs
