from typing import Final

ProviderOption = tuple[str, str, str]
ModelOption = tuple[str, str]

DEFAULT_LLM_PROVIDER: Final[str] = "openai"
DEFAULT_DEEP_MODEL: Final[str] = "gpt-5.2"
DEFAULT_QUICK_MODEL: Final[str] = "gpt-5-mini"

PROVIDER_OPTIONS: Final[tuple[ProviderOption, ...]] = (
    ("openai", "OpenAI", "https://api.openai.com/v1"),
    ("google", "Google", "https://generativelanguage.googleapis.com/v1"),
    ("anthropic", "Anthropic", "https://api.anthropic.com/"),
    ("xai", "xAI", "https://api.x.ai/v1"),
    ("openrouter", "Openrouter", "https://openrouter.ai/api/v1"),
    ("deepseek", "DeepSeek", "https://api.deepseek.com/v1"),
    ("ollama", "Ollama", "http://localhost:11434/v1"),
    ("xiaohumini", "Xiaohumini", "https://xiaohumini.site/v1"),
)

QUICK_MODEL_OPTIONS: Final[dict[str, tuple[ModelOption, ...]]] = {
    "openai": (
        ("GPT-5 Mini - Cost-optimized reasoning", "gpt-5-mini"),
        ("GPT-5 Nano - Ultra-fast, high-throughput", "gpt-5-nano"),
        ("GPT-5.2 - Latest flagship", "gpt-5.2"),
        ("GPT-5.1 - Flexible reasoning", "gpt-5.1"),
        ("GPT-4.1 - Smartest non-reasoning, 1M context", "gpt-4.1"),
    ),
    "anthropic": (
        ("Claude Haiku 4.5 - Fast + extended thinking", "claude-haiku-4-5"),
        ("Claude Sonnet 4.5 - Best for agents/coding", "claude-sonnet-4-5"),
        ("Claude Sonnet 4 - High-performance", "claude-sonnet-4-20250514"),
    ),
    "google": (
        ("Gemini 3 Flash - Next-gen fast", "gemini-3-flash-preview"),
        ("Gemini 2.5 Flash - Balanced, recommended", "gemini-2.5-flash"),
        ("Gemini 3 Pro - Reasoning-first", "gemini-3-pro-preview"),
        ("Gemini 2.5 Flash Lite - Fast, low-cost", "gemini-2.5-flash-lite"),
    ),
    "xai": (
        (
            "Grok 4.1 Fast (Non-Reasoning) - Speed optimized, 2M ctx",
            "grok-4-1-fast-non-reasoning",
        ),
        (
            "Grok 4 Fast (Non-Reasoning) - Speed optimized",
            "grok-4-fast-non-reasoning",
        ),
        (
            "Grok 4.1 Fast (Reasoning) - High-performance, 2M ctx",
            "grok-4-1-fast-reasoning",
        ),
        ("Grok 4 Fast (Reasoning) - High-performance", "grok-4-fast-reasoning"),
    ),
    "openrouter": (
        (
            "NVIDIA Nemotron 3 Nano 30B (free)",
            "nvidia/nemotron-3-nano-30b-a3b:free",
        ),
        ("Z.AI GLM 4.5 Air (free)", "z-ai/glm-4.5-air:free"),
    ),
    "deepseek": (
        ("DeepSeek V3 Chat - Balanced performance", "deepseek-chat"),
        ("DeepSeek R1 Reasoner - Deep reasoning", "deepseek-reasoner"),
    ),
    "ollama": (
        ("Qwen3:latest (8B, local)", "qwen3:latest"),
        ("GPT-OSS:latest (20B, local)", "gpt-oss:latest"),
        ("GLM-4.7-Flash:latest (30B, local)", "glm-4.7-flash:latest"),
    ),
    "xiaohumini": (
        ("GPT-5.2 - Latest flagship", "gpt-5.2"),
        ("Claude Sonnet 4.6 - Fast + capable", "claude-sonnet-4-6"),
        ("Gemini 3.1 Pro Preview - Fast + capable", "gemini-3.1-pro-preview"),
        ("Grok 4.2 - Fast + capable", "grok-4.2"),
    ),
}

DEEP_MODEL_OPTIONS: Final[dict[str, tuple[ModelOption, ...]]] = {
    "openai": (
        ("GPT-5.2 - Latest flagship", "gpt-5.2"),
        ("GPT-5.1 - Flexible reasoning", "gpt-5.1"),
        ("GPT-5 - Advanced reasoning", "gpt-5"),
        ("GPT-4.1 - Smartest non-reasoning, 1M context", "gpt-4.1"),
        ("GPT-5 Mini - Cost-optimized reasoning", "gpt-5-mini"),
        ("GPT-5 Nano - Ultra-fast, high-throughput", "gpt-5-nano"),
    ),
    "anthropic": (
        ("Claude Sonnet 4.5 - Best for agents/coding", "claude-sonnet-4-5"),
        ("Claude Opus 4.5 - Premium, max intelligence", "claude-opus-4-5"),
        ("Claude Opus 4.1 - Most capable model", "claude-opus-4-1-20250805"),
        ("Claude Haiku 4.5 - Fast + extended thinking", "claude-haiku-4-5"),
        ("Claude Sonnet 4 - High-performance", "claude-sonnet-4-20250514"),
    ),
    "google": (
        ("Gemini 3 Pro - Reasoning-first", "gemini-3-pro-preview"),
        ("Gemini 3 Flash - Next-gen fast", "gemini-3-flash-preview"),
        ("Gemini 2.5 Flash - Balanced, recommended", "gemini-2.5-flash"),
    ),
    "xai": (
        (
            "Grok 4.1 Fast (Reasoning) - High-performance, 2M ctx",
            "grok-4-1-fast-reasoning",
        ),
        ("Grok 4 Fast (Reasoning) - High-performance", "grok-4-fast-reasoning"),
        ("Grok 4 - Flagship model", "grok-4-0709"),
        (
            "Grok 4.1 Fast (Non-Reasoning) - Speed optimized, 2M ctx",
            "grok-4-1-fast-non-reasoning",
        ),
        (
            "Grok 4 Fast (Non-Reasoning) - Speed optimized",
            "grok-4-fast-non-reasoning",
        ),
    ),
    "openrouter": (
        ("Z.AI GLM 4.5 Air (free)", "z-ai/glm-4.5-air:free"),
        (
            "NVIDIA Nemotron 3 Nano 30B (free)",
            "nvidia/nemotron-3-nano-30b-a3b:free",
        ),
    ),
    "deepseek": (
        ("DeepSeek R1 Reasoner - Deep reasoning", "deepseek-reasoner"),
        ("DeepSeek V3 Chat - Balanced performance", "deepseek-chat"),
    ),
    "ollama": (
        ("GLM-4.7-Flash:latest (30B, local)", "glm-4.7-flash:latest"),
        ("GPT-OSS:latest (20B, local)", "gpt-oss:latest"),
        ("Qwen3:latest (8B, local)", "qwen3:latest"),
    ),
    "xiaohumini": (
        ("GPT-5.2 - Latest flagship", "gpt-5.2"),
        ("Claude Sonnet 4.6 - Fast + capable", "claude-sonnet-4-6"),
        ("Gemini 3.1 Pro Preview - Fast + capable", "gemini-3.1-pro-preview"),
        ("Grok 4.2 - Fast + capable", "grok-4.2"),
    ),
}

EXTRA_VALIDATED_MODELS: Final[dict[str, tuple[str, ...]]] = {
    "openai": (
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "o4-mini",
        "o3",
        "o3-mini",
        "o1",
        "o1-preview",
        "gpt-4o",
        "gpt-4o-mini",
    ),
    "anthropic": (
        "claude-3-7-sonnet-20250219",
        "claude-3-5-haiku-20241022",
        "claude-3-5-sonnet-20241022",
    ),
    "google": (
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ),
    "xai": (
        "grok-4-1-fast",
        "grok-4",
    ),
    "deepseek": (),
    "openrouter": (),
    "ollama": (),
    "xiaohumini": (),
}

ALLOW_ANY_MODEL_PROVIDERS: Final[frozenset[str]] = frozenset(
    {"ollama", "openrouter", "deepseek", "xiaohumini"}
)


def _normalize_provider(provider: str) -> str:
    return provider.lower()


def _unique_model_ids(
    *option_groups: tuple[ModelOption, ...], extras: tuple[str, ...] = ()
) -> tuple[str, ...]:
    model_ids: list[str] = []
    seen: set[str] = set()

    for options in option_groups:
        for _label, model_id in options:
            if model_id not in seen:
                seen.add(model_id)
                model_ids.append(model_id)

    for model_id in extras:
        if model_id not in seen:
            seen.add(model_id)
            model_ids.append(model_id)

    return tuple(model_ids)


VALIDATED_MODELS: Final[dict[str, tuple[str, ...]]] = {
    provider: _unique_model_ids(
        QUICK_MODEL_OPTIONS[provider],
        DEEP_MODEL_OPTIONS[provider],
        extras=EXTRA_VALIDATED_MODELS.get(provider, ()),
    )
    for provider in QUICK_MODEL_OPTIONS
}


def get_quick_model_options(provider: str) -> tuple[ModelOption, ...]:
    return QUICK_MODEL_OPTIONS[_normalize_provider(provider)]


def get_deep_model_options(provider: str) -> tuple[ModelOption, ...]:
    return DEEP_MODEL_OPTIONS[_normalize_provider(provider)]


def get_model_ids_for_provider(provider: str) -> tuple[str, ...]:
    provider_key = _normalize_provider(provider)
    return _unique_model_ids(
        QUICK_MODEL_OPTIONS[provider_key],
        DEEP_MODEL_OPTIONS[provider_key],
    )


def get_provider_base_url(provider: str) -> str:
    provider_key = _normalize_provider(provider)
    for current_provider, _label, base_url in PROVIDER_OPTIONS:
        if current_provider == provider_key:
            return base_url
    raise KeyError(f"Unknown provider: {provider}")
