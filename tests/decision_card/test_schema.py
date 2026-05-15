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
    assert card.card_version == "1.2"


def test_decision_card_accepts_v1_1_intelligence_fields():
    card = DecisionCard(
        **_card_payload(
            trade_readiness="WAITING_FOR_TRIGGER",
            trade_readiness_reason="Wait for confirmation.",
            blocking_items=["Breakout not confirmed"],
            data_quality_level="partial",
            data_quality_summary="Some price context is missing.",
            why_not={
                "why_not_more_bullish": "Valuation is not compelling.",
                "why_not_more_bearish": "The thesis is still intact.",
                "why_not_act_now": "The trigger has not fired.",
            },
            action_playbook={
                "do_now": ["Watch"],
                "trigger_to_act": ["Breakout confirmation"],
                "invalidation": ["Trend fails"],
                "execution_notes": ["Stage execution"],
            },
            position_guidance={
                "suggested_exposure": "Small staged exposure after trigger.",
                "max_exposure": None,
                "sizing_rationale": "Data quality is partial.",
                "risk_budget_note": "Generic risk guidance.",
            },
        )
    )

    assert card.trade_readiness == "WAITING_FOR_TRIGGER"
    assert card.data_quality_level == "partial"
    assert card.why_not is not None
    assert card.action_playbook is not None
    assert card.position_guidance is not None


def test_invalid_rating_is_rejected():
    with pytest.raises(ValidationError):
        DecisionCard(**_card_payload(rating="STRONG_BUY"))


def test_invalid_action_is_rejected():
    with pytest.raises(ValidationError):
        DecisionCard(**_card_payload(action="WAIT"))


def test_conviction_score_must_be_between_zero_and_one_hundred():
    with pytest.raises(ValidationError):
        DecisionCard(**_card_payload(conviction_score=101))
