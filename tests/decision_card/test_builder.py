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
  "watch_items": ["Breakout volume"],
  "trade_readiness": "READY",
  "data_quality_level": "complete",
  "why_not": {
    "why_not_more_bullish": "Valuation still matters.",
    "why_not_more_bearish": "The thesis remains intact.",
    "why_not_act_now": "The trigger has not fired."
  },
  "action_playbook": {
    "do_now": ["Watch the setup."],
    "trigger_to_act": ["Breakout volume"],
    "invalidation": ["Breaks below trend support"],
    "execution_notes": ["Keep sizing staged."]
  },
  "position_guidance": {
    "suggested_exposure": "No added exposure before trigger confirmation.",
    "max_exposure": null,
    "sizing_rationale": "Setup needs confirmation.",
    "risk_budget_note": "Generic risk guidance."
  }
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
    assert card.card_version == "1.2"
    assert card.trade_readiness == "WAITING_FOR_TRIGGER"
    assert card.data_quality_level == "partial"
    assert card.why_not is not None
    assert card.action_playbook is not None
    assert card.position_guidance is not None
    assert "Price levels were removed" in " ".join(card.data_quality_notes)


def test_build_decision_card_prefers_adk_schema_state_over_legacy_markdown():
    final_state = {
        "portfolio_decision_card": {
            "rating": "OVERWEIGHT",
            "action": "ADD",
            "confidence": "medium",
            "conviction_score": 70,
            "time_horizon": "5-20 trading days",
            "one_line_summary": "Schema state should win.",
            "thesis": "The ADK output_schema sidecar is the stable system output.",
            "key_reasons": [
                {
                    "pillar": "portfolio",
                    "point": "Schema source",
                    "evidence": "Structured sidecar was produced.",
                    "strength": "medium",
                }
            ],
        },
        "final_trade_decision": """Legacy markdown.

```json-decision-card
{
  "rating": "SELL",
  "action": "EXIT",
  "confidence": "low",
  "conviction_score": 10,
  "time_horizon": "now",
  "one_line_summary": "Legacy parser should not win.",
  "thesis": "Legacy block should be fallback only."
}
```
""",
    }

    card = build_decision_card(final_state=final_state, symbol="MSFT")

    assert card.rating == "OVERWEIGHT"
    assert card.action == "ADD"
    assert "ADK output_schema state" in " ".join(card.data_quality_notes)


def test_build_decision_card_uses_language_aware_fallbacks():
    card = build_decision_card(
        final_state={
            "final_trade_decision": """Final ruling.

```json-decision-card
{
  "rating": "OVERWEIGHT",
  "action": "WATCH",
  "confidence": "medium",
  "conviction_score": 73,
  "time_horizon": "5-20 trading days",
  "one_line_summary": "等待触发条件。",
  "thesis": "质量仍强，但需要确认。",
  "price_plan": {
    "current_price": null,
    "entry_zone": null,
    "add_condition": "等待放量突破。",
    "stop_loss": null,
    "take_profit": null,
    "invalidation": ["跌破趋势支撑"],
    "risk_reward_note": null
  },
  "key_reasons": [
    {
      "pillar": "technical",
      "point": "趋势仍强",
      "evidence": "技术报告显示趋势保持。",
      "strength": "medium"
    }
  ],
  "key_risks": ["估值风险"]
}
```
"""
        },
        symbol="AAPL",
        output_language="cn",
    )

    assert card.trade_readiness == "WAITING_FOR_TRIGGER"
    assert card.why_not is not None
    assert "当前" in card.why_not.why_not_act_now


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
