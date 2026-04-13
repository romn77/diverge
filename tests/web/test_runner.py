import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from tradingagents.runner import (
    AnalysisRequest,
    AnalysisTracker,
    run_analysis_streaming,
    save_report_to_disk,
)


class _FakePropagator:
    def create_initial_state(self, *_args, **_kwargs):
        return {}

    def get_graph_args(self):
        return {}


class _FakeTradingAgentsGraph:
    def __init__(self, *_args, **_kwargs):
        self.propagator = _FakePropagator()


class AnalysisTrackerTests(unittest.TestCase):
    def test_tracker_derives_three_state_stage_progress_from_agent_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = AnalysisTracker(["market", "news"], Path(temp_dir))

            initial = tracker.to_progress(status="pending", message="Queued")
            self.assertEqual(initial.stage_status["Analysts"], "not_started")
            self.assertEqual(initial.stage_status["Research"], "not_started")
            self.assertEqual(initial.stage_status["Portfolio"], "not_started")

            tracker.update_agent_status("Market Analyst", "in_progress")
            running = tracker.to_progress(status="running", message="Market analyst started")
            self.assertEqual(running.stage_status["Analysts"], "processing")
            self.assertEqual(running.current_agent, "Market Analyst")

            tracker.update_agent_status("Market Analyst", "completed")
            tracker.update_agent_status("News Analyst", "completed")
            finished = tracker.to_progress(status="running", message="Analysts finished")
            self.assertEqual(finished.stage_status["Analysts"], "completed")

    def test_tracker_writes_partial_reports_into_final_stage_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = AnalysisTracker(["market"], Path(temp_dir))

            tracker.update_report_section("market_report", "# Market\n\nMomentum is positive.")
            tracker.update_report_section("trader_investment_plan", "Reduce risk and wait.")

            market_path = Path(temp_dir) / "1_analysts" / "market.md"
            trader_path = Path(temp_dir) / "3_trading" / "trader.md"

            self.assertTrue(market_path.is_file())
            self.assertTrue(trader_path.is_file())
            self.assertIn("Momentum is positive", market_path.read_text(encoding="utf-8"))
            self.assertIn("Reduce risk", trader_path.read_text(encoding="utf-8"))

    def test_save_report_to_disk_keeps_fundamentals_report_and_writes_thesis_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            final_state = {
                "market_report": "# Market\n\nStable backdrop.",
                "sentiment_report": "# Sentiment\n\nNeutral buzz.",
                "news_report": "# News\n\nCatalysts remain active.",
                "fundamentals_report": (
                    "# Fundamentals\n\n"
                    "## DCF Summary\n\n"
                    "| Metric | Value |\n| --- | --- |\n| Fair Value / Share | $420.00 |\n\n"
                    "```json-highlights\n"
                    '{\n  "category": "fundamentals",\n  "signal": "BUY",\n'
                    '  "signal_confidence": "medium",\n  "summary": "Durable cash generation.",\n'
                    '  "metrics": [],\n  "financial_health": "Strong"\n}\n'
                    "```"
                ),
                "investment_plan": "Lean long with a quality bias.",
                "trader_investment_plan": "Build the position gradually.",
                "investment_debate_state": {
                    "bull_history": "Bull Analyst: Free cash flow remains durable.",
                    "bear_history": "Bear Analyst: Multiple compression is still a risk.",
                    "judge_decision": "Research Manager: BUY with disciplined sizing.",
                },
                "risk_debate_state": {
                    "aggressive_history": "Aggressive Analyst: Momentum confirms the setup.",
                    "conservative_history": "Conservative Analyst: Guard against event volatility.",
                    "neutral_history": "Neutral Analyst: Keep exposure balanced.",
                    "judge_decision": "Portfolio Manager: BUY with risk controls.",
                },
                "historical_trade_feedback": "Historical trade feedback for ticker MSFT:\n1. Respect the planned stop.",
                "historical_trade_reviews": [
                    {
                        "trade_id": "trade-1",
                        "review_type": "entry_review",
                        "thesis_assessment": "Thesis was grounded in durable cloud demand.",
                    }
                ],
            }

            report_path = save_report_to_disk(final_state, "MSFT", Path(temp_dir))

            fundamentals_path = Path(temp_dir) / "1_analysts" / "fundamentals.md"
            thesis_path = Path(temp_dir) / "artifacts" / "thesis.json"
            trade_feedback_path = Path(temp_dir) / "artifacts" / "trade_feedback.json"

            self.assertTrue(report_path.is_file())
            self.assertTrue(fundamentals_path.is_file())
            self.assertTrue(thesis_path.is_file())
            self.assertTrue(trade_feedback_path.is_file())
            self.assertIn("## DCF Summary", fundamentals_path.read_text(encoding="utf-8"))

            thesis_payload = json.loads(thesis_path.read_text(encoding="utf-8"))
            self.assertEqual(thesis_payload["type"], "thesis")
            self.assertEqual(thesis_payload["ticker"], "MSFT")

            trade_feedback_payload = json.loads(
                trade_feedback_path.read_text(encoding="utf-8")
            )
            self.assertEqual(trade_feedback_payload["type"], "trade_feedback")
            self.assertEqual(len(trade_feedback_payload["reviews"]), 1)

    def test_run_analysis_streaming_requests_only_visible_trade_feedback(self):
        request = AnalysisRequest(
            ticker="MSFT",
            analysis_date="2026-04-03",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "tradingagents.runner.get_trade_feedback_payload",
                return_value={"prompt": "", "reviews": []},
            ) as mock_feedback:
                with patch(
                    "tradingagents.runner.TradingAgentsGraph",
                    _FakeTradingAgentsGraph,
                ):
                    generator = run_analysis_streaming(request, Path(temp_dir))
                    next(generator)
                    generator.close()

        mock_feedback.assert_called_once_with(
            "MSFT",
            reports_dir=None,
            analysis_date="2026-04-03",
        )


if __name__ == "__main__":
    unittest.main()
