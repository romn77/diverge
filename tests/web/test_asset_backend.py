import asyncio
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

from tests.web.auth_helpers import AuthClientMixin
from tests.web.http_harness import app_client
from web.backend import app_config, auth
from web.backend.main import app
from web.backend.runtime import analysis_tasks, screener_tasks


class AssetBackendTests(AuthClientMixin, unittest.TestCase):
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
        auth.reset_runtime_state()

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
        self.temp_dir.cleanup()

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

    async def _create_user(self, client, *, email: str, password: str) -> str:
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

    def _manual_asset_payload(
        self,
        *,
        asset_name: str,
        ticker: str | None = None,
        quantity: float = 1.0,
        cost_basis: float = 10000.0,
        manual_price: float = 10000.0,
    ) -> dict:
        return {
            "platform_name": "Broker",
            "account_name": "Core",
            "asset_name": asset_name,
            "asset_category": "stock" if ticker else "cash",
            "quantity": quantity,
            "cost_basis": cost_basis,
            "valuation_mode": "manual",
            "ticker": ticker,
            "currency": "USD",
            "manual_price": manual_price,
            "notes": "owner-scoped test asset",
        }

    def _task_payload(self, ticker: str = "MSFT", output_language: str = "en") -> dict:
        return {
            "ticker": ticker,
            "analysis_date": "2026-04-23",
            "analysts": ["market", "news"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_think_llm": "gpt-5-mini",
            "deep_think_llm": "gpt-5.2",
            "output_language": output_language,
            "openai_reasoning_effort": "medium",
            "google_thinking_level": None,
        }

    def test_asset_routes_are_owner_scoped_when_auth_enabled(self):
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
                    "/api/assets",
                    json=self._manual_asset_payload(asset_name="Cash Reserve"),
                )
                self.assertEqual(create_response.status_code, 200, create_response.text)
                position = create_response.json()
                position_id = position["id"]
                self.assertEqual(position["account"]["platform_name"], "Broker")

                summary_response = await owner_one_client.get(
                    "/api/assets/summary",
                    params={"base_currency": "USD", "refresh_if_stale": "false"},
                )
                self.assertEqual(
                    summary_response.status_code, 200, summary_response.text
                )
                summary = summary_response.json()
                self.assertEqual(summary["totals"]["position_count"], 1)
                self.assertAlmostEqual(summary["totals"]["market_value"], 10000.0)

                detail_response = await owner_one_client.get(
                    f"/api/assets/{position_id}"
                )
                self.assertEqual(detail_response.status_code, 200, detail_response.text)

            async with self._client() as owner_two_client:
                await self._login(
                    owner_two_client, "owner-two@example.com", "OwnerTwoPass123"
                )

                list_response = await owner_two_client.get("/api/assets")
                self.assertEqual(list_response.status_code, 200, list_response.text)
                self.assertEqual(list_response.json(), [])

                summary_response = await owner_two_client.get(
                    "/api/assets/summary",
                    params={"base_currency": "USD", "refresh_if_stale": "false"},
                )
                self.assertEqual(
                    summary_response.status_code, 200, summary_response.text
                )
                self.assertEqual(summary_response.json()["totals"]["position_count"], 0)

                detail_response = await owner_two_client.get(
                    f"/api/assets/{position_id}"
                )
                self.assertEqual(detail_response.status_code, 404, detail_response.text)

        asyncio.run(scenario())

    def test_asset_summary_default_is_read_only_for_write_denied_user(self):
        async def scenario():
            async with self._client() as admin_client:
                await self._login(
                    admin_client,
                    "admin@example.com",
                    "AdminPass123",
                    new_password="AdminPass456",
                )
                owner_id = await self._create_user(
                    admin_client,
                    email="readonly-assets@example.com",
                    password="OwnerPass123",
                )

            async with self._client() as owner_client:
                await self._login(
                    owner_client, "readonly-assets@example.com", "OwnerPass123"
                )
                create_response = await owner_client.post(
                    "/api/assets",
                    json=self._manual_asset_payload(asset_name="Cash Reserve"),
                )
                self.assertEqual(create_response.status_code, 200, create_response.text)

            with patch.dict(
                "os.environ",
                {
                    "AUTH_ENABLED": "true",
                    "AUTH_MODE": "required",
                    "DATABASE_URL": self.database_url,
                },
                clear=False,
            ):
                auth.reset_runtime_state()
                with auth.db_session() as db:
                    auth.set_user_permission(
                        db,
                        owner_id,
                        auth.PERMISSION_ASSETS_WRITE,
                        effect=auth.PERMISSION_EFFECT_DENY,
                    )

            async with self._client() as owner_client:
                await self._login(
                    owner_client, "readonly-assets@example.com", "OwnerPass123"
                )
                summary_response = await owner_client.get("/api/assets/summary")
                self.assertEqual(
                    summary_response.status_code, 200, summary_response.text
                )
                self.assertEqual(summary_response.json()["totals"]["position_count"], 1)

                refresh_response = await owner_client.get(
                    "/api/assets/summary",
                    params={"refresh_if_stale": "true"},
                )
                self.assertEqual(
                    refresh_response.status_code, 403, refresh_response.text
                )

        asyncio.run(scenario())

    def test_task_creation_injects_owner_portfolio_context(self):
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

            async with self._client() as owner_client:
                await self._login(
                    owner_client, "owner-one@example.com", "OwnerOnePass123"
                )
                asset_response = await owner_client.post(
                    "/api/assets",
                    json=self._manual_asset_payload(
                        asset_name="Microsoft Corp",
                        ticker="MSFT",
                        quantity=10.0,
                        cost_basis=400.0,
                        manual_price=420.0,
                    ),
                )
                self.assertEqual(asset_response.status_code, 200, asset_response.text)

                with (
                    patch("web.backend.routers.tasks.hydrate_provider_credentials"),
                    patch(
                        "web.backend.routers.tasks.get_provider_availability",
                        return_value={"enabled": True, "disabled_reason": None},
                    ),
                    patch(
                        "web.backend.routers.tasks.llm_models.ensure_model_selection_available"
                    ),
                    patch(
                        "web.backend.runtime.analysis_tasks.start_task_thread"
                    ) as start_task_thread,
                ):
                    task_response = await owner_client.post(
                        "/api/tasks",
                        json=self._task_payload("MSFT"),
                    )

                self.assertEqual(task_response.status_code, 200, task_response.text)
                start_task_thread.assert_called_once()

                task_id = task_response.json()["task_id"]
                task = analysis_tasks.get_task(task_id)
                self.assertEqual(task.owner_user_id, owner_one_id)
                self.assertIsNotNone(task.request.portfolio_context)
                self.assertIn("Existing MSFT exposure", task.request.portfolio_context)
                self.assertIn("qty 10", task.request.portfolio_context)
                self.assertIn("Tracked holdings: 1", task.request.portfolio_context)
                self.assertNotIn(
                    "Portfolio Ledger Context", task.request.portfolio_context
                )

        asyncio.run(scenario())

    def test_task_creation_localizes_portfolio_context(self):
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
                    email="owner-cn@example.com",
                    password="OwnerCnPass123",
                )

            async with self._client() as owner_client:
                await self._login(
                    owner_client, "owner-cn@example.com", "OwnerCnPass123"
                )
                asset_response = await owner_client.post(
                    "/api/assets",
                    json=self._manual_asset_payload(
                        asset_name="Micron Technology",
                        ticker="MU",
                        quantity=5.0,
                        cost_basis=80.0,
                        manual_price=95.0,
                    ),
                )
                self.assertEqual(asset_response.status_code, 200, asset_response.text)

                with (
                    patch("web.backend.routers.tasks.hydrate_provider_credentials"),
                    patch(
                        "web.backend.routers.tasks.get_provider_availability",
                        return_value={"enabled": True, "disabled_reason": None},
                    ),
                    patch(
                        "web.backend.routers.tasks.llm_models.ensure_model_selection_available"
                    ),
                    patch("web.backend.runtime.analysis_tasks.start_task_thread"),
                ):
                    task_response = await owner_client.post(
                        "/api/tasks",
                        json=self._task_payload("MU", output_language="cn"),
                    )

                self.assertEqual(task_response.status_code, 200, task_response.text)
                task = analysis_tasks.get_task(task_response.json()["task_id"])
                self.assertIsNotNone(task.request.portfolio_context)
                self.assertIn("当前持仓参考", task.request.portfolio_context)
                self.assertIn("当前标的 MU 持仓", task.request.portfolio_context)
                self.assertIn("数量 5", task.request.portfolio_context)
                self.assertNotIn(
                    "Portfolio Ledger Context", task.request.portfolio_context
                )

        asyncio.run(scenario())
