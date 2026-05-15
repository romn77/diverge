from __future__ import annotations

import os

from dotenv import dotenv_values
from fastapi import Request

from diverge.analysis.options import ANALYST_OPTIONS
from diverge.screener.presets import (
    DEFAULT_FILTER_PRESET_SELECTIONS,
    DEFAULT_RANKING_PROFILE_ID,
    list_filter_preset_groups,
    list_ranking_profiles,
)
from diverge.llm_clients.model_config import (
    DEEP_MODEL_OPTIONS,
    PROVIDER_OPTIONS,
    QUICK_MODEL_OPTIONS,
)
from diverge.llm_clients.model_profiles import (
    get_provider_api_key_env_vars,
    list_model_profile_options,
)
from web.backend import app_config, auth, llm_models

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
    secret_names = get_provider_api_key_env_vars(provider)
    if not secret_names:
        return

    for secret_name in secret_names:
        secret_value = get_project_secret(secret_name)
        if secret_value and not os.environ.get(secret_name):
            os.environ[secret_name] = secret_value


def get_provider_availability(provider: str) -> dict[str, str | bool | None]:
    api_key_envs = get_provider_api_key_env_vars(provider)
    if not api_key_envs:
        return {"enabled": True, "disabled_reason": None}

    if any(
        os.environ.get(api_key_env) or get_project_secret(api_key_env)
        for api_key_env in api_key_envs
    ):
        return {"enabled": True, "disabled_reason": None}

    api_key_label = " or ".join(api_key_envs)
    return {
        "enabled": False,
        "disabled_reason": f"Configure API key {api_key_label} to use this provider in web tasks.",
    }


def _request_user_role(request: Request | None) -> str | None:
    if not auth.auth_enabled() or request is None:
        return auth.UserRole.ADMIN.value
    with auth.db_session() as db:
        user = auth.get_request_user(db, request)
        return user.role if user is not None else None


def get_config_options_payload(request: Request | None = None) -> dict:
    user_role = _request_user_role(request)
    include_custom_profile = llm_models.custom_analysis_profile_visible_for_role(
        user_role
    )
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
        {"label": label, "value": value.value} for label, value in ANALYST_OPTIONS
    ]
    model_profile_options = (
        llm_models.list_config_model_profiles(include_custom=include_custom_profile)
        if llm_models.database_backed_llm_models_enabled()
        else [
            option
            for option in list_model_profile_options(get_provider_availability)
            if include_custom_profile or option.get("value") != "custom"
        ]
    )

    return {
        "providers": provider_options,
        "model_profiles": model_profile_options,
        "models": model_options,
        "analysts": analyst_options,
        "research_depth": RESEARCH_DEPTH_OPTIONS,
        "output_languages": OUTPUT_LANGUAGE_OPTIONS,
        "defaults": {},
        "ui_settings": {
            llm_models.SHOW_CUSTOM_ANALYSIS_PROFILE_SETTING: include_custom_profile,
            "opportunity_radar_enabled": app_config.opportunity_radar_enabled(),
        },
        "provider_settings": {
            "openai": {"openai_reasoning_effort": OPENAI_REASONING_OPTIONS},
            "google": {"google_thinking_level": GOOGLE_THINKING_OPTIONS},
        },
    }


def get_screener_config_options_payload() -> dict:
    us_manifest_path = app_config.resolve_manifest_path("us", require_exists=True)
    return {
        "markets": [
            {"label": "A-Share (cn)", "value": "cn", "enabled": True},
            {
                "label": "US Equities (us)",
                "value": "us",
                "enabled": us_manifest_path is not None,
                "disabled_reason": None
                if us_manifest_path is not None
                else (
                    "Add a US manifest at DATA_DIR/manifest/us.csv to enable US screening. "
                    "SCREEN_US_MANIFEST_PATH remains available as a compatibility override."
                ),
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
            "top_k": 100,
            "history_cache_policy": "cache_only",
            "breakout_types": [],
            "filter_preset_selections": DEFAULT_FILTER_PRESET_SELECTIONS,
            "ranking_profile_id": DEFAULT_RANKING_PROFILE_ID,
            "include_fundamentals": False,
            "cn_fundamental_source": "tushare",
            "us_fundamental_source": "simfin",
        },
    }
