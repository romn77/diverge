from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from diverge.decision_card.schema import DecisionCard


def _card_payload(**overrides):
    payload = {
        "symbol": "AAPL",
        "generated_at": datetime.now(timezone.utc),
        "rating": "OVERWEIGHT",
        "action": "WATCH",
        "confidence": "medium",
        "conviction_score": 73,
        "time_horizon": "5-20 trading days",
        "one_line_summary": "Wait for a better entry before adding.",
        "thesis": "Quality remains strong, but the setup needs confirmation.",
        "price_plan": {
            "current_price": None,
            "entry_zone": None,
            "add_condition": "Wait for pullback or breakout confirmation.",
            "stop_loss": None,
            "take_profit": None,
            "invalidation": ["Break below trend support"],
            "risk_reward_note": "Current risk/reward is not clean enough.",
        },
        "key_reasons": [],
        "key_risks": ["Valuation reset"],
        "catalysts": [],
        "watch_items": ["Volume confirmation"],
        "data_quality_notes": [],
        "source_report_paths": [],
    }
    payload.update(overrides)
    return payload


def test_valid_decision_card_passes_validation():
    card = DecisionCard(**_card_payload())

    assert card.rating == "OVERWEIGHT"
    assert card.action == "WATCH"


def test_invalid_rating_is_rejected():
    with pytest.raises(ValidationError):
        DecisionCard(**_card_payload(rating="STRONG_BUY"))


def test_invalid_action_is_rejected():
    with pytest.raises(ValidationError):
        DecisionCard(**_card_payload(action="WAIT"))


def test_conviction_score_must_be_between_zero_and_one_hundred():
    with pytest.raises(ValidationError):
        DecisionCard(**_card_payload(conviction_score=101))
