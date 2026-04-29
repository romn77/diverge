import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from diverge import trade_feedback
from web.backend import app_config, auth
from web.backend.schemas.trades import (
    AnalysisReferencePayload,
    TradeRecordCreatePayload,
    TradeRecordUpdatePayload,
    TradeReviewCreatePayload,
    TradeReviewSavePayload,
)
from web.backend.services.trades import (
    create_trade,
    create_trade_review,
    get_ticker_trade_feedback,
    get_trade,
    save_trade_review,
    update_trade,
)


class _FakeClient:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def get_llm(self):
        response_text = self.response_text

        class _FakeLLM:
            def invoke(self, _prompt):
                return type("Response", (), {"content": response_text})()

        return _FakeLLM()


class TradeFeedbackBackendTests(unittest.TestCase):
    def setUp(self):
        self.auth_env_patch = patch.dict(
            os.environ,
            {"AUTH_ENABLED": "false", "AUTH_MODE": "disabled"},
            clear=False,
        )
        self.auth_env_patch.start()
        auth.reset_runtime_state()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "project"
        self.project_root.mkdir(parents=True)
        self.original_reports_dir = app_config.REPORTS_DIR
        self.original_tmp_reports_dir = app_config.TMP_REPORTS_DIR
        app_config.REPORTS_DIR = self.project_root / "data" / "reports"
        app_config.TMP_REPORTS_DIR = app_config.REPORTS_DIR / ".tmp"

        self.project_patch = patch.object(trade_feedback, "PROJECT_ROOT", self.project_root)
        self.project_patch.start()

        report_dir = app_config.REPORTS_DIR / "MSFT_20260401_120000"
        eval_dir = (
            self.project_root
            / "data"
            / "eval_results"
            / "MSFT"
            / "DivergeStrategy_logs"
        )
        report_dir.mkdir(parents=True)
        eval_dir.mkdir(parents=True)

        (report_dir / "complete_report.md").write_text(
            "# Trading Analysis Report: MSFT\n\nGenerated: 2026-04-01 12:00:00\n\n",
            encoding="utf-8",
        )
        (eval_dir / "full_states_log_2026-04-01.json").write_text(
            json.dumps(
                {
                    "2026-04-01": {
                        "trade_date": "2026-04-01",
                        "market_report": "Constructive market setup.",
                        "sentiment_report": "Sentiment stayed supportive.",
                        "news_report": "Catalysts remained intact.",
                        "fundamentals_report": "Fundamentals remained durable.",
                        "investment_plan": "Buy the pullback.",
                        "trader_investment_decision": "Scale in.",
                        "final_trade_decision": "BUY",
                    }
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        app_config.REPORTS_DIR = self.original_reports_dir
        app_config.TMP_REPORTS_DIR = self.original_tmp_reports_dir
        self.project_patch.stop()
        auth.reset_runtime_state()
        self.auth_env_patch.stop()
        self.temp_dir.cleanup()

    def test_trade_routes_create_update_and_generate_review(self):
        record = create_trade(
            TradeRecordCreatePayload(
                ticker="MSFT",
                exchange_or_market="NASDAQ",
                side="long",
                status="open",
                entry_timestamp="2026-04-01T09:30:00",
                entry_price=420.0,
                size=10,
                initial_thesis="Cloud momentum remains durable.",
                planned_horizon="swing_2w",
                stop_loss=408.0,
                take_profit=448.0,
                notes="Manual entry.",
                analysis_references=[
                    AnalysisReferencePayload(
                        analysis_date="2026-04-01",
                        report_path="data/reports/MSFT_20260401_120000/complete_report.md",
                        full_state_log_path="data/eval_results/MSFT/DivergeStrategy_logs/full_states_log_2026-04-01.json",
                    )
                ],
            )
        )

        trade_id = record["trade_id"]
        updated = update_trade(
            trade_id,
            TradeRecordUpdatePayload(
                status="closed",
                exit_timestamp="2026-04-03T15:55:00",
                exit_price=436.5,
            ),
        )
        self.assertEqual(updated["trade_id"], trade_id)
        self.assertEqual(updated["status"], "closed")

        review_payload = json.dumps(
            {
                "thesis_assessment": "The thesis stayed tied to durable cloud demand instead of a vague momentum story.",
                "timing_assessment": "Timing was disciplined because entry followed an existing setup review.",
                "sizing_assessment": "Sizing matched the planned stop and did not overreach.",
                "discipline_assessment": "Execution remained aligned with the stated plan.",
                "outcome_summary": "The trade worked, but the review still attributes success primarily to process quality.",
                "improvement_actions": ["Write the invalidation clause before entry."],
                "ticker_specific_lessons": ["MSFT setups improve when cloud commentary confirms demand durability."],
                "cross_ticker_tags": ["planned_stop", "catalyst_follow_through"],
            }
        )
        with patch(
            "diverge.trade_feedback.create_llm_client",
            return_value=_FakeClient(review_payload),
        ), patch(
            "diverge.trade_feedback._now_iso",
            return_value="2026-04-03T16:00:00",
        ):
            review = create_trade_review(
                trade_id,
                TradeReviewCreatePayload(
                    review_type="exit_review",
                    llm_provider="ollama",
                    model="local-test",
                    analysis_date="2026-04-03",
                ),
            )

        self.assertEqual(review["trade_id"], trade_id)
        self.assertEqual(review["review_type"], "exit_review")
        self.assertEqual(review["analysis_date"], "2026-04-03")

        trade_payload = get_trade(trade_id)
        self.assertEqual(trade_payload["record"]["trade_id"], trade_id)
        self.assertEqual(len(trade_payload["reviews"]), 1)

        earlier_feedback = get_ticker_trade_feedback(
            "MSFT",
            analysis_date="2026-04-02",
        )
        self.assertEqual(earlier_feedback["reviews"], [])

        feedback_payload = get_ticker_trade_feedback("MSFT")
        self.assertEqual(feedback_payload["ticker"], "MSFT")
        self.assertIn("Historical trade feedback for ticker MSFT", feedback_payload["prompt"])

    def test_create_trade_rejects_path_ticker_before_writing(self):
        with self.assertRaises(HTTPException) as context:
            create_trade(
                TradeRecordCreatePayload(
                    ticker="../../ESCAPE",
                    exchange_or_market="NASDAQ",
                    side="long",
                    status="open",
                    entry_timestamp="2026-04-01T09:30:00",
                    entry_price=420.0,
                    size=10,
                    initial_thesis="Path ticker should not be accepted.",
                    planned_horizon="swing_2w",
                    stop_loss=408.0,
                    take_profit=448.0,
                    notes="Manual entry.",
                    analysis_references=[],
                )
            )

        self.assertEqual(getattr(context.exception, "status_code", None), 400)
        self.assertIn("path", str(context.exception.detail).lower())
        self.assertFalse((app_config.REPORTS_DIR.parent / "ESCAPE").exists())

    def test_trade_dir_rejects_paths_outside_feedback_root(self):
        with self.assertRaises(ValueError):
            trade_feedback._trade_dir("MSFT", "../../ESCAPE", reports_dir=app_config.REPORTS_DIR)

    def test_manual_review_save_accepts_list_fields(self):
        record = create_trade(
            TradeRecordCreatePayload(
                ticker="MSFT",
                exchange_or_market="NASDAQ",
                side="long",
                status="open",
                entry_timestamp="2026-04-01T09:30:00",
                entry_price=420.0,
                size=10,
                initial_thesis="Cloud momentum remains durable.",
                planned_horizon="swing_2w",
                stop_loss=408.0,
                take_profit=448.0,
                notes="Manual entry.",
                analysis_references=[
                    AnalysisReferencePayload(
                        analysis_date="2026-04-01",
                        report_path="data/reports/MSFT_20260401_120000/complete_report.md",
                        full_state_log_path="data/eval_results/MSFT/DivergeStrategy_logs/full_states_log_2026-04-01.json",
                    )
                ],
            )
        )

        with patch(
            "diverge.trade_feedback._now_iso",
            return_value="2026-04-13T09:15:00",
        ):
            review = save_trade_review(
                record["trade_id"],
                "entry_review",
                TradeReviewSavePayload(
                    thesis_assessment="The thesis was explicit and tied to cloud demand durability.",
                    timing_assessment="The entry waited for the planned pullback instead of chasing.",
                    sizing_assessment="Size respected the planned stop distance.",
                    discipline_assessment="Execution matched the written plan.",
                    outcome_summary="The review stays process-focused even before the trade resolves.",
                    improvement_actions=[
                        "Write the invalidation clause before sending the order.",
                        "Confirm the catalyst path before adding.",
                    ],
                    ticker_specific_lessons=[
                        "MSFT entries improve when cloud commentary confirms demand durability."
                    ],
                    cross_ticker_tags=["planned_stop", "quality_growth"],
                    analysis_date="2026-04-02",
                ),
            )

        self.assertEqual(
            review["improvement_actions"],
            [
                "Write the invalidation clause before sending the order.",
                "Confirm the catalyst path before adding.",
            ],
        )
        self.assertEqual(
            review["ticker_specific_lessons"],
            ["MSFT entries improve when cloud commentary confirms demand durability."],
        )

        earlier_feedback = get_ticker_trade_feedback(
            "MSFT",
            analysis_date="2026-04-02",
        )
        visible_feedback = get_ticker_trade_feedback(
            "MSFT",
            analysis_date="2026-04-13",
        )
        self.assertEqual(earlier_feedback["reviews"], [])
        self.assertEqual(len(visible_feedback["reviews"]), 1)


if __name__ == "__main__":
    unittest.main()
