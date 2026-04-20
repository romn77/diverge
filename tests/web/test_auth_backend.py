import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from web.backend import auth
from web.backend import main as backend_main
from web.backend import screener_runs


class AuthBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_reports_dir = backend_main.REPORTS_DIR
        self.original_screener_results_dir = backend_main.SCREENER_RESULTS_DIR
        backend_main.REPORTS_DIR = Path(self.temp_dir.name) / "reports"
        backend_main.SCREENER_RESULTS_DIR = Path(self.temp_dir.name) / "screener"
        backend_main.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        backend_main.SCREENER_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        backend_main.tasks.clear()
        backend_main.screener_tasks.clear()
        self.database_url = f"sqlite+pysqlite:///{Path(self.temp_dir.name) / 'auth.db'}"
        auth.reset_runtime_state()

    def tearDown(self):
        backend_main.REPORTS_DIR = self.original_reports_dir
        backend_main.SCREENER_RESULTS_DIR = self.original_screener_results_dir
        backend_main.tasks.clear()
        backend_main.screener_tasks.clear()
        auth.reset_runtime_state()
        self.temp_dir.cleanup()

    def _write_report(self, report_id: str = "SPY_20260305_155836") -> None:
        report_dir = backend_main.REPORTS_DIR / report_id
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "complete_report.md").write_text(
            "# Trading Analysis Report: SPY\n\nGenerated: 2026-03-05 15:58:40\n\n",
            encoding="utf-8",
        )

    @contextmanager
    def _client(
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
            with TestClient(backend_main.app) as client:
                yield client
            auth.reset_runtime_state()

    def _login(self, client: TestClient, email: str, password: str) -> dict:
        response = client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _create_user(
        self,
        client: TestClient,
        *,
        email: str,
        display_name: str,
        password: str,
        role: str,
    ) -> dict:
        response = client.post(
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
        run_dir = backend_main.SCREENER_RESULTS_DIR / run_id
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

    def test_auth_disabled_keeps_existing_routes_public(self):
        self._write_report()

        with self._client(auth_enabled=False) as client:
            me_response = client.get("/api/auth/me")
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

            reports_response = client.get("/api/reports")
            self.assertEqual(reports_response.status_code, 200)
            self.assertEqual(len(reports_response.json()), 1)

            login_response = client.post(
                "/api/auth/login",
                json={"email": "admin@example.com", "password": "AdminPass123"},
            )
            self.assertEqual(login_response.status_code, 409)

    def test_required_mode_requires_login_and_supports_password_change(self):
        self._write_report()

        with self._client(auth_enabled=True, auth_mode="required") as client:
            self.assertEqual(client.get("/api/reports").status_code, 401)

            login_payload = self._login(client, "admin@example.com", "AdminPass123")
            self.assertTrue(login_payload["authenticated"])
            self.assertEqual(login_payload["user"]["email"], "admin@example.com")

            reports_response = client.get("/api/reports")
            self.assertEqual(reports_response.status_code, 200)

            change_password_response = client.post(
                "/api/auth/change-password",
                json={
                    "current_password": "AdminPass123",
                    "new_password": "AdminPass456",
                },
            )
            self.assertEqual(change_password_response.status_code, 200)
            self.assertFalse(change_password_response.json()["user"]["must_change_password"])

            logout_response = client.post("/api/auth/logout")
            self.assertEqual(logout_response.status_code, 200)
            self.assertFalse(logout_response.json()["authenticated"])
            self.assertEqual(client.get("/api/reports").status_code, 401)

            old_login_response = client.post(
                "/api/auth/login",
                json={"email": "admin@example.com", "password": "AdminPass123"},
            )
            self.assertEqual(old_login_response.status_code, 401)

            new_login_response = client.post(
                "/api/auth/login",
                json={"email": "admin@example.com", "password": "AdminPass456"},
            )
            self.assertEqual(new_login_response.status_code, 200)

    def test_optional_mode_keeps_existing_routes_public_but_admin_routes_protected(self):
        self._write_report()

        with self._client(auth_enabled=True, auth_mode="optional") as client:
            self.assertEqual(client.get("/api/reports").status_code, 200)
            self.assertEqual(client.get("/api/admin/users").status_code, 401)

    def test_admin_routes_require_admin_role_and_support_user_crud(self):
        with self._client(auth_enabled=True, auth_mode="required") as admin_client:
            self._login(admin_client, "admin@example.com", "AdminPass123")

            create_response = admin_client.post(
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

            list_response = admin_client.get("/api/admin/users")
            self.assertEqual(list_response.status_code, 200)
            self.assertEqual(len(list_response.json()), 2)

            update_response = admin_client.put(
                f"/api/admin/users/{operator_id}",
                json={"display_name": "Operator Prime", "status": "disabled"},
            )
            self.assertEqual(update_response.status_code, 200)
            self.assertEqual(update_response.json()["display_name"], "Operator Prime")
            self.assertEqual(update_response.json()["status"], "disabled")

            reset_response = admin_client.post(
                f"/api/admin/users/{operator_id}/reset-password",
                json={"new_password": "ResetPass123", "must_change_password": True},
            )
            self.assertEqual(reset_response.status_code, 200)
            self.assertTrue(reset_response.json()["must_change_password"])

            reenable_response = admin_client.put(
                f"/api/admin/users/{operator_id}",
                json={"status": "active"},
            )
            self.assertEqual(reenable_response.status_code, 200)
            self.assertEqual(reenable_response.json()["status"], "active")

        with self._client(auth_enabled=True, auth_mode="required") as operator_client:
            login_response = operator_client.post(
                "/api/auth/login",
                json={"email": "operator@example.com", "password": "ResetPass123"},
            )
            self.assertEqual(login_response.status_code, 200, login_response.text)
            self.assertEqual(operator_client.get("/api/admin/users").status_code, 403)

        with self._client(auth_enabled=True, auth_mode="required") as admin_client:
            self._login(admin_client, "admin@example.com", "AdminPass123")
            delete_response = admin_client.delete(f"/api/admin/users/{operator_id}")
            self.assertEqual(delete_response.status_code, 200)
            self.assertEqual(delete_response.json()["user_id"], operator_id)

    def test_screener_tasks_require_operator_role_and_scope_to_owner(self):
        with self._client(auth_enabled=True, auth_mode="required") as admin_client:
            self._login(admin_client, "admin@example.com", "AdminPass123")
            operator_user = self._create_user(
                admin_client,
                email="operator.one@example.com",
                display_name="Operator One",
                password="OperatorPass123",
                role="operator",
            )
            self._create_user(
                admin_client,
                email="operator.two@example.com",
                display_name="Operator Two",
                password="OperatorPass123",
                role="operator",
            )
            self._create_user(
                admin_client,
                email="viewer@example.com",
                display_name="Viewer User",
                password="ViewerPass123",
                role="viewer",
            )

        with self._client(auth_enabled=True, auth_mode="required") as operator_client:
            self._login(operator_client, "operator.one@example.com", "OperatorPass123")
            with patch("web.backend.main._start_screener_task_thread") as start_task_thread:
                create_response = operator_client.post(
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
            task_response = operator_client.get(f"/api/screener/tasks/{task_id}")
            self.assertEqual(task_response.status_code, 200, task_response.text)
            self.assertEqual(task_response.json()["owner_user_id"], operator_user["id"])

            list_response = operator_client.get("/api/screener/tasks")
            self.assertEqual(list_response.status_code, 200, list_response.text)
            self.assertEqual([row["id"] for row in list_response.json()], [task_id])

            snapshot_path = (
                backend_main.SCREENER_RESULTS_DIR
                / backend_main.SCREENER_TASKS_STATE_DIRNAME
                / backend_main.ACTIVE_TASKS_DIRNAME
                / task_id
                / "task.json"
            )
            snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot_payload["owner_user_id"], operator_user["id"])

        with self._client(auth_enabled=True, auth_mode="required") as other_operator_client:
            self._login(other_operator_client, "operator.two@example.com", "OperatorPass123")
            list_response = other_operator_client.get("/api/screener/tasks")
            self.assertEqual(list_response.status_code, 200, list_response.text)
            self.assertEqual(list_response.json(), [])
            self.assertEqual(
                other_operator_client.get(f"/api/screener/tasks/{task_id}").status_code,
                404,
            )

        with self._client(auth_enabled=True, auth_mode="required") as viewer_client:
            self._login(viewer_client, "viewer@example.com", "ViewerPass123")
            self.assertEqual(viewer_client.get("/api/screener/tasks").status_code, 403)

        with self._client(auth_enabled=True, auth_mode="required") as admin_client:
            self._login(admin_client, "admin@example.com", "AdminPass123")
            list_response = admin_client.get("/api/screener/tasks")
            self.assertEqual(list_response.status_code, 200, list_response.text)
            self.assertEqual([row["id"] for row in list_response.json()], [task_id])

    def test_screener_runs_require_operator_role_and_scope_to_owner(self):
        with self._client(auth_enabled=True, auth_mode="required") as admin_client:
            self._login(admin_client, "admin@example.com", "AdminPass123")
            operator_one = self._create_user(
                admin_client,
                email="operator.one@example.com",
                display_name="Operator One",
                password="OperatorPass123",
                role="operator",
            )
            operator_two = self._create_user(
                admin_client,
                email="operator.two@example.com",
                display_name="Operator Two",
                password="OperatorPass123",
                role="operator",
            )
            self._create_user(
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
                    as_of_date="2026-03-24",
                    markets=["us"],
                    candidate_count=1,
                    generated_at="20260325_214530",
                    storage_path="20260325_214530",
                    artifact_manifest={
                        "run_meta": "20260325_214530/run_meta.json",
                        "candidates": "20260325_214530/candidates.csv",
                    },
                )

        with self._client(auth_enabled=True, auth_mode="required") as operator_client:
            self._login(operator_client, "operator.one@example.com", "OperatorPass123")

            list_response = operator_client.get("/api/screener/runs")
            self.assertEqual(list_response.status_code, 200, list_response.text)
            self.assertEqual([row["id"] for row in list_response.json()], ["20260324_214530"])

            detail_response = operator_client.get("/api/screener/runs/20260324_214530")
            self.assertEqual(detail_response.status_code, 200, detail_response.text)
            self.assertEqual(detail_response.json()["artifact_paths"]["candidates"], "20260324_214530/candidates.csv")
            self.assertEqual(detail_response.json()["filtered_count_by_reason"], {"liquidity_floor": 2})

            candidates_response = operator_client.get("/api/screener/runs/20260324_214530/candidates")
            self.assertEqual(candidates_response.status_code, 200, candidates_response.text)
            self.assertEqual(candidates_response.json()[0]["symbol"], "600519.SH")

            self.assertEqual(operator_client.get("/api/screener/runs/20260325_214530").status_code, 404)
            self.assertEqual(
                operator_client.get("/api/screener/runs/20260325_214530/candidates").status_code,
                404,
            )

        with self._client(auth_enabled=True, auth_mode="required") as viewer_client:
            self._login(viewer_client, "viewer@example.com", "ViewerPass123")
            self.assertEqual(viewer_client.get("/api/screener/runs").status_code, 403)

        with self._client(auth_enabled=True, auth_mode="required") as admin_client:
            self._login(admin_client, "admin@example.com", "AdminPass123")
            list_response = admin_client.get("/api/screener/runs")
            self.assertEqual(list_response.status_code, 200, list_response.text)
            self.assertEqual(
                [row["id"] for row in list_response.json()],
                ["20260325_214530", "20260324_214530"],
            )


if __name__ == "__main__":
    unittest.main()
