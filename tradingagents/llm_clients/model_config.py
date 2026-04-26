from typing import Final

ProviderOption = tuple[str, str, str]
ModelOption = tuple[str, str]

DEFAULT_LLM_PROVIDER: Final[str] = "openai"
DEFAULT_DEEP_MODEL: Final[str] = "gpt-5.4"
DEFAULT_QUICK_MODEL: Final[str] = "gpt-5.4-mini"

PROVIDER_OPTIONS: Final[tuple[ProviderOption, ...]] = (
    ("openai", "OpenAI", "https://api.openai.com/v1"),
    ("google", "Google", "https://generativelanguage.googleapis.com/v1"),
    ("anthropic", "Anthropic", "https://api.anthropic.com/"),
    ("xai", "xAI", "https://api.x.ai/v1"),
    ("openrouter", "Openrouter", "https://openrouter.ai/api/v1"),
    ("deepseek", "DeepSeek", "https://api.deepseek.com/v1"),
    ("siliconflow", "SiliconFlow", "https://api.siliconflow.cn/v1"),
    ("xiaohumini", "Xiaohumini", "https://xiaohumini.site/v1"),
)

OPENAI_QUICK_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("GPT-5.4 Mini - Fast, strong coding and tool use", "gpt-5.4-mini"),
    ("GPT-5.4 Nano - Cheapest, high-volume tasks", "gpt-5.4-nano"),
    ("GPT-5.4 - Latest frontier, 1M context", "gpt-5.4"),
    ("GPT-5.2 - Strong reasoning, cost-effective", "gpt-5.2"),
    ("GPT-5.1 - Flexible reasoning", "gpt-5.1"),
    ("GPT-5 Mini - Balanced speed, cost, and capability", "gpt-5-mini"),
    ("GPT-5 Nano - High-throughput, simple tasks", "gpt-5-nano"),
    ("GPT-4.1 - Smartest non-reasoning model", "gpt-4.1"),
)

OPENAI_DEEP_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("GPT-5.4 - Latest frontier, 1M context", "gpt-5.4"),
    ("GPT-5.2 - Strong reasoning, cost-effective", "gpt-5.2"),
    ("GPT-5.1 - Flexible reasoning", "gpt-5.1"),
    ("GPT-5.4 Pro - Most capable, expensive", "gpt-5.4-pro"),
    ("GPT-5 - Advanced reasoning", "gpt-5"),
    ("GPT-4.1 - Smartest non-reasoning model", "gpt-4.1"),
    ("GPT-5 Mini - Balanced speed, cost, and capability", "gpt-5-mini"),
    ("GPT-5 Nano - High-throughput, simple tasks", "gpt-5-nano"),
)

ANTHROPIC_QUICK_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("Claude Sonnet 4.6 - Best speed and intelligence balance", "claude-sonnet-4-6"),
    ("Claude Haiku 4.5 - Fast, near-instant responses", "claude-haiku-4-5"),
    ("Claude Sonnet 4.5 - Best for agents/coding", "claude-sonnet-4-5"),
)

ANTHROPIC_DEEP_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("Claude Opus 4.6 - Most intelligent, agents and coding", "claude-opus-4-6"),
    ("Claude Sonnet 4.5 - Best for agents/coding", "claude-sonnet-4-5"),
    ("Claude Opus 4.5 - Premium, max intelligence", "claude-opus-4-5"),
    ("Claude Sonnet 4.6 - Best speed and intelligence balance", "claude-sonnet-4-6"),
    ("Claude Haiku 4.5 - Fast, near-instant responses", "claude-haiku-4-5"),
)

GOOGLE_QUICK_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("Gemini 3 Flash - Next-gen fast", "gemini-3-flash-preview"),
    ("Gemini 2.5 Flash - Balanced, stable", "gemini-2.5-flash"),
    ("Gemini 3.1 Flash Lite - Most cost-efficient", "gemini-3.1-flash-lite-preview"),
    ("Gemini 2.5 Flash Lite - Fast, low-cost", "gemini-2.5-flash-lite"),
)

GOOGLE_DEEP_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("Gemini 3.1 Pro - Reasoning-first, complex workflows", "gemini-3.1-pro-preview"),
    ("Gemini 3 Flash - Next-gen fast", "gemini-3-flash-preview"),
    ("Gemini 2.5 Pro - Stable pro model", "gemini-2.5-pro"),
    ("Gemini 2.5 Flash - Balanced, stable", "gemini-2.5-flash"),
)

XAI_QUICK_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
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
)

XAI_DEEP_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
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
)

OPENROUTER_QUICK_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    (
        "NVIDIA Nemotron 3 Nano 30B (free)",
        "nvidia/nemotron-3-nano-30b-a3b:free",
    ),
    ("Z.AI GLM 4.5 Air (free)", "z-ai/glm-4.5-air:free"),
)

OPENROUTER_DEEP_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("Z.AI GLM 4.5 Air (free)", "z-ai/glm-4.5-air:free"),
    (
        "NVIDIA Nemotron 3 Nano 30B (free)",
        "nvidia/nemotron-3-nano-30b-a3b:free",
    ),
)

DEEPSEEK_QUICK_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("DeepSeek V4 Flash - Fast V4 preview", "deepseek-v4-flash"),
    ("DeepSeek V4 Pro - Most capable V4 model", "deepseek-v4-pro"),
    ("DeepSeek V3 Chat - Balanced performance", "deepseek-chat"),
    ("DeepSeek R1 Reasoner - Deep reasoning", "deepseek-reasoner"),
)

DEEPSEEK_DEEP_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("DeepSeek V4 Pro - Most capable V4 model", "deepseek-v4-pro"),
    ("DeepSeek V4 Flash - Fast V4 preview", "deepseek-v4-flash"),
    ("DeepSeek R1 Reasoner - Deep reasoning", "deepseek-reasoner"),
    ("DeepSeek V3 Chat - Balanced performance", "deepseek-chat"),
)

SILICONFLOW_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("DeepSeek V4 Flash", "deepseek-ai/DeepSeek-V4-Flash"),
    ("Kimi K2.6 Pro", "Pro/moonshotai/Kimi-K2.6"),
    ("Z.AI GLM 5.1 Pro", "Pro/zai-org/GLM-5.1"),
    ("MiniMax M2.5", "MiniMaxAI/MiniMax-M2.5"),
    ("MiniMax M2.5 Pro", "Pro/MiniMaxAI/MiniMax-M2.5"),
    ("Z.AI GLM 5 Pro", "Pro/zai-org/GLM-5"),
    ("Kimi K2.5 Pro", "Pro/moonshotai/Kimi-K2.5"),
    ("Z.AI GLM 4.7 Pro", "Pro/zai-org/GLM-4.7"),
    ("DeepSeek V3.2", "deepseek-ai/DeepSeek-V3.2"),
    ("DeepSeek V3.2 Pro", "Pro/deepseek-ai/DeepSeek-V3.2"),
    ("DeepSeek V3.1 Terminus", "deepseek-ai/DeepSeek-V3.1-Terminus"),
    ("DeepSeek V3.1 Terminus Pro", "Pro/deepseek-ai/DeepSeek-V3.1-Terminus"),
    ("Qwen3.6 35B A3B", "Qwen/Qwen3.6-35B-A3B"),
    ("Qwen3.6 27B", "Qwen/Qwen3.6-27B"),
    ("Qwen3.5 397B A17B", "Qwen/Qwen3.5-397B-A17B"),
    ("Qwen3.5 122B A10B", "Qwen/Qwen3.5-122B-A10B"),
)

XIAOHUMINI_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("gpt-5.3-chat-latest", "gpt-5.3-chat-latest"),
    ("GPT-5.4 - Latest frontier, 1M context", "gpt-5.4"),
    ("Claude Sonnet 4.6 - Fast + capable", "claude-sonnet-4-6"),
    ("Gemini 3.1 Pro Preview - Fast + capable", "gemini-3.1-pro-preview"),
    ("Grok 4.2 - Fast + capable", "grok-4.2"),
)

QUICK_MODEL_OPTIONS: Final[dict[str, tuple[ModelOption, ...]]] = {
    "openai": OPENAI_QUICK_MODEL_OPTIONS,
    "anthropic": ANTHROPIC_QUICK_MODEL_OPTIONS,
    "google": GOOGLE_QUICK_MODEL_OPTIONS,
    "xai": XAI_QUICK_MODEL_OPTIONS,
    "openrouter": OPENROUTER_QUICK_MODEL_OPTIONS,
    "deepseek": DEEPSEEK_QUICK_MODEL_OPTIONS,
    "siliconflow": SILICONFLOW_MODEL_OPTIONS,
    "xiaohumini": XIAOHUMINI_MODEL_OPTIONS,
}

DEEP_MODEL_OPTIONS: Final[dict[str, tuple[ModelOption, ...]]] = {
    "openai": OPENAI_DEEP_MODEL_OPTIONS,
    "anthropic": ANTHROPIC_DEEP_MODEL_OPTIONS,
    "google": GOOGLE_DEEP_MODEL_OPTIONS,
    "xai": XAI_DEEP_MODEL_OPTIONS,
    "openrouter": OPENROUTER_DEEP_MODEL_OPTIONS,
    "deepseek": DEEPSEEK_DEEP_MODEL_OPTIONS,
    "siliconflow": SILICONFLOW_MODEL_OPTIONS,
    "xiaohumini": XIAOHUMINI_MODEL_OPTIONS,
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
        "claude-opus-4-1-20250805",
        "claude-sonnet-4-20250514",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-haiku-20241022",
        "claude-3-5-sonnet-20241022",
    ),
    "google": (
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-3-pro-preview",
    ),
    "xai": (
        "grok-4-1-fast",
        "grok-4",
    ),
    "deepseek": (),
    "siliconflow": (),
    "openrouter": (),
    # "ollama": (),
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
