import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from web.backend import app_config
from web.backend.routers import screeners as screeners_router
from web.backend.runtime import screener_tasks
from web.backend.schemas.screeners import ScreenTaskCreatePayload
from web.backend.services import config as config_service
from web.backend.services import screeners as screener_service


class ScreenerBreakoutContractTests(unittest.TestCase):
    def tearDown(self):
        screener_tasks.screener_tasks.clear()

    def test_screener_config_options_expose_breakout_choices_and_default_selection(self):
        payload = config_service.get_screener_config_options_payload()

        self.assertEqual(
            [option["value"] for option in payload["breakout_types"]],
            ["platform_breakout", "box_breakout", "wedge_breakout"],
        )
        self.assertEqual(payload["defaults"]["breakout_types"], [])

    def test_create_screener_task_preserves_breakout_type_selection(self):
        payload = {
            "markets": ["cn"],
            "as_of_date": "2026-03-24",
            "top_k": 20,
            "cn_data_source": "akshare",
            "breakout_types": ["platform_breakout", "wedge_breakout"],
        }

        with (
            patch("web.backend.access.require_screener_user", return_value=None),
            patch("web.backend.runtime.screener_tasks.start_screener_task_thread"),
        ):
            body = screeners_router.create_screener_task(
                ScreenTaskCreatePayload(**payload)
            )

        task = screener_tasks.screener_tasks[body["task_id"]]
        self.assertEqual(
            task.request_payload["breakout_types"],
            ["platform_breakout", "wedge_breakout"],
        )
        self.assertEqual(
            task.config_payload["breakout_types"],
            ["platform_breakout", "wedge_breakout"],
        )


    def test_legacy_candidate_rows_fill_missing_columns_with_safe_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_dir = Path(temp_dir)
            run_id = "20260324_214530"
            run_dir = runs_dir / run_id
            run_dir.mkdir(parents=True)
            (run_dir / "candidates.csv").write_text(
                "symbol,market,global_rank,total_score,trend_score,momentum_score,risk_score,liquidity_score\n"
                "600519.SH,cn,1,0.91,0.42,0.18,0.12,0.19\n",
                encoding="utf-8",
            )

            with (
                patch.object(app_config, "SCREENER_RESULTS_DIR", runs_dir),
                patch("web.backend.auth.get_auth_settings", return_value=SimpleNamespace(enabled=False)),
            ):
                rows = screener_service.get_screener_run_candidates(run_id)

        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["breakout_type"])
        self.assertEqual(rows[0]["strategy_tags"], "")
        self.assertEqual(rows[0]["risk_flags"], "")


if __name__ == "__main__":
    unittest.main()
