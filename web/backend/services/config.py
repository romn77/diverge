from __future__ import annotations

import os

from dotenv import dotenv_values

from cli.utils import ANALYST_ORDER
from tradingagents.screener.presets import (
    DEFAULT_FILTER_PRESET_SELECTIONS,
    DEFAULT_RANKING_PROFILE_ID,
    list_filter_preset_groups,
    list_ranking_profiles,
)
from tradingagents.llm_clients.model_config import (
    DEEP_MODEL_OPTIONS,
    PROVIDER_OPTIONS,
    QUICK_MODEL_OPTIONS,
)
from tradingagents.llm_clients.model_profiles import (
    PROVIDER_API_KEY_ENV_VARS,
    list_model_profile_options,
)
from web.backend import app_config
from web.backend import llm_models

RESEARCH_DEPTH_OPTIONS = [
    {
        "label": "Shallow",
        "value": 1,
        "description": "Quick research with minimal debate rounds",
    },
    {
        "label": "Medium",
        "value": 3,
        "description": "Balanced debate depth and strategy discussion",
    },
    {
        "label": "Deep",
        "value": 5,
        "description": "Comprehensive debate and risk discussion",
    },
]
OUTPUT_LANGUAGE_OPTIONS = [
    {"label": "English (en)", "value": "en"},
    {"label": "简体中文 (cn)", "value": "cn"},
]
OPENAI_REASONING_OPTIONS = [
    {"label": "Medium", "value": "medium"},
    {"label": "High", "value": "high"},
    {"label": "Low", "value": "low"},
]
GOOGLE_THINKING_OPTIONS = [
    {"label": "Enable Thinking", "value": "high"},
    {"label": "Minimal Thinking", "value": "minimal"},
]
def read_project_env_values() -> dict[str, str]:
    if not app_config.PROJECT_ENV_FILE.is_file():
        return {}
    return {
        key: value.strip()
        for key, value in dotenv_values(app_config.PROJECT_ENV_FILE).items()
        if isinstance(value, str) and value.strip()
    }


def get_project_secret(secret_name: str) -> str | None:
    return read_project_env_values().get(secret_name)


def hydrate_provider_credentials(provider: str) -> None:
    secret_name = PROVIDER_API_KEY_ENV_VARS.get(provider)
    if not secret_name:
        return

    secret_value = get_project_secret(secret_name)
    if secret_value and not os.environ.get(secret_name):
        os.environ[secret_name] = secret_value


def get_provider_availability(provider: str) -> dict[str, str | bool | None]:
    api_key_env = PROVIDER_API_KEY_ENV_VARS.get(provider)
    if api_key_env is None:
        return {"enabled": True, "disabled_reason": None}

    if os.environ.get(api_key_env) or get_project_secret(api_key_env):
        return {"enabled": True, "disabled_reason": None}

    return {
        "enabled": False,
        "disabled_reason": f"Configure API key {api_key_env} to use this provider in web tasks.",
    }


def get_config_options_payload() -> dict:
    provider_options = [
        {
            "label": label,
            "value": provider,
            **get_provider_availability(provider),
        }
        for provider, label, _base_url in PROVIDER_OPTIONS
    ]
    model_options = {
        provider: {
            "quick": [
                {"label": label, "value": model_id}
                for label, model_id in QUICK_MODEL_OPTIONS[provider]
            ],
            "deep": [
                {"label": label, "value": model_id}
                for label, model_id in DEEP_MODEL_OPTIONS[provider]
            ],
        }
        for provider, _label, _base_url in PROVIDER_OPTIONS
    }
    analyst_options = [
        {"label": label, "value": value.value}
        for label, value in ANALYST_ORDER
    ]

    return {
        "providers": provider_options,
        "model_profiles": llm_models.list_config_model_profiles()
        if llm_models.database_backed_llm_models_enabled()
        else list_model_profile_options(get_provider_availability),
        "models": model_options,
        "analysts": analyst_options,
        "research_depth": RESEARCH_DEPTH_OPTIONS,
        "output_languages": OUTPUT_LANGUAGE_OPTIONS,
        "defaults": {},
        "provider_settings": {
            "openai": {"openai_reasoning_effort": OPENAI_REASONING_OPTIONS},
            "google": {"google_thinking_level": GOOGLE_THINKING_OPTIONS},
        },
    }


def get_screener_config_options_payload() -> dict:
    return {
        "markets": [
            {"label": "A-Share (cn)", "value": "cn", "enabled": True},
            {
                "label": "US Equities (us)",
                "value": "us",
                "enabled": bool(os.environ.get("SCREEN_US_MANIFEST_PATH")),
                "disabled_reason": None
                if os.environ.get("SCREEN_US_MANIFEST_PATH")
                else "Configure SCREEN_US_MANIFEST_PATH on the backend to enable US screening.",
            },
        ],
        "cn_data_sources": [
            {"label": "Tushare", "value": "tushare"},
        ],
        "us_data_sources": [
            {"label": "Massive", "value": "massive"},
        ],
        "breakout_types": [
            {"label": "Platform Breakout", "value": "platform_breakout"},
            {"label": "Box Breakout", "value": "box_breakout"},
            {"label": "Wedge Breakout", "value": "wedge_breakout"},
        ],
        "filter_preset_groups": list_filter_preset_groups(),
        "ranking_profiles": list_ranking_profiles(),
        "defaults": {
            "cn_data_source": "tushare",
            "us_data_source": "massive",
            "top_k": 500,
            "history_cache_policy": "cache_only",
            "breakout_types": [],
            "filter_preset_selections": DEFAULT_FILTER_PRESET_SELECTIONS,
            "ranking_profile_id": DEFAULT_RANKING_PROFILE_ID,
            "include_fundamentals": False,
            "cn_fundamental_source": "tushare",
            "us_fundamental_source": "simfin",
        },
    }
