from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Final, Iterable, Literal

from .model_config import get_model_ids_for_provider, get_provider_base_url

ModelProfileId = Literal["low_cost", "balanced", "high_quality", "custom"]
ModelMode = Literal["quick", "deep"]
CostTier = Literal["low", "medium", "high", "premium"]

ProviderAvailabilityFn = Callable[[str], dict[str, str | bool | None]]

PROVIDER_API_KEY_ENV_VARS: Final[dict[str, str | None]] = {
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "xai": "XAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "siliconflow": "SILICONFLOW_API_KEY",
    "ollama": None,
    "xiaohumini": "XIAOHUMINI_API_KEY",
    "sub2api": "SUB2API_API_KEY",
    "mimo": "MIMO_API_KEY",
}


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    quick_model: str
    deep_model: str


@dataclass(frozen=True)
class ModelProfile:
    value: ModelProfileId
    label: str
    description: str
    cost_tier: CostTier
    routes: tuple[ModelRoute, ...]


@dataclass(frozen=True)
class ResolvedModelSelection:
    model_profile: str
    llm_provider: str
    quick_think_llm: str
    deep_think_llm: str
    backend_url: str


STATIC_MODEL_PROFILES: Final[tuple[ModelProfile, ...]] = (
    ModelProfile(
        value="balanced",
        label="Balanced",
        description="Default quality and cost balance for most analysis tasks.",
        cost_tier="medium",
        routes=(
            ModelRoute("openai", "gpt-5.4-mini", "gpt-5.2"),
            ModelRoute("sub2api", "gpt-5.4-mini", "gpt-5.4"),
            ModelRoute("xiaohumini", "gpt-5.4-mini", "gpt-5.2"),
            ModelRoute("mimo", "mimo-v2.5", "mimo-v2.5-pro"),
        ),
    ),
    ModelProfile(
        value="low_cost",
        label="Low Cost",
        description="Lower-cost models for frequent trial runs and lighter analysis.",
        cost_tier="low",
        routes=(
            ModelRoute("openai", "gpt-5.4-nano", "gpt-5-mini"),
            ModelRoute("sub2api", "gpt-5.2", "gpt-5.4"),
            ModelRoute("xiaohumini", "gpt-5.4-nano", "gpt-5-mini"),
            ModelRoute("mimo", "mimo-v2-flash", "mimo-v2-flash"),
        ),
    ),
    ModelProfile(
        value="high_quality",
        label="High Quality",
        description="Higher-capability models for deeper research and important reviews.",
        cost_tier="high",
        routes=(
            ModelRoute("openai", "gpt-5.4", "gpt-5.5"),
            ModelRoute("sub2api", "gpt-5.2", "gpt-5.5"),
            ModelRoute("xiaohumini", "gpt-5.4", "gpt-5.5"),
            ModelRoute("mimo", "mimo-v2.5-pro", "mimo-v2.5-pro"),
        ),
    ),
)


def default_provider_availability(provider: str) -> dict[str, str | bool | None]:
    api_key_env = PROVIDER_API_KEY_ENV_VARS.get(provider)
    if api_key_env is None:
        return {"enabled": True, "disabled_reason": None}
    if os.environ.get(api_key_env):
        return {"enabled": True, "disabled_reason": None}
    return {
        "enabled": False,
        "disabled_reason": f"Configure API key {api_key_env} to use this provider.",
    }


def get_model_profile(profile_id: str) -> ModelProfile:
    normalized = profile_id.strip().lower()
    for profile in STATIC_MODEL_PROFILES:
        if profile.value == normalized:
            return profile
    if normalized == "custom":
        return ModelProfile(
            value="custom",
            label="Custom",
            description="Choose the provider and concrete quick/deep models manually.",
            cost_tier="medium",
            routes=(),
        )
    raise KeyError(f"Unknown model profile: {profile_id}")


def _route_models_are_known(route: ModelRoute) -> bool:
    try:
        known_models = set(get_model_ids_for_provider(route.provider))
    except KeyError:
        return False
    return route.quick_model in known_models and route.deep_model in known_models


def iter_available_routes(
    routes: Iterable[ModelRoute],
    availability_fn: ProviderAvailabilityFn | None = None,
) -> Iterable[ModelRoute]:
    resolved_availability = availability_fn or default_provider_availability
    for route in routes:
        if not _route_models_are_known(route):
            continue
        availability = resolved_availability(route.provider)
        if availability.get("enabled"):
            yield route


def resolve_model_profile(
    profile_id: str,
    availability_fn: ProviderAvailabilityFn | None = None,
) -> ResolvedModelSelection:
    profile = get_model_profile(profile_id)
    if profile.value == "custom":
        raise ValueError(
            "custom model profile requires explicit provider and model selection"
        )

    route = next(iter_available_routes(profile.routes, availability_fn), None)
    if route is None:
        raise ValueError(
            f"Model profile '{profile.value}' has no available provider route"
        )

    return ResolvedModelSelection(
        model_profile=profile.value,
        llm_provider=route.provider,
        quick_think_llm=route.quick_model,
        deep_think_llm=route.deep_model,
        backend_url=get_provider_base_url(route.provider),
    )


def serialize_model_profile(
    profile: ModelProfile,
    availability_fn: ProviderAvailabilityFn | None = None,
) -> dict[str, object]:
    if profile.value == "custom":
        return {
            "label": profile.label,
            "value": profile.value,
            "description": profile.description,
            "cost_tier": profile.cost_tier,
            "enabled": True,
            "disabled_reason": None,
            "default_provider": None,
            "default_quick_model": None,
            "default_deep_model": None,
            "default_quick_label": None,
            "default_deep_label": None,
        }

    route = next(iter_available_routes(profile.routes, availability_fn), None)
    return {
        "label": profile.label,
        "value": profile.value,
        "description": profile.description,
        "cost_tier": profile.cost_tier,
        "enabled": route is not None,
        "disabled_reason": None
        if route is not None
        else "No configured provider is available for this model profile.",
        "default_provider": route.provider if route is not None else None,
        "default_quick_model": route.quick_model if route is not None else None,
        "default_deep_model": route.deep_model if route is not None else None,
        "default_quick_label": route.quick_model if route is not None else None,
        "default_deep_label": route.deep_model if route is not None else None,
    }


def list_model_profile_options(
    availability_fn: ProviderAvailabilityFn | None = None,
) -> list[dict[str, object]]:
    profiles = [
        serialize_model_profile(profile, availability_fn)
        for profile in STATIC_MODEL_PROFILES
    ]
    profiles.append(
        serialize_model_profile(get_model_profile("custom"), availability_fn)
    )
    return profiles
