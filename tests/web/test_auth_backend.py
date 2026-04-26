import asyncio
import json
import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tradingagents.runner import AnalysisRequest
from tests.web.auth_helpers import AuthClientMixin
from tests.web.http_harness import app_client
from web.backend import analysis_limits, app_config, auth, screener_results, screener_runs
from web.backend.main import app
from web.backend.runtime import analysis_tasks, screener_tasks


class AuthBackendTests(AuthClientMixin, unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_reports_dir = app_config.REPORTS_DIR
        self.original_screener_results_dir = app_config.SCREENER_RESULTS_DIR
        self.original_screener_state_dir = app_config.SCREENER_STATE_DIR
        self.original_screener_tasks_dir = app_config.SCREENER_TASKS_DIR
        self.original_screener_cache_dir = app_config.SCREENER_CACHE_DIR
        self.original_stock_history_dir = app_config.STOCK_HISTORY_DIR
        self.original_tmp_reports_dir = app_config.TMP_REPORTS_DIR
        app_config.REPORTS_DIR = Path(self.temp_dir.name) / "data" / "reports"
        app_config.SCREENER_RESULTS_DIR = Path(self.temp_dir.name) / "data" / "screener" / "runs"
        app_config.SCREENER_STATE_DIR = Path(self.temp_dir.name) / "data" / "screener" / "state"
        app_config.SCREENER_TASKS_DIR = Path(self.temp_dir.name) / "data" / "screener" / "tasks"
        app_config.SCREENER_CACHE_DIR = Path(self.temp_dir.name) / "data" / "cache" / "screener"
        app_config.STOCK_HISTORY_DIR = Path(self.temp_dir.name) / "data" / "history"
        app_config.TMP_REPORTS_DIR = app_config.REPORTS_DIR / ".tmp"
        app_config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        app_config.SCREENER_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        app_config.SCREENER_STATE_DIR.mkdir(parents=True, exist_ok=True)
        app_config.SCREENER_TASKS_DIR.mkdir(parents=True, exist_ok=True)
        app_config.SCREENER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        app_config.STOCK_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        analysis_tasks.tasks.clear()
        screener_tasks.screener_tasks.clear()
        self.database_url = f"sqlite+pysqlite:///{Path(self.temp_dir.name) / 'auth.db'}"
        auth.reset_runtime_state()

    def tearDown(self):
        app_config.REPORTS_DIR = self.original_reports_dir
        app_config.SCREENER_RESULTS_DIR = self.original_screener_results_dir
        app_config.SCREENER_STATE_DIR = self.original_screener_state_dir
        app_config.SCREENER_TASKS_DIR = self.original_screener_tasks_dir
        app_config.SCREENER_CACHE_DIR = self.original_screener_cache_dir
        app_config.STOCK_HISTORY_DIR = self.original_stock_history_dir
        app_config.TMP_REPORTS_DIR = self.original_tmp_reports_dir
        analysis_tasks.tasks.clear()
        screener_tasks.screener_tasks.clear()
        screener_results.reset_screener_result_observability()
        auth.reset_runtime_state()
        self.temp_dir.cleanup()

    def _write_report(self, report_id: str = "SPY_20260305_155836") -> None:
        report_dir = app_config.REPORTS_DIR / report_id
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "complete_report.md").write_text(
            "# Trading Analysis Report: SPY\n\nGenerated: 2026-03-05 15:58:40\n\n",
            encoding="utf-8",
        )

    @asynccontextmanager
    async def _client(
        self,
        *,
        auth_enabled: bool,
        auth_mode: str = "required",
        extra_env: dict[str, str] | None = None,
    ):
        env = {
            "AUTH_ENABLED": "true" if auth_enabled else "false",
            "AUTH_MODE": auth_mode,
            "DATABASE_URL": self.database_url,
            "AUTH_BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
            "AUTH_BOOTSTRAP_ADMIN_PASSWORD": "AdminPass123",
            "AUTH_BOOTSTRAP_ADMIN_DISPLAY_NAME": "Admin User",
        }
        if extra_env:
            env.update(extra_env)

        with patch.dict(os.environ, env, clear=False):
            auth.reset_runtime_state()
            if auth_enabled:
                auth.create_all_for_testing()
            async with app_client(app) as client:
                yield client
            auth.reset_runtime_state()

    async def _create_user(
        self,
        client,
        *,
        email: str,
        display_name: str,
        password: str,
        role: str,
    ) -> dict:
        response = await client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": display_name,
                "password": password,
                "role": role,
                "status": "active",
                "must_change_password": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _write_screener_run(
        self,
        run_id: str,
        *,
        symbol: str,
        markets: list[str] | None = None,
    ) -> None:
        resolved_markets = markets or ["cn"]
        run_dir = app_config.SCREENER_RESULTS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_meta.json").write_text(
            json.dumps(
                {
                    "run_timestamp": run_id,
                    "as_of_date": "2026-03-24",
                    "config": {"markets": resolved_markets},
                    "candidate_count": 1,
                    "filtered_count_by_reason": {"liquidity_floor": 2},
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "candidates.csv").write_text(
            f"symbol,market,global_rank,total_score\n{symbol},{resolved_markets[0]},1,0.91\n",
            encoding="utf-8",
        )

    def _write_history_cache(self, *, market: str, symbol: str) -> None:
        cache_path = app_config.STOCK_HISTORY_DIR / market / f"{symbol}.csv"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            (
                "Date,Open,High,Low,Close,Volume,Amount\n"
                "2025-02-17,180,184,179,182,900,163800\n"
                "2026-03-21,210,214,209,213,1000,213000\n"
                "2026-03-24,214,216,213,215,1200,258000\n"
            ),
            encoding="utf-8",
        )

    def test_auth_disabled_keeps_existing_routes_public(self):
        async def scenario():
            self._write_report()

            async with self._client(auth_enabled=False) as client:
                me_response = await client.get("/api/auth/me")
                self.assertEqual(me_response.status_code, 200)
                self.assertEqual(
                    me_response.json(),
                    {
                        "enabled": False,
                        "mode": "disabled",
                        "authenticated": False,
                        "user": None,
                    },
                )

                reports_response = await client.get("/api/reports")
                self.assertEqual(reports_response.status_code, 200)
                self.assertEqual(len(reports_response.json()), 1)

                login_response = await client.post(
                    "/api/auth/login",
                    json={"email": "admin@example.com", "password": "AdminPass123"},
                )
                self.assertEqual(login_response.status_code, 409)

        asyncio.run(scenario())

    def test_required_mode_requires_login_and_supports_password_change(self):
        async def scenario():
            self._write_report()
            self._write_history_cache(market="us", symbol="AAPL")

            async with self._client(auth_enabled=True, auth_mode="required") as client:
                self.assertEqual((await client.get("/api/reports")).status_code, 401)
                self.assertEqual(
                    (
                        await client.get(
                            "/api/ticker-history",
                            params={"symbol": "AAPL", "as_of_date": "2026-03-24"},
                        )
                    ).status_code,
                    401,
                )

                login_payload = await self._login(client, "admin@example.com", "AdminPass123")
                self.assertTrue(login_payload["authenticated"])
                self.assertEqual(login_payload["user"]["email"], "admin@example.com")
                self.assertTrue(login_payload["user"]["must_change_password"])

                me_response = await client.get("/api/auth/me")
                self.assertEqual(me_response.status_code, 200)
                self.assertTrue(me_response.json()["user"]["must_change_password"])

                self.assertEqual((await client.get("/api/reports")).status_code, 403)
                self.assertEqual(
                    (
                        await client.get(
                            "/api/ticker-history",
                            params={"symbol": "AAPL", "as_of_date": "2026-03-24"},
                        )
                    ).status_code,
                    403,
                )

                history_response = await client.get(
                    "/api/ticker-history",
                    params={"symbol": "AAPL", "as_of_date": "2026-03-24"},
                )
                self.assertEqual(history_response.status_code, 403, history_response.text)

                change_password_response = await client.post(
                    "/api/auth/change-password",
                    json={
                        "current_password": "AdminPass123",
                        "new_password": "AdminPass456",
                    },
                )
                self.assertEqual(change_password_response.status_code, 200)
                self.assertFalse(change_password_response.json()["user"]["must_change_password"])

                reports_response = await client.get("/api/reports")
                self.assertEqual(reports_response.status_code, 200)
                history_response = await client.get(
                    "/api/ticker-history",
                    params={"symbol": "AAPL", "as_of_date": "2026-03-24"},
                )
                self.assertEqual(history_response.status_code, 200, history_response.text)
                self.assertEqual(history_response.json()["points"][0]["close"], 182.0)

                logout_response = await client.post("/api/auth/logout")
                self.assertEqual(logout_response.status_code, 200)
                self.assertFalse(logout_response.json()["authenticated"])
                self.assertEqual((await client.get("/api/reports")).status_code, 401)

                old_login_response = await client.post(
                    "/api/auth/login",
                    json={"email": "admin@example.com", "password": "AdminPass123"},
                )
                self.assertEqual(old_login_response.status_code, 401)

                new_login_response = await client.post(
                    "/api/auth/login",
                    json={"email": "admin@example.com", "password": "AdminPass456"},
                )
                self.assertEqual(new_login_response.status_code, 200)

        asyncio.run(scenario())

    def test_login_throttles_repeated_failures(self):
        async def scenario():
            async with self._client(auth_enabled=True, auth_mode="required") as client:
                for _ in range(auth.LOGIN_FAILURE_LIMIT):
                    response = await client.post(
                        "/api/auth/login",
                        json={"email": "admin@example.com", "password": "wrong-password"},
                    )
                    self.assertEqual(response.status_code, 401, response.text)

                locked_response = await client.post(
                    "/api/auth/login",
                    json={"email": "admin@example.com", "password": "wrong-password"},
                )
                self.assertEqual(locked_response.status_code, 429, locked_response.text)

                correct_response = await client.post(
                    "/api/auth/login",
                    json={"email": "admin@example.com", "password": "AdminPass123"},
                )
                self.assertEqual(correct_response.status_code, 429, correct_response.text)

            async with self._client(auth_enabled=True, auth_mode="required") as client:
                for index in range(auth.LOGIN_FAILURE_LIMIT):
                    response = await client.post(
                        "/api/auth/login",
                        json={
                            "email": f"missing-{index}@example.com",
                            "password": "wrong-password",
                        },
                    )
                    self.assertEqual(response.status_code, 401, response.text)

                correct_response = await client.post(
                    "/api/auth/login",
                    json={"email": "admin@example.com", "password": "AdminPass123"},
                )
                self.assertEqual(correct_response.status_code, 429, correct_response.text)

        asyncio.run(scenario())

    def test_login_rate_limit_uses_forwarded_client_ip_from_trusted_proxy(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="172.18.0.5"),
            headers={"x-forwarded-for": "198.51.100.7, 203.0.113.9"},
        )
        untrusted_request = SimpleNamespace(
            client=SimpleNamespace(host="203.0.113.200"),
            headers={"x-forwarded-for": "198.51.100.7"},
        )
        invalid_forwarded_request = SimpleNamespace(
            client=SimpleNamespace(host="172.18.0.5"),
            headers={"x-forwarded-for": "not-an-ip"},
        )

        with patch.dict(
            os.environ,
            {"TRUSTED_PROXY_CIDRS": "172.16.0.0/12"},
            clear=False,
        ):
            self.assertEqual(auth.client_ip_for_request(request), "203.0.113.9")
            self.assertEqual(
                auth.client_ip_for_request(untrusted_request),
                "203.0.113.200",
            )
            self.assertEqual(
                auth.client_ip_for_request(invalid_forwarded_request),
                "172.18.0.5",
            )

    def test_optional_mode_keeps_existing_routes_public_but_admin_routes_protected(self):
        async def scenario():
            self._write_report()
            self._write_history_cache(market="us", symbol="AAPL")

            async with self._client(auth_enabled=True, auth_mode="optional") as client:
                self.assertEqual((await client.get("/api/reports")).status_code, 200)
                self.assertEqual((await client.get("/api/admin/users")).status_code, 401)
                history_response = await client.get(
                    "/api/ticker-history",
                    params={"symbol": "AAPL", "as_of_date": "2026-03-24"},
                )
                self.assertEqual(history_response.status_code, 200, history_response.text)
                self.assertEqual(history_response.json()["market"], "us")

        asyncio.run(scenario())

    def test_admin_routes_require_admin_role_and_support_user_crud(self):
        async def scenario():
            async with self._client(auth_enabled=True, auth_mode="required") as admin_client:
                await self._login(
                    admin_client,
                    "admin@example.com",
                    "AdminPass123",
                    new_password="AdminPass456",
                )

                create_response = await admin_client.post(
                    "/api/admin/users",
                    json={
                        "email": "operator@example.com",
                        "display_name": "Operator User",
                        "password": "OperatorPass123",
                        "role": "operator",
                        "status": "active",
                        "must_change_password": False,
                    },
                )
                self.assertEqual(create_response.status_code, 200, create_response.text)
                operator_id = create_response.json()["id"]

                list_response = await admin_client.get("/api/admin/users")
                self.assertEqual(list_response.status_code, 200)
                self.assertEqual(len(list_response.json()), 2)

                update_response = await admin_client.put(
                    f"/api/admin/users/{operator_id}",
                    json={"display_name": "Operator Prime", "status": "disabled"},
                )
                self.assertEqual(update_response.status_code, 200)
                self.assertEqual(update_response.json()["display_name"], "Operator Prime")
                self.assertEqual(update_response.json()["status"], "disabled")

                reset_response = await admin_client.post(
                    f"/api/admin/users/{operator_id}/reset-password",
                    json={"new_password": "ResetPass123", "must_change_password": True},
                )
                self.assertEqual(reset_response.status_code, 200)
                self.assertTrue(reset_response.json()["must_change_password"])

                reenable_response = await admin_client.put(
                    f"/api/admin/users/{operator_id}",
                    json={"status": "active"},
                )
                self.assertEqual(reenable_response.status_code, 200)
                self.assertEqual(reenable_response.json()["status"], "active")

            async with self._client(auth_enabled=True, auth_mode="required") as operator_client:
                login_response = await operator_client.post(
                    "/api/auth/login",
                    json={"email": "operator@example.com", "password": "ResetPass123"},
                )
                self.assertEqual(login_response.status_code, 200, login_response.text)
                self.assertEqual((await operator_client.get("/api/admin/users")).status_code, 403)

            async with self._client(auth_enabled=True, auth_mode="required") as admin_client:
                await self._login(admin_client, "admin@example.com", "AdminPass456")
                delete_response = await admin_client.delete(f"/api/admin/users/{operator_id}")
                self.assertEqual(delete_response.status_code, 200)
                self.assertEqual(delete_response.json()["user_id"], operator_id)

        asyncio.run(scenario())

    def test_screener_tasks_scope_to_owner_and_allow_viewer_limited_usage(self):
        async def scenario():
            async with self._client(auth_enabled=True, auth_mode="required") as admin_client:
                await self._login(
                    admin_client,
                    "admin@example.com",
                    "AdminPass123",
                    new_password="AdminPass456",
                )
                operator_user = await self._create_user(
                    admin_client,
                    email="operator.one@example.com",
                    display_name="Operator One",
                    password="OperatorPass123",
                    role="operator",
                )
                await self._create_user(
                    admin_client,
                    email="operator.two@example.com",
                    display_name="Operator Two",
                    password="OperatorPass123",
                    role="operator",
                )
                await self._create_user(
                    admin_client,
                    email="viewer@example.com",
                    display_name="Viewer User",
                    password="ViewerPass123",
                    role="viewer",
                )

            async with self._client(auth_enabled=True, auth_mode="required") as operator_client:
                await self._login(operator_client, "operator.one@example.com", "OperatorPass123")
                with patch("web.backend.runtime.screener_tasks.start_screener_task_thread") as start_task_thread:
                    create_response = await operator_client.post(
                        "/api/screener/tasks",
                        json={
                            "markets": ["cn"],
                            "as_of_date": "2026-03-24",
                            "top_k": 20,
                            "cn_data_source": "tushare",
                        },
                    )
                self.assertEqual(create_response.status_code, 200, create_response.text)
                start_task_thread.assert_called_once()

                task_id = create_response.json()["task_id"]
                task_response = await operator_client.get(f"/api/screener/tasks/{task_id}")
                self.assertEqual(task_response.status_code, 200, task_response.text)
                self.assertEqual(task_response.json()["owner_user_id"], operator_user["id"])

                list_response = await operator_client.get("/api/screener/tasks")
                self.assertEqual(list_response.status_code, 200, list_response.text)
                self.assertEqual([row["id"] for row in list_response.json()], [task_id])

                snapshot_path = (
                    app_config.SCREENER_TASKS_DIR
                    / app_config.ACTIVE_TASKS_DIRNAME
                    / task_id
                    / "task.json"
                )
                snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
                self.assertEqual(snapshot_payload["owner_user_id"], operator_user["id"])

            async with self._client(auth_enabled=True, auth_mode="required") as other_operator_client:
                await self._login(other_operator_client, "operator.two@example.com", "OperatorPass123")
                list_response = await other_operator_client.get("/api/screener/tasks")
                self.assertEqual(list_response.status_code, 200, list_response.text)
                self.assertEqual(list_response.json(), [])
                self.assertEqual(
                    (await other_operator_client.get(f"/api/screener/tasks/{task_id}")).status_code,
                    404,
                )

            async with self._client(auth_enabled=True, auth_mode="required") as viewer_client:
                await self._login(viewer_client, "viewer@example.com", "ViewerPass123")
                list_response = await viewer_client.get("/api/screener/tasks")
                self.assertEqual(list_response.status_code, 200, list_response.text)
                self.assertEqual(list_response.json(), [])

            async with self._client(auth_enabled=True, auth_mode="required") as admin_client:
                await self._login(admin_client, "admin@example.com", "AdminPass456")
                list_response = await admin_client.get("/api/screener/tasks")
                self.assertEqual(list_response.status_code, 200, list_response.text)
                self.assertEqual([row["id"] for row in list_response.json()], [task_id])

        asyncio.run(scenario())

    def test_analysis_tasks_require_owner_or_admin_to_read_payloads(self):
        async def scenario():
            async with self._client(auth_enabled=True, auth_mode="required") as admin_client:
                await self._login(
                    admin_client,
                    "admin@example.com",
                    "AdminPass123",
                    new_password="AdminPass456",
                )
                operator_one = await self._create_user(
                    admin_client,
                    email="operator.one@example.com",
                    display_name="Operator One",
                    password="OperatorPass123",
                    role="operator",
                )
                await self._create_user(
                    admin_client,
                    email="operator.two@example.com",
                    display_name="Operator Two",
                    password="OperatorPass123",
                    role="operator",
                )

            task = analysis_tasks.Task(
                id="task-owned",
                request=AnalysisRequest(
                    ticker="MSFT",
                    analysis_date="2026-04-23",
                    analysts=["market"],
                    research_depth=1,
                    llm_provider="openai",
                    quick_think_llm="gpt-5-mini",
                    deep_think_llm="gpt-5.2",
                    output_language="en",
                    openai_reasoning_effort="medium",
                    google_thinking_level=None,
                    portfolio_context="owner-one private portfolio context",
                ),
                owner_user_id=operator_one["id"],
                status="completed",
                report_id="MSFT_20260423_120000",
            )
            analysis_tasks.tasks[task.id] = task

            async with self._client(auth_enabled=True, auth_mode="required") as operator_client:
                await self._login(operator_client, "operator.one@example.com", "OperatorPass123")
                list_response = await operator_client.get("/api/tasks")
                self.assertEqual(list_response.status_code, 200, list_response.text)
                self.assertEqual([row["id"] for row in list_response.json()], ["task-owned"])
                self.assertIn(
                    "owner-one private portfolio context",
                    list_response.json()[0]["request_payload"]["portfolio_context"],
                )

                detail_response = await operator_client.get("/api/tasks/task-owned")
                self.assertEqual(detail_response.status_code, 200, detail_response.text)

            async with self._client(auth_enabled=True, auth_mode="required") as other_client:
                await self._login(other_client, "operator.two@example.com", "OperatorPass123")
                list_response = await other_client.get("/api/tasks")
                self.assertEqual(list_response.status_code, 200, list_response.text)
                self.assertEqual(list_response.json(), [])
                self.assertEqual((await other_client.get("/api/tasks/task-owned")).status_code, 404)
                self.assertEqual(
                    (await other_client.get("/api/tasks/task-owned/stream")).status_code,
                    404,
                )

            async with self._client(auth_enabled=True, auth_mode="required") as admin_client:
                await self._login(admin_client, "admin@example.com", "AdminPass456")
                list_response = await admin_client.get("/api/tasks")
                self.assertEqual(list_response.status_code, 200, list_response.text)
                self.assertEqual([row["id"] for row in list_response.json()], ["task-owned"])

        asyncio.run(scenario())

    def test_analysis_tasks_enforce_admin_configured_weekly_role_limits(self):
        task_payload = {
            "ticker": "MSFT",
            "analysis_date": "2026-04-23",
            "analysts": ["market"],
            "research_depth": 1,
            "llm_provider": "openai",
            "quick_think_llm": "gpt-5-mini",
            "deep_think_llm": "gpt-5.2",
            "output_language": "en",
            "openai_reasoning_effort": "medium",
            "google_thinking_level": None,
        }

        async def scenario():
            async with self._client(auth_enabled=True, auth_mode="required") as admin_client:
                await self._login(
                    admin_client,
                    "admin@example.com",
                    "AdminPass123",
                    new_password="AdminPass456",
                )
                await self._create_user(
                    admin_client,
                    email="operator.limited@example.com",
                    display_name="Limited Operator",
                    password="OperatorPass123",
                    role="operator",
                )

                limits_response = await admin_client.put(
                    "/api/admin/analysis-limits",
                    json={
                        "limits": [
                            {"role": "admin", "weekly_limit": None},
                            {"role": "operator", "weekly_limit": 1},
                            {"role": "viewer", "weekly_limit": 4},
                        ]
                    },
                )
                self.assertEqual(limits_response.status_code, 200, limits_response.text)
                self.assertEqual(
                    {
                        row["role"]: row["weekly_limit"]
                        for row in limits_response.json()["limits"]
                    },
                    {"admin": None, "operator": 1, "viewer": 4},
                )

            async with self._client(auth_enabled=True, auth_mode="required") as operator_client:
                await self._login(
                    operator_client,
                    "operator.limited@example.com",
                    "OperatorPass123",
                )
                with (
                    patch("web.backend.routers.tasks.hydrate_provider_credentials"),
                    patch(
                        "web.backend.routers.tasks.get_provider_availability",
                        return_value={"enabled": True, "disabled_reason": None},
                    ),
                    patch("web.backend.runtime.analysis_tasks.start_task_thread") as start_task_thread,
                ):
                    first_response = await operator_client.post("/api/tasks", json=task_payload)
                    second_response = await operator_client.post(
                        "/api/tasks",
                        json={**task_payload, "ticker": "AAPL"},
                    )

                self.assertEqual(first_response.status_code, 200, first_response.text)
                self.assertEqual(second_response.status_code, 429, second_response.text)
                self.assertIn("Weekly analysis limit", second_response.json()["detail"])
                start_task_thread.assert_called_once()

        asyncio.run(scenario())

    def test_admin_users_include_weekly_usage_stats_and_reset_current_week(self):
        async def scenario():
            async with self._client(auth_enabled=True, auth_mode="required") as admin_client:
                await self._login(
                    admin_client,
                    "admin@example.com",
                    "AdminPass123",
                    new_password="AdminPass456",
                )
                operator_user = await self._create_user(
                    admin_client,
                    email="operator.usage@example.com",
                    display_name="Usage Operator",
                    password="OperatorPass123",
                    role="operator",
                )

                with auth.db_session() as db:
                    persisted_user = auth.get_user_by_id(db, operator_user["id"])
                    analysis_limits.record_module_usage(db, persisted_user, module="analysis")
                    analysis_limits.record_module_usage(db, persisted_user, module="screener")

                users_response = await admin_client.get("/api/admin/users")
                self.assertEqual(users_response.status_code, 200, users_response.text)
                usage_user = next(
                    row
                    for row in users_response.json()
                    if row["id"] == operator_user["id"]
                )
                self.assertEqual(usage_user["usage"]["weekly_limit"], 20)
                self.assertEqual(
                    usage_user["usage"]["modules"]["analysis"]["used_count"],
                    1,
                )
                self.assertEqual(
                    usage_user["usage"]["modules"]["screener"]["used_count"],
                    1,
                )

                reset_response = await admin_client.post(
                    f"/api/admin/users/{operator_user['id']}/usage/reset"
                )
                self.assertEqual(reset_response.status_code, 200, reset_response.text)
                self.assertEqual(reset_response.json()["reset_count"], 2)

                users_response = await admin_client.get("/api/admin/users")
                self.assertEqual(users_response.status_code, 200, users_response.text)
                usage_user = next(
                    row
                    for row in users_response.json()
                    if row["id"] == operator_user["id"]
                )
                self.assertEqual(
                    usage_user["usage"]["modules"]["analysis"]["used_count"],
                    0,
                )
                self.assertEqual(
                    usage_user["usage"]["modules"]["screener"]["used_count"],
                    0,
                )

        asyncio.run(scenario())

    def test_screener_runs_require_operator_role_and_scope_to_owner(self):
        async def scenario():
            async with self._client(auth_enabled=True, auth_mode="required") as admin_client:
                await self._login(
                    admin_client,
                    "admin@example.com",
                    "AdminPass123",
                    new_password="AdminPass456",
                )
                operator_one = await self._create_user(
                    admin_client,
                    email="operator.one@example.com",
                    display_name="Operator One",
                    password="OperatorPass123",
                    role="operator",
                )
                operator_two = await self._create_user(
                    admin_client,
                    email="operator.two@example.com",
                    display_name="Operator Two",
                    password="OperatorPass123",
                    role="operator",
                )
                await self._create_user(
                    admin_client,
                    email="viewer@example.com",
                    display_name="Viewer User",
                    password="ViewerPass123",
                    role="viewer",
                )

                self._write_screener_run("20260324_214530", symbol="600519.SH")
                self._write_screener_run("20260325_214530", symbol="AAPL", markets=["us"])
                with auth.db_session() as db:
                    screener_runs.upsert_screener_run(
                        db,
                        run_id="20260324_214530",
                        owner_user_id=operator_one["id"],
                        as_of_date="2026-03-24",
                        markets=["cn"],
                        candidate_count=1,
                        generated_at="20260324_214530",
                        storage_path="20260324_214530",
                        artifact_manifest={
                            "run_meta": "20260324_214530/run_meta.json",
                            "candidates": "20260324_214530/candidates.csv",
                        },
                    )
                    screener_runs.upsert_screener_run(
                        db,
                        run_id="20260325_214530",
                        owner_user_id=operator_two["id"],
                        as_of_date="2026-03-25",
                        markets=["us"],
                        candidate_count=1,
                        generated_at="20260325_214530",
                        storage_path="20260325_214530",
                        artifact_manifest={
                            "run_meta": "20260325_214530/run_meta.json",
                            "candidates": "20260325_214530/candidates.csv",
                        },
                    )

            async with self._client(auth_enabled=True, auth_mode="required") as operator_client:
                await self._login(operator_client, "operator.one@example.com", "OperatorPass123")
                list_response = await operator_client.get("/api/screener/runs")
                self.assertEqual(list_response.status_code, 200, list_response.text)
                self.assertEqual([row["id"] for row in list_response.json()], ["20260324_214530"])

                detail_response = await operator_client.get("/api/screener/runs/20260324_214530")
                self.assertEqual(detail_response.status_code, 200, detail_response.text)
                self.assertEqual(
                    detail_response.json()["filtered_count_by_reason"]["liquidity_floor"],
                    2,
                )

                candidates_response = await operator_client.get(
                    "/api/screener/runs/20260324_214530/candidates"
                )
                self.assertEqual(candidates_response.status_code, 200, candidates_response.text)
                self.assertEqual(candidates_response.json()[0]["symbol"], "600519.SH")

                self.assertEqual(
                    (await operator_client.get("/api/screener/runs/20260325_214530")).status_code,
                    404,
                )

            async with self._client(auth_enabled=True, auth_mode="required") as admin_client:
                await self._login(admin_client, "admin@example.com", "AdminPass456")
                list_response = await admin_client.get("/api/screener/runs")
                self.assertEqual(list_response.status_code, 200, list_response.text)
                self.assertEqual(
                    {row["id"] for row in list_response.json()},
                    {"20260324_214530", "20260325_214530"},
                )

            async with self._client(auth_enabled=True, auth_mode="required") as viewer_client:
                await self._login(viewer_client, "viewer@example.com", "ViewerPass123")
                list_response = await viewer_client.get("/api/screener/runs")
                self.assertEqual(list_response.status_code, 200, list_response.text)
                self.assertEqual(list_response.json(), [])

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
