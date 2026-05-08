from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from diverge.research.search.schema import (
    SearchResponse,
    SearchResult,
    SearchWarning,
    clamp_max_results,
)


def test_search_result_requires_core_fields():
    with pytest.raises(ValidationError) as excinfo:
        SearchResult(
            id="r1",
            provider="brave",
            query="AAPL latest news",
            title="Apple news",
        )

    message = str(excinfo.value)
    assert "url" in message
    assert "retrieved_at" in message


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 5),
        (0, 1),
        (-4, 1),
        (3, 3),
        (12, 5),
    ],
)
def test_clamp_max_results(value, expected):
    assert clamp_max_results(value) == expected


def test_search_result_accepts_missing_published_at_as_unknown():
    result = SearchResult(
        id="r1",
        provider="brave",
        query="AAPL latest news",
        title="Apple news",
        url="https://example.com/apple",
        source="Example",
        snippet="Short snippet",
        published_at=None,
        retrieved_at=datetime.now(timezone.utc),
    )

    assert result.freshness_status == "unknown"


def test_search_warning_carries_provider_reason_and_message():
    warning = SearchWarning(
        provider="tavily",
        reason="quota_exhausted",
        message="Monthly free quota exhausted.",
    )

    assert warning.provider == "tavily"
    assert warning.reason == "quota_exhausted"
    assert warning.message == "Monthly free quota exhausted."


def test_search_response_defaults_structured_lists():
    requested_at = datetime.now(timezone.utc)

    response = SearchResponse(
        agent="News Analyst",
        ticker="AAPL",
        analysis_date="2026-05-08",
        query="AAPL latest stock news",
        requested_at=requested_at,
    )

    assert response.purpose == "default"
    assert response.attempted_providers == []
    assert response.results == []
    assert response.warnings == []
