from __future__ import annotations

import pytest

from diverge.research.search.providers.base import (
    SearchProviderAuthError,
    SearchProviderPaymentError,
    SearchProviderQuotaError,
    SearchProviderTemporaryError,
)
from diverge.research.search.providers.bocha import BochaSearchProvider
from diverge.research.search.providers.brave import BraveSearchProvider
from diverge.research.search.providers.tavily import TavilySearchProvider


class FakeResponse:
    def __init__(
        self, status_code: int = 200, payload: dict | None = None, text: str = ""
    ):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.response

    def post(self, url: str, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.response


def test_brave_maps_web_results_into_search_results():
    client = FakeClient(
        FakeResponse(
            payload={
                "web": {
                    "results": [
                        {
                            "title": "Apple shares rise",
                            "url": "https://example.com/aapl",
                            "description": "Guidance improved.",
                            "profile": {"name": "Example News"},
                            "datePublished": "2026-05-08T10:00:00Z",
                        }
                    ]
                }
            }
        )
    )

    results = BraveSearchProvider(api_key="key", client=client).search(
        "AAPL latest news",
        max_results=5,
        language="en",
        market="us",
    )

    assert len(results) == 1
    assert results[0].provider == "brave"
    assert results[0].title == "Apple shares rise"
    assert results[0].source == "Example News"
    assert results[0].published_at is not None
    assert client.calls[0][0] == "GET"


def test_tavily_maps_result_objects_into_search_results():
    client = FakeClient(
        FakeResponse(
            payload={
                "results": [
                    {
                        "title": "AAPL sentiment improves",
                        "url": "https://example.com/sentiment",
                        "content": "Investors warmed to the update.",
                        "published_date": "2026-05-08",
                        "score": 0.82,
                    }
                ]
            }
        )
    )

    results = TavilySearchProvider(api_key="key", client=client).search(
        "AAPL sentiment",
        max_results=3,
        language="en",
        market="us",
    )

    assert results[0].provider == "tavily"
    assert results[0].snippet == "Investors warmed to the update."
    assert results[0].relevance_score == 0.82
    assert client.calls[0][0] == "POST"


def test_bocha_maps_chinese_search_results_into_search_results():
    client = FakeClient(
        FakeResponse(
            payload={
                "data": {
                    "webPages": {
                        "value": [
                            {
                                "name": "苹果公司最新消息",
                                "url": "https://example.cn/aapl",
                                "snippet": "苹果公司发布新公告。",
                                "siteName": "财联社",
                                "datePublished": "2026-05-08T08:00:00+08:00",
                            }
                        ]
                    }
                }
            }
        )
    )

    results = BochaSearchProvider(api_key="key", client=client).search(
        "AAPL 最新 消息",
        max_results=2,
        language="cn",
        market="cn",
    )

    assert results[0].provider == "bocha"
    assert results[0].title == "苹果公司最新消息"
    assert results[0].source == "财联社"
    assert results[0].language == "cn"


def test_missing_key_raises_auth_error_before_http_request():
    client = FakeClient(FakeResponse())

    with pytest.raises(SearchProviderAuthError):
        BraveSearchProvider(api_key="", client=client).search(
            "AAPL latest news",
            max_results=1,
            language="en",
            market="us",
        )

    assert client.calls == []


def test_payment_and_monthly_quota_responses_raise_monthly_disable_errors():
    payment_client = FakeClient(FakeResponse(status_code=402, text="payment required"))
    quota_client = FakeClient(
        FakeResponse(status_code=429, text="monthly quota exceeded for this account")
    )

    with pytest.raises(SearchProviderPaymentError):
        BraveSearchProvider(api_key="key", client=payment_client).search(
            "AAPL",
            max_results=1,
            language="en",
            market="us",
        )

    with pytest.raises(SearchProviderQuotaError):
        TavilySearchProvider(api_key="key", client=quota_client).search(
            "AAPL",
            max_results=1,
            language="en",
            market="us",
        )


def test_plain_429_is_temporary_error():
    client = FakeClient(FakeResponse(status_code=429, text="rate limit"))

    with pytest.raises(SearchProviderTemporaryError):
        BochaSearchProvider(api_key="key", client=client).search(
            "AAPL",
            max_results=1,
            language="en",
            market="us",
        )
