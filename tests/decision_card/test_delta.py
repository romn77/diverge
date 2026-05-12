from datetime import datetime, timezone

from diverge.decision_card.delta import (
    build_decision_delta,
    find_previous_decision_card,
    save_decision_delta,
)
from diverge.decision_card.schema import DecisionCard
from diverge.decision_card.storage import save_decision_card


def _card(
    report_id: str,
    *,
    symbol="AAPL",
    rating="HOLD",
    action="NO_ACTION",
    score=50,
):
    return DecisionCard(
        report_id=report_id,
        symbol=symbol,
        generated_at=datetime.now(timezone.utc),
        rating=rating,
        action=action,
        confidence="medium",
        conviction_score=score,
        time_horizon="5-20 trading days",
        one_line_summary="Summary.",
        thesis="Thesis.",
        key_reasons=[
            {
                "pillar": "portfolio",
                "point": "Evidence",
                "evidence": "Concrete evidence.",
                "strength": "medium",
            }
        ],
        key_risks=["Risk"],
        trade_readiness="WAITING_FOR_TRIGGER",
    )


def test_build_decision_delta_compares_stable_fields():
    previous = _card("AAPL_old", rating="HOLD", action="NO_ACTION", score=58)
    current = _card("AAPL_new", rating="OVERWEIGHT", action="WATCH", score=73)

    delta = build_decision_delta(
        current_card=current,
        previous_card=previous,
        current_report_id="AAPL_new",
    )

    assert delta.previous_report_id == "AAPL_old"
    assert delta.rating.changed is True
    assert delta.rating.previous == "HOLD"
    assert delta.rating.current == "OVERWEIGHT"
    assert delta.conviction_score.previous == 58
    assert "changed" in delta.summary


def test_find_previous_decision_card_uses_same_symbol(tmp_path):
    old_dir = tmp_path / "AAPL_old"
    other_dir = tmp_path / "MSFT_old"
    save_decision_card(_card("AAPL_old"), old_dir)
    save_decision_card(_card("MSFT_old", symbol="MSFT"), other_dir)

    previous = find_previous_decision_card(
        current_card=_card("AAPL_new", rating="OVERWEIGHT"),
        candidate_report_dirs=[other_dir, old_dir],
        current_report_id="AAPL_new",
    )

    assert previous is not None
    assert previous.report_id == "AAPL_old"


def test_save_decision_delta_writes_artifact(tmp_path):
    delta = build_decision_delta(
        current_card=_card("AAPL_new", rating="OVERWEIGHT"),
        previous_card=_card("AAPL_old"),
        current_report_id="AAPL_new",
    )

    path = save_decision_delta(delta, tmp_path)

    assert path == tmp_path / "artifacts" / "decision_delta.json"
    assert path.is_file()
