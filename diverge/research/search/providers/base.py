from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from diverge.research.search.schema import SearchResult


MONTHLY_DISABLE_REASONS = {
    "quota_exhausted",
    "payment_required",
    "insufficient_balance",
    "monthly_limit_reached",
    "hard_cap_reached",
    "account_disabled_for_billing",
}


def is_monthly_disable_reason(reason: str) -> bool:
    return str(reason or "").strip().lower() in MONTHLY_DISABLE_REASONS


class SearchProviderError(Exception):
    default_monthly_disable = False

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        monthly_disable: bool | None = None,
    ) -> None:
        self.reason = str(reason or "provider_error")
        self.message = str(message or self.reason)
        if monthly_disable is None:
            monthly_disable = self.default_monthly_disable or is_monthly_disable_reason(
                self.reason
            )
        self.monthly_disable = bool(monthly_disable)
        super().__init__(self.message)


class SearchProviderAuthError(SearchProviderError):
    pass


class SearchProviderQuotaError(SearchProviderError):
    default_monthly_disable = True


class SearchProviderPaymentError(SearchProviderError):
    default_monthly_disable = True


class SearchProviderTemporaryError(SearchProviderError):
    pass


class SearchProviderEmptyResult(SearchProviderError):
    pass


class SearchProviderMalformedResponse(SearchProviderError):
    pass


class SearchProvider(Protocol):
    name: str

    def search(
        self,
        query: str,
        *,
        max_results: int,
        language: str | None,
        market: str | None,
    ) -> list[SearchResult]:
        ...


def require_api_key(api_key: str | None, provider: str) -> str:
    normalized = str(api_key or "").strip()
    if not normalized:
        raise SearchProviderAuthError(
            "missing_api_key",
            f"{provider} API key is not configured.",
        )
    return normalized


def parse_provider_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _looks_like_monthly_quota(text: str) -> bool:
    lowered = text.lower()
    quota_markers = (
        "monthly quota",
        "monthly limit",
        "quota exceeded",
        "quota_exhausted",
        "hard cap",
        "insufficient balance",
        "account disabled for billing",
    )
    return any(marker in lowered for marker in quota_markers)


def _looks_like_payment(text: str) -> bool:
    lowered = text.lower()
    return "payment required" in lowered or "billing" in lowered


def raise_for_http_status(provider: str, status_code: int, text: str) -> None:
    if status_code < 400:
        return
    if status_code in {401, 403} and not _looks_like_monthly_quota(text):
        raise SearchProviderAuthError("auth_error", f"{provider}: authentication failed")
    if status_code == 402 or _looks_like_payment(text):
        raise SearchProviderPaymentError(
            "payment_required",
            f"{provider}: payment or billing required",
        )
    if status_code == 429:
        if _looks_like_monthly_quota(text):
            raise SearchProviderQuotaError(
                "quota_exhausted",
                f"{provider}: monthly quota exhausted",
            )
        raise SearchProviderTemporaryError("rate_limited", f"{provider}: rate limited")
    if status_code >= 500:
        raise SearchProviderTemporaryError(
            "server_error",
            f"{provider}: server error {status_code}",
        )
    raise SearchProviderTemporaryError(
        "http_error",
        f"{provider}: HTTP error {status_code}",
    )


def raise_for_provider_payload(provider: str, payload: dict[str, Any]) -> None:
    message_parts = []
    for key in ("error", "message", "msg", "detail", "code"):
        value = payload.get(key)
        if value:
            message_parts.append(str(value))
    message = " ".join(message_parts)
    if _looks_like_monthly_quota(message):
        raise SearchProviderQuotaError(
            "quota_exhausted",
            f"{provider}: monthly quota exhausted",
        )
    if _looks_like_payment(message):
        raise SearchProviderPaymentError(
            "payment_required",
            f"{provider}: payment or billing required",
        )


def response_json(provider: str, response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise SearchProviderMalformedResponse(
            "malformed_response",
            f"{provider}: response JSON could not be parsed",
        ) from exc
    if not isinstance(payload, dict):
        raise SearchProviderMalformedResponse(
            "malformed_response",
            f"{provider}: response JSON root must be an object",
        )
    raise_for_provider_payload(provider, payload)
    return payload
