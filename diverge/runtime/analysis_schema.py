from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

HISTORICAL_TRADE_FEEDBACK_KEY = "historical_trade_feedback"
HISTORICAL_TRADE_REVIEWS_KEY = "historical_trade_reviews"
TRADE_FEEDBACK_ARTIFACT_TYPE = "trade_feedback"


def _normalize_prompt(value: Any) -> str:
    return str(value or "")


def _normalize_reviews(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, dict))


@dataclass(frozen=True)
class HistoricalTradeFeedback:
    prompt: str = ""
    review_items: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_values(cls, *, prompt: Any, reviews: Any) -> HistoricalTradeFeedback:
        return cls(
            prompt=_normalize_prompt(prompt),
            review_items=_normalize_reviews(reviews),
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> HistoricalTradeFeedback:
        return cls.from_values(
            prompt=state.get(HISTORICAL_TRADE_FEEDBACK_KEY),
            reviews=state.get(HISTORICAL_TRADE_REVIEWS_KEY),
        )

    def reviews(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.review_items]

    def initial_state_fields(self) -> dict[str, Any]:
        return {
            HISTORICAL_TRADE_FEEDBACK_KEY: self.prompt,
            HISTORICAL_TRADE_REVIEWS_KEY: self.reviews(),
        }

    def artifact(self, *, ticker: str) -> dict[str, Any] | None:
        reviews = self.reviews()
        if not reviews:
            return None
        return {
            "type": TRADE_FEEDBACK_ARTIFACT_TYPE,
            "ticker": ticker,
            "prompt": self.prompt,
            "reviews": reviews,
        }


def historical_trade_feedback_from_values(
    *,
    prompt: Any,
    reviews: Any,
) -> HistoricalTradeFeedback:
    return HistoricalTradeFeedback.from_values(prompt=prompt, reviews=reviews)


def historical_trade_feedback_from_state(
    state: Mapping[str, Any],
) -> HistoricalTradeFeedback:
    return HistoricalTradeFeedback.from_state(state)


def trade_feedback_artifact_from_state(
    state: Mapping[str, Any],
    *,
    ticker: str,
) -> dict[str, Any] | None:
    return historical_trade_feedback_from_state(state).artifact(ticker=ticker)
