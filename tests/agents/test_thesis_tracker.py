import json
import tempfile
from pathlib import Path

from tradingagents.research.thesis_tracker import build_thesis_artifact
from tradingagents.runner import save_report_to_disk


def _final_state():
    return {
        "company_of_interest": "MSFT",
        "trade_date": "2026-03-20",
        "market_report": "# Market\n\nMacro backdrop is steady.",
        "sentiment_report": "# Sentiment\n\nPositioning is constructive.",
        "news_report": (
            "# News\n\n"
            "## Post-Earnings Review Focus\n\n"
            "- Reported revenue: 97B\n"
            "- Reported EPS: 1.72\n"
            "- Guidance change: Raised services outlook\n"
        ),
        "fundamentals_report": (
            "# Fundamentals\n\n"
            "## DCF Summary\n\n"
            "| Metric | Value |\n| --- | --- |\n| Fair Value / Share | $420.00 |\n\n"
            "## Multiples Summary\n\n"
            "| Multiple | Value |\n| --- | --- |\n| EV/EBITDA | 12.5x |\n"
        ),
        "investment_plan": "Buy the name on durable cloud growth and resilient cash generation.",
        "trader_investment_plan": "Scale in over two sessions and respect the stop discipline.",
        "final_trade_decision": "BUY",
        "investment_debate_state": {
            "bull_history": "Bull Analyst: Upside remains supported by cloud and margin durability.",
            "bear_history": "Bear Analyst: Valuation leaves less room for execution mistakes.",
            "judge_decision": "Research Manager: BUY with earnings follow-through as the next key catalyst.",
        },
        "risk_debate_state": {
            "aggressive_history": "Aggressive Analyst: Momentum remains favorable.",
            "conservative_history": "Conservative Analyst: Watch valuation compression risk.",
            "neutral_history": "Neutral Analyst: Size prudently around event risk.",
            "judge_decision": "Portfolio Manager: BUY with tight risk controls.",
        },
    }


def test_thesis_artifact_can_be_created_from_completed_report_state():
    artifact = build_thesis_artifact(_final_state(), ticker="MSFT")

    assert artifact["ticker"] == "MSFT"
    assert artifact["thesis_summary"]
    assert artifact["supporting_evidence"]
    assert artifact["invalidation_signals"]
    assert artifact["next_catalysts"]


def test_thesis_artifact_serialization_does_not_break_report_saving():
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = save_report_to_disk(_final_state(), "MSFT", Path(temp_dir))

        assert report_path.is_file()
        thesis_path = Path(temp_dir) / "artifacts" / "thesis.json"
        assert thesis_path.is_file()

        payload = json.loads(thesis_path.read_text(encoding="utf-8"))
        assert payload["ticker"] == "MSFT"
        assert payload["thesis_summary"]


def test_thesis_artifact_ignores_json_highlights_payload_text():
    final_state = _final_state()
    final_state["investment_debate_state"]["bear_history"] = (
        "Bear Analyst: Demand is softening and valuation remains stretched.\n\n"
        "```json-highlights\n"
        '{\n  "category": "bear_case",\n  "signal": "SELL",\n'
        '  "signal_confidence": "medium",\n  "summary": "Too expensive."\n}\n'
        "```"
    )

    artifact = build_thesis_artifact(final_state, ticker="MSFT")

    joined = " ".join(artifact["invalidation_signals"])
    assert '"category"' not in joined
    assert '"signal"' not in joined
