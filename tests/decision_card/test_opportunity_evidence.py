from __future__ import annotations

from diverge.decision_card.builder import build_decision_card


def test_decision_card_attaches_opportunity_evidence_to_v12_card():
    card = build_decision_card(
        final_state={
            "final_trade_decision": "BUY",
            "opportunity_context": {
                "trigger": "theme_breakout + capital_confirmed",
                "theme_id": "ai_compute",
                "theme_name": "AI Compute",
                "candidate_type": "leader",
                "source_run_id": "radar_1",
                "backtest_summary": {
                    "sample_size": 12,
                    "holding_periods": {"5d": {"win_rate": 0.58}},
                },
                "risk_flags": ["short_term_overheated"],
            },
        },
        symbol="300001.SZ",
        report_id="report-1",
    )

    assert card.card_version == "1.2"
    assert card.opportunity_evidence is not None
    assert card.opportunity_evidence.theme_id == "ai_compute"
    assert any(reason.pillar == "opportunity" for reason in card.key_reasons)
