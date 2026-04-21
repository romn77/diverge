"""Compatibility layer exposing model selections for CLI/tests.

Keep model_config.py as the single source of truth for provider/model options.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .model_config import (
    PROVIDER_OPTIONS,
    get_deep_model_options,
    get_model_ids_for_provider,
    get_quick_model_options,
)

ModelOption = Tuple[str, str]


def get_model_options(provider: str, mode: str) -> List[ModelOption]:
    """Return shared model options for a provider and selection mode."""
    if mode == "quick":
        return list(get_quick_model_options(provider))
    if mode == "deep":
        return list(get_deep_model_options(provider))
    raise KeyError(f"Unknown model selection mode: {mode}")


def get_known_models() -> Dict[str, List[str]]:
    """Build known model names from the shared CLI catalog."""
    return {
        provider: sorted(get_model_ids_for_provider(provider))
        for provider, _label, _url in PROVIDER_OPTIONS
    }
