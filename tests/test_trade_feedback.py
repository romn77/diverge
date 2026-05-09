import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from diverge import trade_feedback


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
        self.report_dir = (
            self.project_root / "data" / "reports" / "MSFT_20260401_120000"
        )
        self.eval_dir = (
            self.project_root
            / "data"
            / "eval_results"
            / "MSFT"
            / "DivergeStrategy_logs"
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

    def _trade_payload(self, **overrides):
        payload = {
            "raw_symbol": "MSFT",
            "side": "long",
            "entry_timestamp": "2026-04-01T09:30:00",
            "entry_price": 420.5,
            "size": 12,
            "strategy_tags": ["pullback"],
            "entry_reason": "Cloud durability and AI demand remain underpriced.",
            "invalidation_condition": "Cloud demand commentary weakens or price closes below support.",
            "planned_horizon": "swing_1_4w",
            "stop_loss": 405.0,
            "take_profit": 450.0,
            "notes": "Entered after the report review.",
            "analysis_references": [
                {
                    "analysis_date": "2026-04-01",
                    "report_path": "data/reports/MSFT_20260401_120000/complete_report.md",
                    "full_state_log_path": "data/eval_results/MSFT/DivergeStrategy_logs/full_states_log_2026-04-01.json",
                }
            ],
        }
        payload.update(overrides)
        return payload

    def test_trade_record_review_and_feedback_prompt_round_trip(self):
        record = trade_feedback.create_trade_record(
            self._trade_payload(raw_symbol="msft"),
            reports_dir=self.reports_dir,
        )

        updated = trade_feedback.update_trade_record(
            record["trade_id"],
            {
                "exit_timestamp": "2026-04-04T15:59:00",
                "exit_price": 438.25,
                "exit_reason": "Exited into the catalyst follow-through.",
                "plan_execution": "followed_plan",
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
                    "cross_ticker_tags": [
                        "earnings_follow_through",
                        "planned_scale_in",
                    ],
                }
            )
        )
        with patch(
            "diverge.trade_feedback._now_iso",
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
        self.assertIn(
            "Reports and full-state logs are optional supplements", fake_llm.prompts[0]
        )
        self.assertIn("Evidence pack:", fake_llm.prompts[0])
        self.assertIn('"local_price_history"', fake_llm.prompts[0])
        self.assertIn('"external_news"', fake_llm.prompts[0])
        self.assertIn("Review diagnostics:", fake_llm.prompts[0])
        self.assertIn("Separate record quality from trade quality", fake_llm.prompts[0])
        self.assertIn("Determine setup_type", fake_llm.prompts[0])
        self.assertIn(
            "Do not mechanically punish a trade for missing fundamentals",
            fake_llm.prompts[0],
        )
        self.assertIn("CRITICAL OUTPUT FORMAT", fake_llm.prompts[0])
        self.assertIn("Score floors by setup_type", fake_llm.prompts[0])
        self.assertIn("Record quality: <high|medium|low>", fake_llm.prompts[0])
        self.assertIn("`thesis_assessment` = Logic assessment", fake_llm.prompts[0])
        self.assertIn("`timing_assessment` = Technical assessment", fake_llm.prompts[0])
        self.assertIn(
            "`sizing_assessment` = Risk-control assessment", fake_llm.prompts[0]
        )
        self.assertIn(
            "`discipline_assessment` = Execution assessment", fake_llm.prompts[0]
        )
        self.assertIn(
            "Assign each root cause to one primary module", fake_llm.prompts[0]
        )
        self.assertIn(
            "verify whether the buy actually satisfied the setup trigger",
            fake_llm.prompts[0],
        )
        self.assertIn(
            "fundamental/catalyst context supports or conflicts with the technical signal",
            fake_llm.prompts[0],
        )
        self.assertIn(
            "explicitly give the required risk-control rule or remediation",
            fake_llm.prompts[0],
        )
        self.assertIn("critique the operational failure", fake_llm.prompts[0])
        self.assertIn(
            "Each action must be enforceable by software or a pre-order checklist",
            fake_llm.prompts[0],
        )
        self.assertIn("Review diagnostics as the source of truth", fake_llm.prompts[0])
        self.assertIn("high-quality trading coach", fake_llm.prompts[0])
        self.assertIn(
            "Translate raw record and diagnostic keys into trader-facing language",
            fake_llm.prompts[0],
        )
        self.assertIn("Do not output internal diagnostic keys", fake_llm.prompts[0])
        self.assertIn(
            'For each score, include a short "because..." explanation',
            fake_llm.prompts[0],
        )
        self.assertIn(
            "Outcome summary after the anchor sentence should be 2-3 coaching sentences only",
            fake_llm.prompts[0],
        )
        self.assertIn("why confidence is high/medium/low", fake_llm.prompts[0])
        self.assertIn(
            'Write "R:R could not be calculated", not `risk_reward_available=false`',
            fake_llm.prompts[0],
        )
        self.assertIn(
            "Mix severity levels so the ruleset is usable", fake_llm.prompts[0]
        )
        self.assertIn(
            "Prefix each action with exactly one severity label", fake_llm.prompts[0]
        )
        self.assertIn("`BLOCKING:`", fake_llm.prompts[0])
        self.assertIn("`CONDITIONAL:`", fake_llm.prompts[0])
        self.assertIn("`FLAG:`", fake_llm.prompts[0])
        self.assertIn("all English lowercase snake_case", fake_llm.prompts[0])
        self.assertIn("Do not mix Chinese and English in tags", fake_llm.prompts[0])
        self.assertIn(
            "mention each unavailable evidence source at most once", fake_llm.prompts[0]
        )
        self.assertIn("Return 3 to 5 items only", fake_llm.prompts[0])
        self.assertIn("Verdict: <one phrase> | Score:", fake_llm.prompts[0])
        self.assertIn(
            "Use numeric thresholds when the record, setup defaults, or provided rule examples support them",
            fake_llm.prompts[0],
        )

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
        self.assertIn(
            "Historical trade feedback for ticker MSFT", feedback_payload["prompt"]
        )
        self.assertIn("planned_scale_in", feedback_payload["prompt"])

    def test_backfilled_review_visibility_uses_review_save_time(self):
        record = trade_feedback.create_trade_record(
            self._trade_payload(raw_symbol="msft"),
            reports_dir=self.reports_dir,
        )

        with patch(
            "diverge.trade_feedback._now_iso",
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

    def test_generated_review_prompt_uses_local_price_history_cache_when_available(
        self,
    ):
        history_dir = self.project_root / "data" / "history" / "us"
        history_dir.mkdir(parents=True)
        start = date(2026, 1, 1)
        rows = ["Date,Open,High,Low,Close,Volume,Amount"]
        for offset in range(75):
            day = start + timedelta(days=offset)
            close = 100 + offset
            rows.append(
                f"{day.isoformat()},{close - 1},{close + 2},{close - 3},{close},1000000,{close * 1000000}"
            )
        (history_dir / "MSFT.csv").write_text("\n".join(rows), encoding="utf-8")
        record = trade_feedback.create_trade_record(
            self._trade_payload(
                raw_symbol="msft",
                entry_timestamp="2026-03-16T09:30:00",
                entry_price=174.0,
            ),
            reports_dir=self.reports_dir,
        )
        fake_llm = _FakeLLM(
            json.dumps(
                {
                    "thesis_assessment": "The thesis was testable.",
                    "timing_assessment": "The local price cache showed momentum context.",
                    "sizing_assessment": "Sizing was reviewable.",
                    "discipline_assessment": "The entry followed the plan.",
                    "outcome_summary": "Evidence was used.",
                    "improvement_actions": ["Keep cache coverage fresh."],
                    "ticker_specific_lessons": [
                        "MSFT reviews should cite local cache context."
                    ],
                    "cross_ticker_tags": ["local_history_available"],
                }
            )
        )

        trade_feedback.generate_trade_review(
            record["trade_id"],
            review_type="entry_review",
            llm_provider="ollama",
            model="local-test",
            analysis_date="2026-03-16",
            reports_dir=self.reports_dir,
            llm=fake_llm,
        )

        prompt = fake_llm.prompts[0]
        self.assertIn('"status": "available"', prompt)
        self.assertIn('"source": "local_history_cache"', prompt)
        self.assertIn('"technical_summary"', prompt)
        self.assertIn('"rsi_14"', prompt)
        self.assertIn('"technical_decision_checks"', prompt)
        self.assertIn('"must_use_in_timing_assessment": true', prompt)
        self.assertIn('"entry_vs_previous_20d_high_pct"', prompt)
        self.assertIn("MUST cite at least three concrete OHLC-derived metrics", prompt)
        self.assertIn(
            "do NOT say there is no chart, volume, price structure, or technical context",
            prompt,
        )
        self.assertIn("For breakout trades, focus on breakout level", prompt)
        self.assertIn(
            "Low data_quality means limited review confidence, not automatic poor trade quality",
            prompt,
        )
        self.assertIn("Keep fundamental discussion to 1-2 sentences", prompt)
        self.assertIn("Do not explain general trading theory", prompt)

    def test_generated_review_prompt_includes_behavior_diagnostics(self):
        record = trade_feedback.create_trade_record(
            self._trade_payload(
                raw_symbol="msft",
                strategy_tags=["breakout"],
                entry_reason="突破周线 盘中追高",
                invalidation_condition="突破失败",
                planned_horizon="unknown",
                stop_loss=None,
                take_profit=None,
                notes="",
                analysis_references=[],
            ),
            reports_dir=self.reports_dir,
        )
        fake_llm = _FakeLLM(
            json.dumps(
                {
                    "thesis_assessment": "Record quality: Low. Process quality: Weak. Confidence: Medium-low.",
                    "timing_assessment": "Technical timing: Weak, 2/5.",
                    "sizing_assessment": "Risk/reward: Poor, 1/5.",
                    "discipline_assessment": "Discipline: Weak, 2/5.",
                    "outcome_summary": "Record quality: Low. Setup type: breakout. Process quality: weak.",
                    "improvement_actions": [
                        "Before entering a breakout trade, record breakout level and confirmation method."
                    ],
                    "ticker_specific_lessons": [
                        "MSFT breakout reviews need executable levels."
                    ],
                    "cross_ticker_tags": ["undefined_risk"],
                }
            )
        )

        trade_feedback.generate_trade_review(
            record["trade_id"],
            review_type="entry_review",
            llm_provider="ollama",
            model="local-test",
            analysis_date="2026-04-01",
            reports_dir=self.reports_dir,
            llm=fake_llm,
        )

        prompt = fake_llm.prompts[0]
        self.assertIn('"setup_type": "breakout"', prompt)
        self.assertIn('"record_quality": "low"', prompt)
        self.assertIn('"breakout_level"', prompt)
        self.assertIn('"confirmation_method"', prompt)
        self.assertIn('"risk_reward_available": false', prompt)
        self.assertIn("entry_reason suggests intraday chase", prompt)
        self.assertIn("breakout execution undefined", prompt)

    def test_manual_review_can_save_without_analysis_references(self):
        record = trade_feedback.create_trade_record(
            self._trade_payload(
                raw_symbol="msft",
                notes="Entered after a manual chart review.",
                analysis_references=[],
            ),
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
            self._trade_payload(
                raw_symbol="msft",
                notes="Entered after a manual chart review.",
                analysis_references=[],
            ),
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
                    "ticker_specific_lessons": [
                        "MSFT entries need clear cloud demand confirmation."
                    ],
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
