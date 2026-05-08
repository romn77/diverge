from datetime import datetime, timezone

from diverge.research.search.providers.base import (
    SearchProvider,
    SearchProviderEmptyResult,
    SearchProviderMalformedResponse,
    SearchProviderPaymentError,
    SearchProviderQuotaError,
    SearchProviderTemporaryError,
    is_monthly_disable_reason,
)
from diverge.research.search.schema import SearchResult


def test_billing_and_quota_errors_are_monthly_disable_errors():
    assert is_monthly_disable_reason("quota_exhausted")
    assert is_monthly_disable_reason("payment_required")
    assert is_monthly_disable_reason("hard_cap_reached")

    assert SearchProviderQuotaError("quota_exhausted", "Quota exhausted").monthly_disable
    assert SearchProviderPaymentError("payment_required", "Payment required").monthly_disable


def test_temporary_empty_and_malformed_errors_do_not_monthly_disable():
    errors = [
        SearchProviderTemporaryError("timeout", "Timed out"),
        SearchProviderTemporaryError("network_error", "Network failed"),
        SearchProviderTemporaryError("server_error", "Server failed"),
        SearchProviderEmptyResult("empty_results", "No results"),
        SearchProviderMalformedResponse("malformed_response", "Malformed response"),
    ]

    assert not any(error.monthly_disable for error in errors)


def test_provider_protocol_returns_search_results():
    class FakeProvider:
        name = "fake"

        def search(
            self,
            query: str,
            *,
            max_results: int,
            language: str | None,
            market: str | None,
        ) -> list[SearchResult]:
            return [
                SearchResult(
                    id="fake-1",
                    provider=self.name,
                    query=query,
                    title="Result",
                    url="https://example.com",
                    retrieved_at=datetime.now(timezone.utc),
                    language=language,
                    market=market,
                )
            ][:max_results]

    provider: SearchProvider = FakeProvider()

    results = provider.search(
        "AAPL latest news",
        max_results=1,
        language="en",
        market="us",
    )

    assert results[0].provider == "fake"
