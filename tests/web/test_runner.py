import tempfile
import unittest
from pathlib import Path

from tradingagents.runner import AnalysisTracker


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


if __name__ == "__main__":
    unittest.main()
