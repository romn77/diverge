from typing import Final

ProviderOption = tuple[str, str, str]
ModelOption = tuple[str, str]

DEFAULT_LLM_PROVIDER: Final[str] = "openai"
DEFAULT_DEEP_MODEL: Final[str] = "gpt-5.5"
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
    ("sub2api", "Sub2API", "https://cc.z2blog.com"),
)

OPENAI_QUICK_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("GPT-5.4 Mini - Fast, strong coding and tool use", "gpt-5.4-mini"),
    ("GPT-5.4 Nano - High-volume simple tasks", "gpt-5.4-nano"),
    ("GPT-5.5 - Latest frontier, complex work", "gpt-5.5"),
    ("GPT-5.4 - Frontier model, 1M context", "gpt-5.4"),
    ("GPT-5.2 - Strong reasoning", "gpt-5.2"),
    ("GPT-5.1 - Flexible reasoning", "gpt-5.1"),
    ("GPT-5 Mini - Balanced speed and capability", "gpt-5-mini"),
    ("GPT-5 Nano - High-throughput simple tasks", "gpt-5-nano"),
    ("GPT-4.1 - Smartest non-reasoning model", "gpt-4.1"),
)

OPENAI_DEEP_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("GPT-5.5 - Latest frontier for complex reasoning and coding", "gpt-5.5"),
    ("GPT-5.4 - Frontier model, 1M context", "gpt-5.4"),
    ("GPT-5.5 Pro - Highest precision, slowest", "gpt-5.5-pro"),
    ("GPT-5.4 Pro - High-compute GPT-5.4", "gpt-5.4-pro"),
    ("GPT-5.2 - Strong reasoning", "gpt-5.2"),
    ("GPT-5.1 - Flexible reasoning", "gpt-5.1"),
    ("GPT-5 - Advanced reasoning", "gpt-5"),
    ("GPT-4.1 - Smartest non-reasoning model", "gpt-4.1"),
    ("GPT-5 Mini - Balanced speed and capability", "gpt-5-mini"),
    ("GPT-5 Nano - High-throughput simple tasks", "gpt-5-nano"),
)

SUB2API_QUICK_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = OPENAI_QUICK_MODEL_OPTIONS
SUB2API_DEEP_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = OPENAI_DEEP_MODEL_OPTIONS

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
    ("Gemini 3.1 Flash Lite - Fast lightweight", "gemini-3.1-flash-lite-preview"),
    ("Gemini 2.5 Flash Lite - Fast lightweight", "gemini-2.5-flash-lite"),
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
        "NVIDIA Nemotron 3 Nano 30B",
        "nvidia/nemotron-3-nano-30b-a3b:free",
    ),
    ("Z.AI GLM 4.5 Air", "z-ai/glm-4.5-air:free"),
)

OPENROUTER_DEEP_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("Z.AI GLM 4.5 Air", "z-ai/glm-4.5-air:free"),
    (
        "NVIDIA Nemotron 3 Nano 30B",
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

SILICONFLOW_QUICK_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("DeepSeek V4 Flash - Latest fast preview", "deepseek-ai/DeepSeek-V4-Flash"),
    ("MiniMax M2.5 - Latest MiniMax standard", "MiniMaxAI/MiniMax-M2.5"),
    ("DeepSeek V3.2 - Efficient latest DeepSeek", "deepseek-ai/DeepSeek-V3.2"),
    ("DeepSeek V3.1 Terminus - Stable efficient chat", "deepseek-ai/DeepSeek-V3.1-Terminus"),
    ("DeepSeek V3 - Latest V3 refresh", "deepseek-ai/DeepSeek-V3"),
    ("Z.AI GLM 4.6 - Efficient GLM chat", "zai-org/GLM-4.6"),
    ("Z.AI GLM 4.6V - Vision-capable GLM", "zai-org/GLM-4.6V"),
    ("Qwen3.6 27B - Compact Qwen", "Qwen/Qwen3.6-27B"),
    ("Qwen3.6 35B A3B - Fast MoE Qwen", "Qwen/Qwen3.6-35B-A3B"),
)

SILICONFLOW_DEEP_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("Kimi K2.6 Pro - Latest Kimi flagship", "Pro/moonshotai/Kimi-K2.6"),
    ("Z.AI GLM 5.1 Pro - Latest GLM flagship", "Pro/zai-org/GLM-5.1"),
    ("MiniMax M2.5 Pro - Higher-throughput MiniMax", "Pro/MiniMaxAI/MiniMax-M2.5"),
    ("Z.AI GLM 5 Pro - Deep agent tasks", "Pro/zai-org/GLM-5"),
    ("Kimi K2.5 Pro - Strong long-context Kimi", "Pro/moonshotai/Kimi-K2.5"),
    ("Z.AI GLM 4.7 Pro - Strong reasoning GLM", "Pro/zai-org/GLM-4.7"),
    ("DeepSeek V3.2 Pro - Latest DeepSeek pro", "Pro/deepseek-ai/DeepSeek-V3.2"),
    ("DeepSeek V3.1 Terminus Pro - Stable pro chat", "Pro/deepseek-ai/DeepSeek-V3.1-Terminus"),
    ("DeepSeek R1 - Reasoning baseline", "deepseek-ai/DeepSeek-R1"),
    ("DeepSeek R1 Pro - Pro reasoning", "Pro/deepseek-ai/DeepSeek-R1"),
    ("DeepSeek V3 Pro - Pro V3 refresh", "Pro/deepseek-ai/DeepSeek-V3"),
    ("Kimi K2 Thinking - Open reasoning Kimi", "moonshotai/Kimi-K2-Thinking"),
    ("Kimi K2 Thinking Pro - Pro reasoning Kimi", "Pro/moonshotai/Kimi-K2-Thinking"),
    ("Qwen3.5 122B A10B - Large Qwen", "Qwen/Qwen3.5-122B-A10B"),
    ("Qwen3.5 397B A17B - Largest Qwen", "Qwen/Qwen3.5-397B-A17B"),
)

SILICONFLOW_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    SILICONFLOW_QUICK_MODEL_OPTIONS + SILICONFLOW_DEEP_MODEL_OPTIONS
)

XIAOHUMINI_QUICK_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("GPT-5.4 Mini - Fast balanced OpenAI", "gpt-5.4-mini"),
    ("GPT-5.4 Nano - High-volume OpenAI tasks", "gpt-5.4-nano"),
    (
        "Grok 4.1 Fast Reasoning - Fast lightweight reasoning",
        "grok-4-1-fast-reasoning",
    ),
    (
        "Grok 4.1 Fast Non-Reasoning - Fast lightweight chat",
        "grok-4-1-fast-non-reasoning",
    ),
    (
        "Gemini 3.1 Flash Lite Preview - Fast multimodal",
        "gemini-3.1-flash-lite-preview",
    ),
    ("DeepSeek V4 Flash - Fast V4", "deepseek-v4-flash"),
    (
        "Grok 4.20 Non-Reasoning - Latest xAI fast",
        "grok-4-20-non-reasoning",
    ),
    ("GPT-5.4 - Strong frontier", "gpt-5.4"),
    ("MiniMax M2.7 - Latest MiniMax", "MiniMax-M2.7"),
    (
        "Claude Sonnet 4.6 - Latest Anthropic balanced",
        "claude-sonnet-4-6",
    ),
)

XIAOHUMINI_DEEP_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    ("GPT-5.5 - Best balanced frontier", "gpt-5.5"),
    ("GPT-5.4 - Deep OpenAI baseline", "gpt-5.4"),
    (
        "Grok 4.20 Reasoning - Latest xAI reasoning",
        "grok-4-20-reasoning",
    ),
    ("Grok 4.2 - Current xAI flagship", "grok-4.2"),
    (
        "Gemini 3.1 Pro Preview - Latest Gemini pro",
        "gemini-3.1-pro-preview",
    ),
    ("MiniMax M2.7 - Latest MiniMax", "MiniMax-M2.7"),
    (
        "Claude Sonnet 4.6 - Latest Anthropic balanced",
        "claude-sonnet-4-6",
    ),
    ("Kimi K2.6 - Latest Kimi", "kimi-k2.6"),
    ("DeepSeek V4 Pro - Latest DeepSeek pro", "deepseek-v4-pro"),
    ("GPT-5.4 Pro - High-compute GPT-5.4", "gpt-5.4-pro"),
    (
        "GPT-5.5 Pro - Highest capability",
        "gpt-5.5-pro",
    ),
)

XIAOHUMINI_MODEL_OPTIONS: Final[tuple[ModelOption, ...]] = (
    XIAOHUMINI_QUICK_MODEL_OPTIONS + XIAOHUMINI_DEEP_MODEL_OPTIONS
)

QUICK_MODEL_OPTIONS: Final[dict[str, tuple[ModelOption, ...]]] = {
    "openai": OPENAI_QUICK_MODEL_OPTIONS,
    "anthropic": ANTHROPIC_QUICK_MODEL_OPTIONS,
    "google": GOOGLE_QUICK_MODEL_OPTIONS,
    "xai": XAI_QUICK_MODEL_OPTIONS,
    "openrouter": OPENROUTER_QUICK_MODEL_OPTIONS,
    "deepseek": DEEPSEEK_QUICK_MODEL_OPTIONS,
    "siliconflow": SILICONFLOW_QUICK_MODEL_OPTIONS,
    "xiaohumini": XIAOHUMINI_QUICK_MODEL_OPTIONS,
    "sub2api": SUB2API_QUICK_MODEL_OPTIONS,
}

DEEP_MODEL_OPTIONS: Final[dict[str, tuple[ModelOption, ...]]] = {
    "openai": OPENAI_DEEP_MODEL_OPTIONS,
    "anthropic": ANTHROPIC_DEEP_MODEL_OPTIONS,
    "google": GOOGLE_DEEP_MODEL_OPTIONS,
    "xai": XAI_DEEP_MODEL_OPTIONS,
    "openrouter": OPENROUTER_DEEP_MODEL_OPTIONS,
    "deepseek": DEEPSEEK_DEEP_MODEL_OPTIONS,
    "siliconflow": SILICONFLOW_DEEP_MODEL_OPTIONS,
    "xiaohumini": XIAOHUMINI_DEEP_MODEL_OPTIONS,
    "sub2api": SUB2API_DEEP_MODEL_OPTIONS,
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
    "sub2api": (),
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
