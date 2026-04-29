import copy

import diverge.default_config as default_config
from typing import Dict, Optional, cast

# Use default config but allow it to be overridden
_config: Optional[Dict] = None


def _deep_merge_dicts(base: Dict, updates: Dict) -> Dict:
    merged = copy.deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def initialize_config():
    """Initialize the configuration with default values."""
    global _config
    if _config is None:
        _config = copy.deepcopy(default_config.DEFAULT_CONFIG)


def set_config(config: Dict):
    """Update the configuration with custom values."""
    global _config
    if _config is None:
        _config = copy.deepcopy(default_config.DEFAULT_CONFIG)
    _config = _deep_merge_dicts(_config, config)


def get_config() -> Dict:
    """Get the current configuration."""
    if _config is None:
        initialize_config()
    if _config is None:
        raise RuntimeError("Configuration failed to initialize")
    return cast(Dict, copy.deepcopy(_config))


# Initialize with default config
initialize_config()
