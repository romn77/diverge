from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from diverge.config.paths import PROJECT_ROOT

CONFIG_ROOT = PROJECT_ROOT / "configs" / "opportunity"


class OpportunityConfigError(ValueError):
    pass


def _load_json_or_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise OpportunityConfigError(f"Opportunity config not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise OpportunityConfigError(
                f"{path} is not JSON-compatible YAML and PyYAML is not installed"
            ) from exc
        payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise OpportunityConfigError(f"Opportunity config must be an object: {path}")
    return payload


@lru_cache(maxsize=64)
def load_opportunity_config(name: str) -> dict[str, Any]:
    safe_name = name.strip().strip("/")
    path = CONFIG_ROOT / safe_name
    return _load_json_or_yaml(path)


def load_strategy_config(strategy_id: str) -> dict[str, Any]:
    return load_opportunity_config(f"strategies/{strategy_id}.yaml")


def load_cost_models() -> dict[str, Any]:
    return load_opportunity_config("cost_models.yaml")


def load_watchlist_policy() -> dict[str, Any]:
    return load_opportunity_config("watchlist_policy.yaml")


def load_theme_registry() -> dict[str, Any]:
    return load_opportunity_config("theme_registry.yaml")


def load_analysis_defaults() -> dict[str, Any]:
    return load_opportunity_config("analysis_defaults.yaml")
