from __future__ import annotations

from typing import Protocol

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
