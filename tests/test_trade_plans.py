import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from diverge import trade_feedback, trade_plans


class TradePlanServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        self.reports_dir = self.project_root / "data" / "reports"
        self.reports_dir.mkdir(parents=True)
        self.project_patch = patch.object(
            trade_feedback,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.project_patch.start()

    def tearDown(self):
        self.project_patch.stop()
        self.temp_dir.cleanup()

    def _plan_payload(self, **overrides):
        payload = {
            "raw_symbol": "MSFT",
            "side": "long",
            "strategy_tags": ["pullback"],
            "entry_condition": "Buy only after a controlled pullback near support.",
            "thesis": "Cloud demand remains durable and the pullback improves R:R.",
            "invalidation_condition": "Cloud demand weakens or support fails.",
            "risk_rule": "Stop on a daily close below support.",
            "reward_target": "Trim near prior high and exit remainder around 2R.",
            "position_plan": "Start at 3% portfolio risk capped at 0.5% account loss.",
            "planned_horizon": "swing_1_4w",
            "stop_loss": 408.0,
            "take_profit": None,
            "expires_at": "2026-04-02T16:00:00+00:00",
            "notes": "Manual plan.",
            "analysis_references": [],
        }
        payload.update(overrides)
        return payload

    def test_plan_create_list_expire_and_delete_round_trip(self):
        with patch("diverge.trade_plans._now_iso", return_value="2026-04-01T09:00:00+00:00"):
            plan = trade_plans.create_trade_plan(
                self._plan_payload(raw_symbol="msft"),
                reports_dir=self.reports_dir,
            )

        self.assertEqual(plan["ticker"], "MSFT")
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["reward_target"], "Trim near prior high and exit remainder around 2R.")
        self.assertIsNone(plan["take_profit"])

        with patch("diverge.trade_plans._now_iso", return_value="2026-04-03T09:00:00+00:00"):
            expired = trade_plans.get_trade_plan(
                plan["plan_id"], reports_dir=self.reports_dir
            )

        self.assertEqual(expired["status"], "expired")
        self.assertEqual(
            expired["status_reason"],
            trade_plans.STATUS_REASON_NOT_EXECUTED_BEFORE_EXPIRY,
        )
        self.assertEqual(
            trade_plans.list_trade_plans(
                status="planned", reports_dir=self.reports_dir
            ),
            [],
        )

        trade_plans.delete_trade_plan(plan["plan_id"], reports_dir=self.reports_dir)
        with self.assertRaises(ValueError):
            trade_plans.get_trade_plan(plan["plan_id"], reports_dir=self.reports_dir)

    def test_executed_plan_locks_baseline_and_snapshot(self):
        with patch("diverge.trade_plans._now_iso", return_value="2026-04-01T09:00:00+00:00"):
            plan = trade_plans.create_trade_plan(
                self._plan_payload(),
                reports_dir=self.reports_dir,
            )

        record_payload = trade_plans.build_execution_trade_payload(
            plan,
            {
                "entry_timestamp": "2026-04-02T15:30:00+00:00",
                "entry_price": 420.0,
                "size": 10,
                "execution_note": "Executed at a smaller size than planned.",
            },
        )
        record = trade_feedback.create_trade_record(
            record_payload,
            reports_dir=self.reports_dir,
        )
        trade_plans.validate_plan_link(plan, record)
        executed = trade_plans.mark_trade_plan_executed(
            plan["plan_id"], record["trade_id"], reports_dir=self.reports_dir
        )

        self.assertEqual(executed["status"], "executed")
        self.assertEqual(executed["linked_trade_id"], record["trade_id"])
        self.assertEqual(record["originating_plan_id"], plan["plan_id"])
        self.assertEqual(
            record["originating_plan_snapshot"]["entry_condition"],
            plan["entry_condition"],
        )
        self.assertEqual(
            record["execution_note"],
            "Executed at a smaller size than planned.",
        )

        with self.assertRaises(ValueError):
            trade_plans.update_trade_plan(
                plan["plan_id"],
                {"entry_condition": "Rewrite the baseline."},
                reports_dir=self.reports_dir,
            )
        updated = trade_plans.update_trade_plan(
            plan["plan_id"],
            {"notes": "Corrected a typo in the note."},
            reports_dir=self.reports_dir,
        )
        self.assertEqual(updated["notes"], "Corrected a typo in the note.")

        with self.assertRaises(ValueError):
            trade_plans.delete_trade_plan(plan["plan_id"], reports_dir=self.reports_dir)

    def test_plan_link_rejects_mismatched_side_and_late_entry(self):
        plan = trade_plans.create_trade_plan(
            self._plan_payload(expires_at="2026-04-02T16:00:00+00:00"),
            reports_dir=self.reports_dir,
        )

        short_record = trade_feedback.create_trade_record(
            {
                **trade_plans.build_execution_trade_payload(
                    plan,
                    {
                        "entry_timestamp": "2026-04-02T15:30:00+00:00",
                        "entry_price": 420.0,
                        "size": 10,
                    },
                ),
                "originating_plan_id": "",
                "originating_plan_snapshot": None,
                "side": "short",
            },
            reports_dir=self.reports_dir,
        )
        with self.assertRaises(ValueError):
            trade_plans.validate_plan_link(plan, short_record)

        late_record = trade_feedback.create_trade_record(
            {
                **trade_plans.build_execution_trade_payload(
                    plan,
                    {
                        "entry_timestamp": "2026-04-03T15:30:00+00:00",
                        "entry_price": 420.0,
                        "size": 10,
                    },
                ),
                "originating_plan_id": "",
                "originating_plan_snapshot": None,
            },
            reports_dir=self.reports_dir,
        )
        with self.assertRaises(ValueError):
            trade_plans.validate_plan_link(plan, late_record)


if __name__ == "__main__":
    unittest.main()
