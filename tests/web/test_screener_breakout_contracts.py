import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException

from diverge.market_data.history_cache import save_history_cache
from diverge.screener.schema import ScreenRunConfig
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

    def _write_cn_manifest(self) -> Path:
        manifest_path = Path(self.temp_dir.name) / "cn_manifest.csv"
        manifest_path.write_text(
            "symbol,name,exchange,sector,list_date,mktcap\n"
            "600519.SH,Kweichow Moutai,SSE,Consumer,2001-08-27,100000000\n",
            encoding="utf-8",
        )
        return manifest_path

    def _save_single_cn_history_bar(self, history_date: str) -> Path:
        history_dir = Path(self.temp_dir.name) / "history"
        save_history_cache(
            history_dir,
            "cn",
            "600519.SH",
            pd.DataFrame(
                [
                    {
                        "Date": history_date,
                        "Open": 1,
                        "High": 1,
                        "Low": 1,
                        "Close": 1,
                        "Volume": 1,
                        "Amount": 1,
                    }
                ]
            ),
        )
        return history_dir

    def _write_cn_manifest_with_symbols(self, symbols: list[str]) -> Path:
        manifest_path = Path(self.temp_dir.name) / "cn_manifest.csv"
        rows = ["symbol,name,exchange,sector,list_date,mktcap"]
        for symbol in symbols:
            exchange = "SSE" if symbol.endswith(".SH") else "SZSE"
            rows.append(
                f"{symbol},Name {symbol},{exchange},Consumer,20200101,100000000"
            )
        manifest_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return manifest_path

    def _save_cn_history_bars(self, symbol_dates: dict[str, str]) -> Path:
        history_dir = Path(self.temp_dir.name) / "history"
        for symbol, history_date in symbol_dates.items():
            save_history_cache(
                history_dir,
                "cn",
                symbol,
                pd.DataFrame(
                    [
                        {
                            "Date": history_date,
                            "Open": 1,
                            "High": 1,
                            "Low": 1,
                            "Close": 1,
                            "Volume": 1,
                            "Amount": 1,
                        }
                    ]
                ),
            )
        return history_dir

    def _cn_cache_only_config(
        self, *, manifest_path: Path, history_dir: Path
    ) -> ScreenRunConfig:
        return ScreenRunConfig(
            markets=["cn"],
            as_of_date="2026-03-24",
            top_k=20,
            cache_dir=str(Path(self.temp_dir.name) / "cache"),
            history_dir=str(history_dir),
            output_dir=str(Path(self.temp_dir.name) / "runs"),
            history_cache_policy="cache_only",
            cn_manifest_path=str(manifest_path),
        )

    def test_screener_config_options_expose_breakout_choices_and_default_selection(
        self,
    ):
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
            patch(
                "web.backend.services.screeners.ensure_screener_cache_coverage",
                create=True,
            ),
            patch("web.backend.runtime.screener_tasks.start_screener_task_thread"),
            patch(
                "web.backend.runtime.data_sync_tasks.resolve_latest_ready_trading_day",
                return_value=date(2026, 3, 24),
            ),
            patch("web.backend.routers.screeners.date") as date_module,
        ):
            date_module.today.return_value = date(2026, 3, 24)
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

    def test_create_screener_task_defaults_to_previous_cn_trading_day_before_vendor_cutoff(
        self,
    ):
        payload = {
            "markets": ["cn"],
            "top_k": 20,
        }

        with (
            patch("web.backend.access.require_screener_user", return_value=None),
            patch(
                "web.backend.routers.screeners.resolve_screener_data_sources",
                return_value={
                    "cn_data_source": "tushare",
                    "cn_data_source_fallbacks": [],
                },
            ),
            patch(
                "web.backend.runtime.data_sync_tasks._now_for_vendor_timezone",
                return_value=datetime(2026, 4, 29, 15, 57),
            ),
            patch(
                "web.backend.services.screeners.ensure_screener_cache_coverage",
                create=True,
            ),
            patch("web.backend.runtime.screener_tasks.start_screener_task_thread"),
            patch("web.backend.routers.screeners.date") as date_module,
        ):
            date_module.today.return_value = date(2026, 4, 29)
            body = screeners_router.create_screener_task(
                ScreenTaskCreatePayload(**payload)
            )

        task = screener_tasks.screener_tasks[body["task_id"]]
        self.assertEqual(task.request_payload["as_of_date"], "2026-04-28")
        self.assertEqual(task.config_payload["as_of_date"], "2026-04-28")

    def test_create_screener_task_forces_cache_only_history_policy(self):
        payload = {
            "markets": ["cn"],
            "as_of_date": "2026-03-24",
            "top_k": 20,
            "history_cache_policy": "refresh_missing",
        }

        with (
            patch("web.backend.access.require_screener_user", return_value=None),
            patch(
                "web.backend.services.screeners.ensure_screener_cache_coverage",
                create=True,
            ),
            patch("web.backend.runtime.screener_tasks.start_screener_task_thread"),
        ):
            body = screeners_router.create_screener_task(
                ScreenTaskCreatePayload(**payload)
            )

        task = screener_tasks.screener_tasks[body["task_id"]]
        self.assertEqual(task.request_payload["history_cache_policy"], "cache_only")
        self.assertEqual(task.config_payload["history_cache_policy"], "cache_only")

    def test_create_screener_task_records_cache_coverage_failure_in_task(self):
        payload = {
            "markets": ["cn"],
            "as_of_date": "2026-03-24",
            "top_k": 20,
        }
        detail = {
            "code": "screener_data_not_ready",
            "message": "Screener data is not ready for 2026-03-24.",
            "as_of_date": "2026-03-24",
            "symbols_checked": 1,
            "symbols_missing": 1,
            "missing_markets": ["cn"],
            "examples": [
                {
                    "market": "cn",
                    "symbol": "600519.SH",
                    "reason": "history_cache_miss",
                    "cache_span": None,
                }
            ],
        }

        with (
            patch("web.backend.access.require_screener_user", return_value=None),
            patch(
                "web.backend.services.screeners.ensure_screener_cache_coverage",
                side_effect=HTTPException(status_code=409, detail=detail),
                create=True,
            ) as ensure_cache,
            patch(
                "web.backend.runtime.screener_tasks.start_screener_task_thread"
            ) as start_thread,
        ):
            body = screeners_router.create_screener_task(
                ScreenTaskCreatePayload(**payload)
            )
            screener_tasks.run_screener_task(body["task_id"])

        self.assertEqual(body["status"], "pending")
        start_thread.assert_called_once()
        ensure_cache.assert_called_once()
        task = screener_tasks.get_screener_task(body["task_id"])
        self.assertEqual(task.status, "failed")
        self.assertEqual(task.error, "Screener data is not ready for 2026-03-24.")
        self.assertIn("Screener data is not ready", task.latest_progress["message"])

    def test_create_screener_task_reuses_shared_cached_result_for_same_screen(self):
        payload = {
            "markets": ["cn"],
            "top_k": 20,
            "cn_data_source": "akshare",
            "breakout_types": ["platform_breakout"],
        }

        with (
            patch("web.backend.access.require_screener_user", return_value=None),
            patch(
                "web.backend.services.screeners.ensure_screener_cache_coverage",
                create=True,
            ),
            patch(
                "web.backend.runtime.screener_tasks.start_screener_task_thread"
            ) as start_thread,
            patch("web.backend.routers.screeners.date") as date_module,
        ):
            date_module.today.return_value = date(2026, 3, 24)
            first = screeners_router.create_screener_task(
                ScreenTaskCreatePayload(**payload)
            )
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

            second = screeners_router.create_screener_task(
                ScreenTaskCreatePayload(**payload)
            )

        self.assertEqual(second["status"], "completed")
        self.assertEqual(second["run_id"], "cached-run-001")
        self.assertTrue(second["cached"])
        self.assertEqual(start_thread.call_count, 1)
        second_task = screener_tasks.screener_tasks[second["task_id"]]
        self.assertEqual(second_task.status, "completed")
        self.assertEqual(second_task.run_id, "cached-run-001")

    def test_screener_cache_preflight_rejects_when_all_history_cache_is_missing_as_of_bar(
        self,
    ):
        config = self._cn_cache_only_config(
            manifest_path=self._write_cn_manifest(),
            history_dir=self._save_single_cn_history_bar("2026-03-23"),
        )

        with self.assertRaises(HTTPException) as context:
            screener_service.ensure_screener_cache_coverage(config)

        self.assertEqual(context.exception.status_code, 409)
        detail = context.exception.detail
        self.assertEqual(detail["code"], "screener_data_not_ready")
        self.assertEqual(detail["symbols_checked"], 1)
        self.assertEqual(detail["symbols_missing"], 1)
        self.assertEqual(detail["examples"][0]["reason"], "missing_as_of_bar")

    def test_screener_cache_preflight_allows_partial_missing_as_of_bars(self):
        config = self._cn_cache_only_config(
            manifest_path=self._write_cn_manifest_with_symbols(
                ["600519.SH", "000001.SZ", "000002.SZ"]
            ),
            history_dir=self._save_cn_history_bars(
                {
                    "600519.SH": "2026-03-24",
                    "000001.SZ": "2026-03-24",
                    "000002.SZ": "2026-03-23",
                }
            ),
        )

        screener_service.ensure_screener_cache_coverage(config)

    def test_screener_cache_preflight_accepts_history_covering_as_of_date(self):
        config = self._cn_cache_only_config(
            manifest_path=self._write_cn_manifest(),
            history_dir=self._save_single_cn_history_bar("2026-03-24"),
        )

        screener_service.ensure_screener_cache_coverage(config)

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
                patch.object(
                    app_config, "SCREENER_STATE_DIR", Path(temp_dir) / "state"
                ),
                patch(
                    "web.backend.auth.get_auth_settings",
                    return_value=SimpleNamespace(enabled=False),
                ),
            ):
                screener_results.migrate_legacy_screener_results(force=True)
                rows = screener_service.get_screener_run_candidates(run_id)

        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["breakout_type"])
        self.assertEqual(rows[0]["strategy_tags"], "")
        self.assertEqual(rows[0]["risk_flags"], "")


if __name__ == "__main__":
    unittest.main()
