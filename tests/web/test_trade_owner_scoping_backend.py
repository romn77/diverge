import asyncio
import json
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

from diverge import trade_feedback
from diverge.runner import AnalysisRequest
from tests.web.auth_helpers import AuthClientMixin
from tests.web.http_harness import app_client
from web.backend import app_config, auth
from web.backend.main import app
from web.backend.runtime import analysis_tasks, screener_tasks


class TradeOwnerScopingBackendTests(AuthClientMixin, unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "project"
        self.project_root.mkdir(parents=True)
        self.original_reports_dir = app_config.REPORTS_DIR
        self.original_screener_results_dir = app_config.SCREENER_RESULTS_DIR
        self.original_screener_tasks_dir = app_config.SCREENER_TASKS_DIR
        self.original_screener_cache_dir = app_config.SCREENER_CACHE_DIR
        self.original_stock_history_dir = app_config.STOCK_HISTORY_DIR
        self.original_tmp_reports_dir = app_config.TMP_REPORTS_DIR
        app_config.REPORTS_DIR = self.project_root / "data" / "reports"
        app_config.SCREENER_RESULTS_DIR = (
            self.project_root / "data" / "screener" / "runs"
        )
        app_config.SCREENER_TASKS_DIR = (
            self.project_root / "data" / "screener" / "tasks"
        )
        app_config.SCREENER_CACHE_DIR = (
            self.project_root / "data" / "cache" / "screener"
        )
        app_config.STOCK_HISTORY_DIR = self.project_root / "data" / "history"
        app_config.TMP_REPORTS_DIR = app_config.REPORTS_DIR / ".tmp"
        app_config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        app_config.SCREENER_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        app_config.SCREENER_TASKS_DIR.mkdir(parents=True, exist_ok=True)
        app_config.SCREENER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        app_config.STOCK_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        analysis_tasks.tasks.clear()
        screener_tasks.screener_tasks.clear()
        self.database_url = f"sqlite+pysqlite:///{self.project_root / 'auth.db'}"

        self.project_patch = patch.object(
            trade_feedback, "PROJECT_ROOT", self.project_root
        )
        self.project_patch.start()
        auth.reset_runtime_state()
        self._write_analysis_snapshot()

    def tearDown(self):
        app_config.REPORTS_DIR = self.original_reports_dir
        app_config.SCREENER_RESULTS_DIR = self.original_screener_results_dir
        app_config.SCREENER_TASKS_DIR = self.original_screener_tasks_dir
        app_config.SCREENER_CACHE_DIR = self.original_screener_cache_dir
        app_config.STOCK_HISTORY_DIR = self.original_stock_history_dir
        app_config.TMP_REPORTS_DIR = self.original_tmp_reports_dir
        analysis_tasks.tasks.clear()
        screener_tasks.screener_tasks.clear()
        auth.reset_runtime_state()
        self.project_patch.stop()
        self.temp_dir.cleanup()

    def _write_analysis_snapshot(self) -> None:
        report_dir = app_config.REPORTS_DIR / "MSFT_20260401_120000"
        eval_dir = (
            self.project_root
            / "data"
            / "eval_results"
            / "MSFT"
            / "DivergeStrategy_logs"
        )
        report_dir.mkdir(parents=True, exist_ok=True)
        eval_dir.mkdir(parents=True, exist_ok=True)

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

    @asynccontextmanager
    async def _client(self):
        env = {
            "AUTH_ENABLED": "true",
            "AUTH_MODE": "required",
            "DATABASE_URL": self.database_url,
            "AUTH_BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
            "AUTH_BOOTSTRAP_ADMIN_PASSWORD": "AdminPass123",
            "AUTH_BOOTSTRAP_ADMIN_DISPLAY_NAME": "Admin User",
        }
        with patch.dict("os.environ", env, clear=False):
            auth.reset_runtime_state()
            auth.create_all_for_testing()
            async with app_client(app) as client:
                yield client
            auth.reset_runtime_state()

    async def _create_user(
        self,
        client,
        *,
        email: str,
        password: str,
    ) -> str:
        response = await client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": email.split("@", 1)[0],
                "password": password,
                "role": "operator",
                "status": "active",
                "must_change_password": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def _trade_payload(self, notes: str) -> dict:
        return {
            "raw_symbol": "MSFT",
            "side": "long",
            "entry_timestamp": "2026-04-01T09:30:00",
            "entry_price": 420.0,
            "size": 10,
            "strategy_tags": ["pullback"],
            "entry_reason": "Cloud momentum remains durable.",
            "invalidation_condition": "Cloud demand weakens or price breaks support.",
            "planned_horizon": "swing_1_4w",
            "stop_loss": 408.0,
            "take_profit": 448.0,
            "notes": notes,
            "analysis_references": [
                {
                    "analysis_date": "2026-04-01",
                    "report_path": "data/reports/MSFT_20260401_120000/complete_report.md",
                    "full_state_log_path": "data/eval_results/MSFT/DivergeStrategy_logs/full_states_log_2026-04-01.json",
                }
            ],
        }

    def _review_payload(self) -> dict:
        return {
            "thesis_assessment": "The thesis stayed tied to durable cloud demand.",
            "timing_assessment": "Timing followed the planned pullback window.",
            "sizing_assessment": "Sizing matched the documented risk.",
            "discipline_assessment": "Execution remained aligned with the plan.",
            "outcome_summary": "The review focuses on process quality.",
            "improvement_actions": ["Write the invalidation clause before entry."],
            "ticker_specific_lessons": [
                "MSFT setups improve when cloud demand is explicit."
            ],
            "cross_ticker_tags": ["planned_stop"],
            "analysis_date": "2026-04-02",
        }

    def test_trade_routes_are_owner_scoped_when_auth_enabled(self):
        async def scenario():
            async with self._client() as admin_client:
                await self._login(
                    admin_client,
                    "admin@example.com",
                    "AdminPass123",
                    new_password="AdminPass456",
                )
                await self._create_user(
                    admin_client,
                    email="owner-one@example.com",
                    password="OwnerOnePass123",
                )
                await self._create_user(
                    admin_client,
                    email="owner-two@example.com",
                    password="OwnerTwoPass123",
                )

            async with self._client() as owner_one_client:
                await self._login(
                    owner_one_client, "owner-one@example.com", "OwnerOnePass123"
                )
                create_response = await owner_one_client.post(
                    "/api/trades",
                    json=self._trade_payload("Owner one trade."),
                )
                self.assertEqual(create_response.status_code, 200, create_response.text)
                trade_id = create_response.json()["trade_id"]

                save_response = await owner_one_client.put(
                    f"/api/trades/{trade_id}/reviews/entry_review",
                    json=self._review_payload(),
                )
                self.assertEqual(save_response.status_code, 200, save_response.text)

                trades_response = await owner_one_client.get("/api/trades")
                self.assertEqual(trades_response.status_code, 200)
                self.assertEqual(
                    [item["trade_id"] for item in trades_response.json()], [trade_id]
                )

                feedback_response = await owner_one_client.get(
                    "/api/trade-feedback/MSFT"
                )
                self.assertEqual(
                    feedback_response.status_code, 200, feedback_response.text
                )
                self.assertEqual(len(feedback_response.json()["reviews"]), 1)

            async with self._client() as owner_two_client:
                await self._login(
                    owner_two_client, "owner-two@example.com", "OwnerTwoPass123"
                )

                trades_response = await owner_two_client.get("/api/trades")
                self.assertEqual(trades_response.status_code, 200)
                self.assertEqual(trades_response.json(), [])

                detail_response = await owner_two_client.get(f"/api/trades/{trade_id}")
                self.assertEqual(detail_response.status_code, 404)

                reviews_response = await owner_two_client.get(
                    f"/api/trades/{trade_id}/reviews"
                )
                self.assertEqual(reviews_response.status_code, 404)

                feedback_response = await owner_two_client.get(
                    "/api/trade-feedback/MSFT"
                )
                self.assertEqual(
                    feedback_response.status_code, 200, feedback_response.text
                )
                self.assertEqual(feedback_response.json()["reviews"], [])
                self.assertEqual(feedback_response.json()["prompt"], "")

        asyncio.run(scenario())

    def test_run_task_passes_only_owner_visible_trade_ids_to_analysis(self):
        async def scenario():
            async with self._client() as admin_client:
                await self._login(
                    admin_client,
                    "admin@example.com",
                    "AdminPass123",
                    new_password="AdminPass456",
                )
                owner_one_id = await self._create_user(
                    admin_client,
                    email="owner-one@example.com",
                    password="OwnerOnePass123",
                )
                await self._create_user(
                    admin_client,
                    email="owner-two@example.com",
                    password="OwnerTwoPass123",
                )

            async with self._client() as owner_one_client:
                await self._login(
                    owner_one_client, "owner-one@example.com", "OwnerOnePass123"
                )
                owner_one_trade_response = await owner_one_client.post(
                    "/api/trades",
                    json=self._trade_payload("Owner one trade."),
                )
                self.assertEqual(
                    owner_one_trade_response.status_code,
                    200,
                    owner_one_trade_response.text,
                )
                owner_one_trade_id = owner_one_trade_response.json()["trade_id"]

            async with self._client() as owner_two_client:
                await self._login(
                    owner_two_client, "owner-two@example.com", "OwnerTwoPass123"
                )
                owner_two_trade_response = await owner_two_client.post(
                    "/api/trades",
                    json=self._trade_payload("Owner two trade."),
                )
                self.assertEqual(
                    owner_two_trade_response.status_code,
                    200,
                    owner_two_trade_response.text,
                )

            captured: dict[str, object] = {}

            def fake_stream(
                _request, _temp_dir, *, reports_dir=None, visible_trade_ids=None
            ):
                captured["reports_dir"] = reports_dir
                captured["visible_trade_ids"] = visible_trade_ids
                if False:
                    yield None
                return {}

            task = analysis_tasks.Task(
                id="task-owner-scope",
                request=AnalysisRequest(
                    ticker="MSFT",
                    analysis_date="2026-04-03",
                    analysts=["market"],
                    research_depth=1,
                    llm_provider="openai",
                    quick_think_llm="gpt-5-mini",
                    deep_think_llm="gpt-5.2",
                    output_language="en",
                    openai_reasoning_effort="medium",
                ),
                owner_user_id=owner_one_id,
            )
            analysis_tasks.tasks[task.id] = task

            with patch.dict(
                "os.environ",
                {
                    "AUTH_ENABLED": "true",
                    "AUTH_MODE": "required",
                    "DATABASE_URL": self.database_url,
                    "AUTH_BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
                    "AUTH_BOOTSTRAP_ADMIN_PASSWORD": "AdminPass123",
                },
                clear=False,
            ):
                with patch(
                    "web.backend.runtime.analysis_tasks.run_analysis_streaming",
                    side_effect=fake_stream,
                ):
                    with patch(
                        "web.backend.runtime.analysis_tasks.save_report_to_disk",
                        return_value=None,
                    ):
                        analysis_tasks.run_task(task.id)

            self.assertEqual(captured["reports_dir"], app_config.REPORTS_DIR)
            self.assertEqual(captured["visible_trade_ids"], {owner_one_trade_id})

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
