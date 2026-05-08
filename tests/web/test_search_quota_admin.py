import asyncio
import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

from tests.web.auth_helpers import AuthClientMixin
from tests.web.http_harness import app_client
from web.backend import auth, search_quota
from web.backend.main import app


class SearchQuotaAdminApiTests(AuthClientMixin, unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_url = f"sqlite+pysqlite:///{Path(self.temp_dir.name) / 'auth.db'}"
        auth.reset_runtime_state()

    def tearDown(self):
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
        with patch.dict(os.environ, env, clear=False):
            auth.reset_runtime_state()
            auth.create_all_for_testing()
            async with app_client(app) as client:
                yield client
            auth.reset_runtime_state()

    def test_admin_search_quota_endpoints_manage_config_and_usage(self):
        async def scenario():
            async with self._client() as client:
                await self._login(
                    client,
                    "admin@example.com",
                    "AdminPass123",
                    new_password="AdminPass124",
                )

                list_response = await client.get("/api/admin/search-quota")
                self.assertEqual(list_response.status_code, 200, list_response.text)
                payload = list_response.json()
                self.assertFalse(payload["global"]["enabled"])
                self.assertEqual(
                    [provider["provider"] for provider in payload["providers"]],
                    ["brave", "tavily", "bocha"],
                )

                global_response = await client.put(
                    "/api/admin/search-quota/global",
                    json={"enabled": True},
                )
                self.assertEqual(global_response.status_code, 200, global_response.text)
                self.assertTrue(global_response.json()["global"]["enabled"])

                provider_response = await client.put(
                    "/api/admin/search-quota/providers/brave",
                    json={
                        "enabled": True,
                        "monthly_free_quota": 10,
                        "monthly_hard_cap": 8,
                    },
                )
                self.assertEqual(provider_response.status_code, 200, provider_response.text)
                provider = provider_response.json()["provider"]
                self.assertTrue(provider["enabled"])
                self.assertEqual(provider["monthly_free_quota"], 10)
                self.assertEqual(provider["monthly_hard_cap"], 8)

                with auth.db_session() as db:
                    search_quota.record_search_provider_call(
                        db,
                        "brave",
                        success=True,
                    )
                    search_quota.disable_provider_until_month_end(
                        db,
                        "brave",
                        "temporary_disable",
                    )

                reactivate_response = await client.post(
                    "/api/admin/search-quota/providers/brave/reactivate"
                )
                self.assertEqual(reactivate_response.status_code, 200, reactivate_response.text)
                self.assertTrue(reactivate_response.json()["provider"]["enabled"])

                reset_response = await client.post(
                    "/api/admin/search-quota/providers/brave/usage/reset"
                )
                self.assertEqual(reset_response.status_code, 200, reset_response.text)
                self.assertEqual(reset_response.json()["reset_count"], 1)

        asyncio.run(scenario())

    def test_admin_search_quota_rejects_invalid_provider_and_hard_cap(self):
        async def scenario():
            async with self._client() as client:
                await self._login(
                    client,
                    "admin@example.com",
                    "AdminPass123",
                    new_password="AdminPass124",
                )

                invalid_provider = await client.put(
                    "/api/admin/search-quota/providers/unknown",
                    json={"enabled": True},
                )
                self.assertEqual(invalid_provider.status_code, 400)

                invalid_cap = await client.put(
                    "/api/admin/search-quota/providers/brave",
                    json={
                        "enabled": True,
                        "monthly_free_quota": 5,
                        "monthly_hard_cap": 6,
                    },
                )
                self.assertEqual(invalid_cap.status_code, 400)

        asyncio.run(scenario())

    def test_admin_search_quota_requires_admin_settings_permission(self):
        async def scenario():
            async with self._client() as client:
                with auth.db_session() as db:
                    auth.create_user(
                        db,
                        email="viewer@example.com",
                        display_name="Viewer",
                        password="ViewerPass123",
                        role=auth.UserRole.VIEWER.value,
                        must_change_password=False,
                    )

                await self._login(client, "viewer@example.com", "ViewerPass123")

                response = await client.get("/api/admin/search-quota")
                self.assertEqual(response.status_code, 403)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
