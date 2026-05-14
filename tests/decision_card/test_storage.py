import json

from diverge.decision_card.builder import build_fallback_decision_card
from diverge.decision_card.storage import save_decision_card


def test_save_decision_card_writes_artifact(tmp_path):
    card = build_fallback_decision_card(symbol="AAPL", report_id="AAPL_report")

    path = save_decision_card(card, tmp_path)

    assert path == tmp_path / "artifacts" / "decision_card.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["symbol"] == "AAPL"
