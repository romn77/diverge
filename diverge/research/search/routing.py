from __future__ import annotations


def provider_order_for_context(*, market: str, language: str | None) -> list[str]:
    normalized_market = str(market or "").strip().lower()
    normalized_language = str(language or "").strip().lower()
    if normalized_market in {"cn", "hk"} or normalized_language in {
        "cn",
        "zh",
        "zh-cn",
    }:
        return ["bocha", "brave", "tavily"]
    return ["brave", "tavily"]


def _provider_available(provider: dict) -> bool:
    if not provider.get("enabled"):
        return False
    if provider.get("key_status") != "configured":
        return False
    if provider.get("hard_cap_reached"):
        return False
    remaining = provider.get("remaining_to_hard_cap")
    if remaining is not None and int(remaining) <= 0:
        return False
    return True


def available_provider_chain(order: list[str], quota_summary: dict) -> list[str]:
    global_config = quota_summary.get("global") or {}
    if not global_config.get("enabled"):
        return []

    providers = {
        str(provider.get("provider")): provider
        for provider in quota_summary.get("providers", [])
        if isinstance(provider, dict)
    }
    return [
        provider
        for provider in order
        if provider in providers and _provider_available(providers[provider])
    ]
