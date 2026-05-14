from diverge.decision_card.parser import (
    extract_decision_card_block,
    extract_highlights_block,
    extract_rating_from_text,
    infer_action_from_rating,
    normalize_rating,
)


def test_extract_decision_card_block():
    markdown = """Decision.

```json-decision-card
{"rating": "OVERWEIGHT", "action": "WATCH"}
```
"""

    assert extract_decision_card_block(markdown) == {
        "rating": "OVERWEIGHT",
        "action": "WATCH",
    }


def test_extract_highlights_block_supports_five_rating_values():
    markdown = """```json-highlights
{"category": "portfolio_decision", "signal": "UNDERWEIGHT"}
```"""

    assert extract_highlights_block(markdown)["signal"] == "UNDERWEIGHT"


def test_normalize_rating_defaults_to_hold_for_unknown_values():
    assert normalize_rating("overweight") == "OVERWEIGHT"
    assert normalize_rating("nope") == "HOLD"


def test_extract_rating_from_final_proposal_text():
    assert (
        extract_rating_from_text("FINAL TRANSACTION PROPOSAL: **UNDERWEIGHT**")
        == "UNDERWEIGHT"
    )


def test_infer_action_from_rating():
    assert infer_action_from_rating("BUY") == "OPEN"
    assert infer_action_from_rating("SELL") == "EXIT"
