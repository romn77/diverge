import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from diverge.runner import (
    AnalysisRequest,
    AnalysisTracker,
    build_analysis_config,
    run_analysis_streaming,
    save_report_to_disk,
)


class _FakePropagator:
    def create_initial_state(self, *_args, **_kwargs):
        return {}

    def get_graph_args(self):
        return {}


class _FakeDivergeGraph:
    def __init__(self, *_args, **_kwargs):
        self.propagator = _FakePropagator()


class AnalysisTrackerTests(unittest.TestCase):
    def test_analysis_request_keeps_trading_session_date(self):
        request = AnalysisRequest(
            ticker="SPY",
            analysis_date="2024-03-15",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

        self.assertEqual(request.analysis_date, "2024-03-15")

    def test_analysis_request_moves_us_weekend_to_previous_close(self):
        request = AnalysisRequest(
            ticker="SPY",
            analysis_date="2024-03-17",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

        self.assertEqual(request.analysis_date, "2024-03-15")

    def test_analysis_request_moves_cn_holiday_to_previous_close(self):
        request = AnalysisRequest(
            ticker="600519.SH",
            analysis_date="2025-10-05",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            quick_think_llm="gpt-5-mini",
            deep_think_llm="gpt-5.2",
            output_language="en",
            openai_reasoning_effort="medium",
        )

        self.assertEqual(request.analysis_date, "2025-09-30")

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
                "report_summary": "BUY with disciplined sizing; fundamentals are durable, while event volatility and valuation are the key risks.",
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
            summary_path = Path(temp_dir) / "artifacts" / "summary.json"
            trade_feedback_path = Path(temp_dir) / "artifacts" / "trade_feedback.json"

            self.assertTrue(report_path.is_file())
            self.assertTrue(fundamentals_path.is_file())
            self.assertTrue(thesis_path.is_file())
            self.assertTrue(summary_path.is_file())
            self.assertTrue(trade_feedback_path.is_file())
            self.assertIn("## DCF Summary", fundamentals_path.read_text(encoding="utf-8"))

            thesis_payload = json.loads(thesis_path.read_text(encoding="utf-8"))
            self.assertEqual(thesis_payload["type"], "thesis")
            self.assertEqual(thesis_payload["ticker"], "MSFT")

            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["type"], "summary")
            self.assertEqual(summary_payload["ticker"], "MSFT")
            self.assertIn("disciplined sizing", summary_payload["summary"])

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
                "diverge.runner.get_trade_feedback_payload",
                return_value={"prompt": "", "reviews": []},
            ) as mock_feedback:
                with patch(
                    "diverge.runner.DivergeGraph",
                    _FakeDivergeGraph,
                ):
                    generator = run_analysis_streaming(request, Path(temp_dir))
                    next(generator)
                    generator.close()

        mock_feedback.assert_called_once_with(
            "MSFT",
            reports_dir=None,
            analysis_date="2026-04-02",
            visible_trade_ids=None,
        )

    def test_build_analysis_config_can_prefer_massive_for_us_market_data(self):
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
            market_data_source="massive",
        )

        config = build_analysis_config(request)

        self.assertEqual(
            config["market_overrides"]["us"]["core_stock_apis"],
            "massive",
        )
        self.assertEqual(
            config["market_overrides"]["us"]["technical_indicators"],
            "local",
        )
        self.assertEqual(
            config["market_overrides"]["us"]["fundamental_data"],
            "fmp,alpha_vantage,yfinance",
        )


if __name__ == "__main__":
    unittest.main()
