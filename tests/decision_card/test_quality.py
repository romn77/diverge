from datetime import datetime, timezone

from diverge.decision_card.quality import apply_quality_gates
from diverge.decision_card.schema import DecisionCard


def _card(**overrides):
    payload = {
        "symbol": "AAPL",
        "generated_at": datetime.now(timezone.utc),
        "rating": "BUY",
        "action": "ADD",
        "confidence": "high",
        "conviction_score": 80,
        "time_horizon": "5-20 trading days",
        "one_line_summary": "Constructive setup.",
        "thesis": "Constructive setup with risk controls.",
        "price_plan": {
            "current_price": None,
            "entry_zone": None,
            "add_condition": "Wait for confirmation.",
            "stop_loss": None,
            "take_profit": None,
            "invalidation": ["Trend support breaks"],
            "risk_reward_note": None,
        },
        "key_reasons": [
            {
                "pillar": "technical",
                "point": "Trend support",
                "evidence": "Market report cited rising moving averages.",
                "strength": "medium",
            }
        ],
        "key_risks": ["Valuation reset"],
    }
    payload.update(overrides)
    return DecisionCard(**payload)


def test_sell_add_is_corrected_to_exit():
    card = apply_quality_gates(_card(rating="SELL", action="ADD"))

    assert card.action == "EXIT"
    assert "SELL cannot map to OPEN or ADD" in " ".join(card.data_quality_notes)


def test_buy_exit_is_corrected_to_watch():
    card = apply_quality_gates(_card(rating="BUY", action="EXIT"))

    assert card.action == "WATCH"


def test_model_conviction_score_is_preserved():
    card = apply_quality_gates(_card(conviction_score=62))

    assert card.conviction_score == 62


def test_missing_price_context_removes_stop_loss_and_take_profit():
    card = apply_quality_gates(
        _card(
            price_plan={
                "current_price": None,
                "entry_zone": None,
                "add_condition": "Wait for setup.",
                "stop_loss": 10,
                "take_profit": [20],
                "invalidation": ["Support fails"],
                "risk_reward_note": None,
            }
        )
    )

    assert card.price_plan.stop_loss is None
    assert card.price_plan.take_profit is None


def test_confidence_downgrades_when_quality_issues_accumulate():
    card = apply_quality_gates(
        _card(
            confidence="high",
            key_reasons=[],
            key_risks=[],
            price_plan={
                "current_price": None,
                "entry_zone": None,
                "add_condition": None,
                "stop_loss": None,
                "take_profit": None,
                "invalidation": [],
                "risk_reward_note": None,
            },
        )
    )

    assert card.confidence == "low"
