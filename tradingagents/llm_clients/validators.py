"""Model name validators for each provider.

Only validates model names - does NOT enforce limits.
Let LLM providers use their own defaults for unspecified params.
"""

from .model_config import ALLOW_ANY_MODEL_PROVIDERS, VALIDATED_MODELS


def validate_model(provider: str, model: str) -> bool:
    """Check if model name is valid for the given provider.

    For ollama, openrouter, deepseek, xiaohumini - any model is accepted.
    """
    provider_lower = provider.lower()

    if provider_lower in ALLOW_ANY_MODEL_PROVIDERS:
        return True

    if provider_lower not in VALIDATED_MODELS:
        return True

    return model in VALIDATED_MODELS[provider_lower]
