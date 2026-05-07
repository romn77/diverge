from __future__ import annotations

import json
import re
from typing import Any

from diverge.decision_card.schema import PortfolioAction, PortfolioRating


DECISION_CARD_BLOCK_RE = re.compile(
    r"```json-decision-card[ \t]*\r?\n([\s\S]*?)\r?\n?```",
    re.MULTILINE,
)
HIGHLIGHTS_BLOCK_RE = re.compile(
    r"```json-highlights[ \t]*\r?\n([\s\S]*?)\r?\n?```",
    re.MULTILINE,
)
RATING_RE = re.compile(
    r"(?:rating|final(?:\s+transaction)?\s+(?:proposal|decision)|decision)\s*[:：]\s*\**\s*"
    r"(BUY|OVERWEIGHT|HOLD|UNDERWEIGHT|SELL)\b",
    re.IGNORECASE,
)

RATING_VALUES: tuple[PortfolioRating, ...] = (
    "BUY",
    "OVERWEIGHT",
    "HOLD",
    "UNDERWEIGHT",
    "SELL",
)
ACTION_VALUES: tuple[PortfolioAction, ...] = (
    "OPEN",
    "ADD",
    "MAINTAIN",
    "TRIM",
    "EXIT",
    "WATCH",
    "NO_ACTION",
    "AVOID",
)


def _parse_json_block(markdown: str, pattern: re.Pattern[str]) -> dict[str, Any] | None:
    match = pattern.search(markdown or "")
    if not match:
        return None
    raw_json = (match.group(1) or "").strip()
    if not raw_json:
        return None
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def extract_decision_card_block(markdown: str) -> dict[str, Any] | None:
    return _parse_json_block(markdown, DECISION_CARD_BLOCK_RE)


def extract_highlights_block(markdown: str) -> dict[str, Any] | None:
    return _parse_json_block(markdown, HIGHLIGHTS_BLOCK_RE)


def normalize_rating(value: str | None) -> PortfolioRating:
    candidate = (value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if candidate in RATING_VALUES:
        return candidate  # type: ignore[return-value]
    return "HOLD"


def normalize_action(value: str | None, rating: PortfolioRating) -> PortfolioAction:
    candidate = (value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if candidate in ACTION_VALUES:
        return candidate  # type: ignore[return-value]
    return infer_action_from_rating(rating)


def normalize_confidence(value: str | None) -> str:
    candidate = (value or "").strip().lower()
    if candidate in {"high", "medium", "low"}:
        return candidate
    return "low"


def infer_action_from_rating(rating: PortfolioRating) -> PortfolioAction:
    return {
        "BUY": "OPEN",
        "OVERWEIGHT": "ADD",
        "HOLD": "MAINTAIN",
        "UNDERWEIGHT": "TRIM",
        "SELL": "EXIT",
    }[rating]


def extract_rating_from_text(markdown: str) -> PortfolioRating | None:
    match = RATING_RE.search(markdown or "")
    if match and match.group(1):
        return normalize_rating(match.group(1))
    upper = (markdown or "").upper()
    for rating in RATING_VALUES:
        if re.search(rf"\b{rating}\b", upper):
            return rating
    return None
