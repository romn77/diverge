from diverge.decision_card.builder import build_decision_card


def test_build_decision_card_prefers_json_decision_card():
    final_state = {
        "final_trade_decision": """Final ruling.

```json-decision-card
{
  "rating": "OVERWEIGHT",
  "action": "WATCH",
  "confidence": "medium",
  "conviction_score": 88,
  "time_horizon": "5-20 trading days",
  "one_line_summary": "Quality is strong, but wait for confirmation.",
  "thesis": "The business is durable and the trend is constructive, but entry risk is elevated.",
  "price_plan": {
    "current_price": null,
    "entry_zone": null,
    "add_condition": "Add only after a pullback or breakout confirmation.",
    "stop_loss": 100,
    "take_profit": [130],
    "invalidation": ["Breaks below trend support"],
    "risk_reward_note": "Wait for a cleaner risk/reward."
  },
  "key_reasons": [
    {
      "pillar": "fundamentals",
      "point": "Durable quality",
      "evidence": "Analysts cited resilient margins.",
      "strength": "strong",
      "source": "fundamentals_analyst",
      "data_date": "2026-05-07",
      "confidence": "high",
      "limitation": "Segment margins unavailable"
    }
  ],
  "key_risks": ["Valuation reset"],
  "watch_items": ["Breakout volume"]
}
```
""",
    }

    card = build_decision_card(
        final_state=final_state,
        symbol="AAPL",
        report_id="AAPL_20260507_120000",
        analysis_date="2026-05-07",
    )

    assert card.rating == "OVERWEIGHT"
    assert card.action == "WATCH"
    assert card.conviction_score == 88
    assert card.key_reasons[0].source == "fundamentals_analyst"
    assert card.key_reasons[0].data_date == "2026-05-07"
    assert card.key_reasons[0].confidence == "high"
    assert card.key_reasons[0].limitation == "Segment margins unavailable"
    assert card.price_plan.stop_loss is None
    assert card.price_plan.take_profit is None
    assert "Price levels were removed" in " ".join(card.data_quality_notes)


def test_build_decision_card_falls_back_to_json_highlights():
    final_state = {
        "final_trade_decision": """Portfolio ruling.

```json-highlights
{
  "category": "portfolio_decision",
  "signal": "UNDERWEIGHT",
  "signal_confidence": "medium",
  "summary": "Reduce exposure until risk/reward improves.",
  "final_decision": "UNDERWEIGHT",
  "decision_basis": "Risk analysts highlighted unfavorable downside asymmetry.",
  "strategic_actions": [
    {"action": "Trim into strength.", "priority": "conditional"}
  ],
  "risk_warnings": ["Margin pressure"]
}
```
""",
    }

    card = build_decision_card(final_state=final_state, symbol="MSFT")

    assert card.rating == "UNDERWEIGHT"
    assert card.action == "TRIM"
    assert card.key_risks == ["Margin pressure"]
    assert "legacy json-highlights" in " ".join(card.data_quality_notes)


def test_build_decision_card_uses_text_rating_when_structured_blocks_are_absent():
    card = build_decision_card(
        final_state={"final_trade_decision": "Rating: Sell. Exit the position."},
        symbol="TSLA",
    )

    assert card.rating == "SELL"
    assert card.action == "EXIT"
    assert card.confidence == "low"


def test_build_decision_card_returns_low_confidence_fallback_without_signal():
    card = build_decision_card(
        final_state={"final_trade_decision": "No clear call."}, symbol="QQQ"
    )

    assert card.rating == "HOLD"
    assert card.action == "NO_ACTION"
    assert card.confidence == "low"
