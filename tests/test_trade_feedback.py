import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tradingagents import trade_feedback


class _FakeLLM:
    def __init__(self, content: str):
        self.content = content
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return type("Response", (), {"content": self.content})()


class TradeFeedbackServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        self.reports_dir = self.project_root / "data" / "reports"
        self.report_dir = self.project_root / "data" / "reports" / "MSFT_20260401_120000"
        self.eval_dir = (
            self.project_root
            / "data"
            / "eval_results"
            / "MSFT"
            / "TradingAgentsStrategy_logs"
        )
        self.report_dir.mkdir(parents=True)
        self.eval_dir.mkdir(parents=True)

        (self.report_dir / "complete_report.md").write_text(
            "# Trading Analysis Report: MSFT\n\nGenerated: 2026-04-01 12:00:00\n\n## Summary\n\nCloud growth remains intact.\n",
            encoding="utf-8",
        )
        (self.eval_dir / "full_states_log_2026-04-01.json").write_text(
            json.dumps(
                {
                    "2026-04-01": {
                        "trade_date": "2026-04-01",
                        "market_report": "Market setup is constructive.",
                        "sentiment_report": "Sentiment is supportive.",
                        "news_report": "News flow is stable.",
                        "fundamentals_report": "Fundamentals remain healthy.",
                        "investment_plan": "Buy on orderly pullbacks.",
                        "trader_investment_decision": "Scale in over two tranches.",
                        "final_trade_decision": "BUY",
                    }
                }
            ),
            encoding="utf-8",
        )

        self.project_patch = patch.object(
            trade_feedback,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.project_patch.start()

    def tearDown(self):
        self.project_patch.stop()
        self.temp_dir.cleanup()

    def test_trade_record_review_and_feedback_prompt_round_trip(self):
        record = trade_feedback.create_trade_record(
            {
                "ticker": "msft",
                "exchange_or_market": "NASDAQ",
                "side": "long",
                "status": "open",
                "entry_timestamp": "2026-04-01T09:30:00",
                "entry_price": 420.5,
                "size": 12,
                "initial_thesis": "Cloud durability and AI demand remain underpriced.",
                "planned_horizon": "swing_2w",
                "stop_loss": 405.0,
                "take_profit": 450.0,
                "notes": "Entered after the report review.",
                "analysis_references": [
                    {
                        "analysis_date": "2026-04-01",
                        "report_path": "data/reports/MSFT_20260401_120000/complete_report.md",
                        "full_state_log_path": "data/eval_results/MSFT/TradingAgentsStrategy_logs/full_states_log_2026-04-01.json",
                    }
                ],
            },
            reports_dir=self.reports_dir,
        )

        updated = trade_feedback.update_trade_record(
            record["trade_id"],
            {
                "status": "closed",
                "exit_timestamp": "2026-04-04T15:59:00",
                "exit_price": 438.25,
                "notes": "Exited into the catalyst follow-through.",
            },
            reports_dir=self.reports_dir,
        )

        self.assertEqual(updated["trade_id"], record["trade_id"])
        self.assertEqual(updated["ticker"], "MSFT")
        self.assertEqual(updated["status"], "closed")

        fake_llm = _FakeLLM(
            json.dumps(
                {
                    "thesis_assessment": "The entry thesis stayed grounded in durable cloud demand and did not overfit a single catalyst.",
                    "timing_assessment": "Timing was acceptable because the entry waited for a documented setup instead of chasing the first move.",
                    "sizing_assessment": "Sizing was disciplined relative to the stated stop distance.",
                    "discipline_assessment": "Execution respected the plan and the exit remained aligned with the catalyst path.",
                    "outcome_summary": "The trade worked, but the review still credits process quality more than the realized gain.",
                    "improvement_actions": [
                        "Write the invalidation condition in one sentence before entry."
                    ],
                    "ticker_specific_lessons": [
                        "MSFT follow-through trades work better when cloud commentary confirms the thesis."
                    ],
                    "cross_ticker_tags": ["earnings_follow_through", "planned_scale_in"],
                }
            )
        )
        with patch(
            "tradingagents.trade_feedback._now_iso",
            return_value="2026-04-04T16:00:00",
        ):
            review = trade_feedback.generate_trade_review(
                record["trade_id"],
                review_type="exit_review",
                llm_provider="ollama",
                model="local-test",
                analysis_date="2026-04-04",
                reports_dir=self.reports_dir,
                llm=fake_llm,
            )

        self.assertEqual(review["review_type"], "exit_review")
        self.assertEqual(review["analysis_date"], "2026-04-04")
        self.assertIn("Avoid obvious hindsight bias", fake_llm.prompts[0])
        self.assertIn("This is an EXIT review.", fake_llm.prompts[0])
        self.assertIn("Reports and full-state logs are optional supplements", fake_llm.prompts[0])

        earlier_feedback = trade_feedback.get_trade_feedback_payload(
            "MSFT",
            reports_dir=self.reports_dir,
            analysis_date="2026-04-03",
        )
        self.assertEqual(earlier_feedback["reviews"], [])

        feedback_payload = trade_feedback.get_trade_feedback_payload(
            "MSFT",
            reports_dir=self.reports_dir,
            analysis_date="2026-04-04",
        )
        self.assertEqual(len(feedback_payload["reviews"]), 1)
        self.assertIn("Historical trade feedback for ticker MSFT", feedback_payload["prompt"])
        self.assertIn("planned_scale_in", feedback_payload["prompt"])

    def test_backfilled_review_visibility_uses_review_save_time(self):
        record = trade_feedback.create_trade_record(
            {
                "ticker": "msft",
                "exchange_or_market": "NASDAQ",
                "side": "long",
                "status": "open",
                "entry_timestamp": "2026-04-01T09:30:00",
                "entry_price": 420.5,
                "size": 12,
                "initial_thesis": "Cloud durability and AI demand remain underpriced.",
                "planned_horizon": "swing_2w",
                "stop_loss": 405.0,
                "take_profit": 450.0,
                "notes": "Entered after the report review.",
                "analysis_references": [
                    {
                        "analysis_date": "2026-04-01",
                        "report_path": "data/reports/MSFT_20260401_120000/complete_report.md",
                        "full_state_log_path": "data/eval_results/MSFT/TradingAgentsStrategy_logs/full_states_log_2026-04-01.json",
                    }
                ],
            },
            reports_dir=self.reports_dir,
        )

        with patch(
            "tradingagents.trade_feedback._now_iso",
            return_value="2026-04-13T09:15:00",
        ):
            review = trade_feedback.save_trade_review(
                record["trade_id"],
                review_type="entry_review",
                payload={
                    "thesis_assessment": "The thesis stayed explicit and testable.",
                    "timing_assessment": "The entry followed the planned setup window.",
                    "sizing_assessment": "Sizing respected the stop distance.",
                    "discipline_assessment": "Execution matched the written plan.",
                    "outcome_summary": "The review remains process-focused.",
                    "improvement_actions": [
                        "Write the invalidation clause before sending the order."
                    ],
                    "ticker_specific_lessons": [
                        "MSFT entries improve when cloud commentary confirms the thesis."
                    ],
                    "cross_ticker_tags": ["planned_stop"],
                },
                analysis_date="2026-04-01",
                reports_dir=self.reports_dir,
            )

        self.assertEqual(review["analysis_date"], "2026-04-01")

        hidden_feedback = trade_feedback.get_trade_feedback_payload(
            "MSFT",
            reports_dir=self.reports_dir,
            analysis_date="2026-04-02",
        )
        visible_feedback = trade_feedback.get_trade_feedback_payload(
            "MSFT",
            reports_dir=self.reports_dir,
            analysis_date="2026-04-13",
        )

        self.assertEqual(hidden_feedback["reviews"], [])
        self.assertEqual(len(visible_feedback["reviews"]), 1)

    def test_manual_review_can_save_without_analysis_references(self):
        record = trade_feedback.create_trade_record(
            {
                "ticker": "msft",
                "exchange_or_market": "NASDAQ",
                "side": "long",
                "status": "open",
                "entry_timestamp": "2026-04-01T09:30:00",
                "entry_price": 420.5,
                "size": 12,
                "initial_thesis": "Cloud durability and AI demand remain underpriced.",
                "planned_horizon": "swing_2w",
                "stop_loss": 405.0,
                "take_profit": 450.0,
                "notes": "Entered after a manual chart review.",
                "analysis_references": [],
            },
            reports_dir=self.reports_dir,
        )

        review = trade_feedback.save_trade_review(
            record["trade_id"],
            review_type="entry_review",
            payload={
                "thesis_assessment": "Inherited from the saved trade record.",
                "timing_assessment": "Manual entry review saved without linked snapshots.",
                "sizing_assessment": "Sizing was not separately reviewed.",
                "discipline_assessment": "Discipline was not separately reviewed.",
                "outcome_summary": "Manual review remains available for future context.",
                "improvement_actions": [],
                "ticker_specific_lessons": [],
                "cross_ticker_tags": [],
            },
            analysis_date="2026-04-01",
            reports_dir=self.reports_dir,
        )

        self.assertEqual(review["analysis_references"], [])
        self.assertEqual(review["analysis_date"], "2026-04-01")

    def test_ai_review_can_generate_without_analysis_references(self):
        record = trade_feedback.create_trade_record(
            {
                "ticker": "msft",
                "exchange_or_market": "NASDAQ",
                "side": "long",
                "status": "open",
                "entry_timestamp": "2026-04-01T09:30:00",
                "entry_price": 420.5,
                "size": 12,
                "initial_thesis": "Cloud durability and AI demand remain underpriced.",
                "planned_horizon": "swing_2w",
                "stop_loss": 405.0,
                "take_profit": 450.0,
                "notes": "Entered after a manual chart review.",
                "analysis_references": [],
            },
            reports_dir=self.reports_dir,
        )
        fake_llm = _FakeLLM(
            json.dumps(
                {
                    "thesis_assessment": "Overall entry verdict: Mixed. Fundamental thesis score: 3/5.",
                    "timing_assessment": "Technical timing score: 3/5. Entry was reasonable but needed confirmation.",
                    "sizing_assessment": "Risk/reward score: 3/5. Sizing score: 3/5.",
                    "discipline_assessment": "Discipline score: 4/5. The decision followed the written plan.",
                    "outcome_summary": "Strengths: clear thesis. Weaknesses: limited confirmation. Hindsight calibration: unavailable.",
                    "improvement_actions": ["Wait for confirmation before entry."],
                    "ticker_specific_lessons": ["MSFT entries need clear cloud demand confirmation."],
                    "cross_ticker_tags": ["confirmation_needed"],
                }
            )
        )

        review = trade_feedback.generate_trade_review(
            record["trade_id"],
            review_type="entry_review",
            llm_provider="ollama",
            model="local-test",
            analysis_date="2026-04-01",
            reports_dir=self.reports_dir,
            llm=fake_llm,
        )

        self.assertEqual(review["analysis_references"], [])
        self.assertIn("This is an ENTRY review.", fake_llm.prompts[0])
        self.assertIn("No analysis snapshots are attached", fake_llm.prompts[0])


if __name__ == "__main__":
    unittest.main()
