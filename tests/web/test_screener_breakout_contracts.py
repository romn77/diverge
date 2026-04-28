import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import json

from web.backend import app_config, screener_results
from web.backend.routers import screeners as screeners_router
from web.backend.runtime import screener_tasks
from web.backend.schemas.screeners import ScreenTaskCreatePayload
from web.backend.services import config as config_service
from web.backend.services import screeners as screener_service


class ScreenerBreakoutContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_state_dir = app_config.SCREENER_STATE_DIR
        self.original_results_dir = app_config.SCREENER_RESULTS_DIR
        app_config.SCREENER_STATE_DIR = Path(self.temp_dir.name) / "state"
        app_config.SCREENER_RESULTS_DIR = Path(self.temp_dir.name) / "runs"

    def tearDown(self):
        app_config.SCREENER_STATE_DIR = self.original_state_dir
        app_config.SCREENER_RESULTS_DIR = self.original_results_dir
        screener_tasks.screener_tasks.clear()
        self.temp_dir.cleanup()

    def test_screener_config_options_expose_breakout_choices_and_default_selection(self):
        payload = config_service.get_screener_config_options_payload()

        self.assertEqual(
            [option["value"] for option in payload["breakout_types"]],
            ["platform_breakout", "box_breakout", "wedge_breakout"],
        )
        self.assertEqual(payload["defaults"]["breakout_types"], [])
        self.assertEqual(payload["defaults"]["top_k"], 100)

    def test_create_screener_task_preserves_breakout_type_selection(self):
        payload = {
            "markets": ["cn"],
            "top_k": 20,
            "cn_data_source": "akshare",
            "breakout_types": ["platform_breakout", "wedge_breakout"],
        }

        with (
            patch("web.backend.access.require_screener_user", return_value=None),
            patch("web.backend.runtime.screener_tasks.start_screener_task_thread"),
            patch("web.backend.routers.screeners.date") as date_module,
        ):
            date_module.today.return_value = __import__("datetime").date(2026, 3, 24)
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
        self.assertEqual(task.request_payload["as_of_date"], "2026-03-24")

    def test_create_screener_task_reuses_shared_cached_result_for_same_screen(self):
        payload = {
            "markets": ["cn"],
            "top_k": 20,
            "cn_data_source": "akshare",
            "breakout_types": ["platform_breakout"],
        }

        with (
            patch("web.backend.access.require_screener_user", return_value=None),
            patch("web.backend.runtime.screener_tasks.start_screener_task_thread") as start_thread,
            patch("web.backend.routers.screeners.date") as date_module,
        ):
            date_module.today.return_value = __import__("datetime").date(2026, 3, 24)
            first = screeners_router.create_screener_task(ScreenTaskCreatePayload(**payload))
            first_task = screener_tasks.screener_tasks[first["task_id"]]
            key = first_task.request_payload["screener_key"]
            cached_state = screener_results.ScreenerResultState(
                screener_key=key,
                owner_user_id=None,
                current_result=screener_results.ScreenerResultSnapshot(
                    slot=screener_results.CURRENT_SNAPSHOT_SLOT,
                    source_run_id="cached-run-001",
                    generated_at="20260324_214530",
                    updated_at="2026-03-24T21:45:30Z",
                    as_of_date="2026-03-24",
                    markets=["cn"],
                    candidate_count=1,
                    rows=[
                        {
                            "symbol": "600519.SH",
                            "market": "cn",
                            "global_rank": 1,
                            "total_score": 0.91,
                        }
                    ],
                ),
            )
            screener_results.save_screener_result_state(cached_state)

            second = screeners_router.create_screener_task(ScreenTaskCreatePayload(**payload))

        self.assertEqual(second["status"], "completed")
        self.assertEqual(second["run_id"], "cached-run-001")
        self.assertTrue(second["cached"])
        self.assertEqual(start_thread.call_count, 1)
        second_task = screener_tasks.screener_tasks[second["task_id"]]
        self.assertEqual(second_task.status, "completed")
        self.assertEqual(second_task.run_id, "cached-run-001")


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
            (run_dir / "run_meta.json").write_text(
                json.dumps(
                    {
                        "run_timestamp": run_id,
                        "as_of_date": "2026-03-24",
                        "config": {"markets": ["cn"]},
                        "candidate_count": 1,
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(app_config, "SCREENER_RESULTS_DIR", runs_dir),
                patch.object(app_config, "SCREENER_STATE_DIR", Path(temp_dir) / "state"),
                patch("web.backend.auth.get_auth_settings", return_value=SimpleNamespace(enabled=False)),
            ):
                screener_results.migrate_legacy_screener_results(force=True)
                rows = screener_service.get_screener_run_candidates(run_id)

        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["breakout_type"])
        self.assertEqual(rows[0]["strategy_tags"], "")
        self.assertEqual(rows[0]["risk_flags"], "")


if __name__ == "__main__":
    unittest.main()
