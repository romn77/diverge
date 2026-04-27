import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.web.auth_helpers import AuthClientMixin
from tests.web.http_harness import app_client
from web.backend import audit, auth
from web.backend.main import app


class AuditBackendTests(AuthClientMixin, unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_url = f"sqlite+pysqlite:///{Path(self.temp_dir.name) / 'auth.db'}"
        self.env_patcher = patch.dict(
            "os.environ",
            {
                "AUTH_ENABLED": "true",
                "AUTH_MODE": "required",
                "DATABASE_URL": self.database_url,
                "SESSION_COOKIE_NAME": "test_session",
                "SESSION_COOKIE_SECURE": "false",
                "SESSION_COOKIE_SAMESITE": "lax",
            },
            clear=False,
        )
        self.env_patcher.start()
        auth.reset_runtime_state()
        auth.create_all_for_testing()

        with auth.db_session() as db:
            self.admin = auth.create_user(
                db,
                email="admin@example.com",
                display_name="Admin",
                password="admin-password",
                role=auth.UserRole.ADMIN,
                must_change_password=False,
            )
            other_tenant = auth.create_tenant(db, name="Other Tenant", slug="other-tenant")
            self.other_admin = auth.create_user(
                db,
                email="other-admin@example.com",
                display_name="Other Admin",
                password="other-password",
                role=auth.UserRole.ADMIN,
                must_change_password=False,
                tenant_id=other_tenant.id,
            )
            self.admin_id = self.admin.id
            self.admin_tenant_id = self.admin.tenant_id
            self.other_admin_id = self.other_admin.id
            self.other_tenant_id = other_tenant.id

    def tearDown(self):
        self.env_patcher.stop()
        auth.reset_runtime_state()
        self.temp_dir.cleanup()

    def test_record_audit_event_persists_safe_metadata(self):
        with auth.db_session() as db:
            event = audit.record_audit_event(
                db,
                tenant_id=self.admin_tenant_id,
                actor_user_id=self.admin_id,
                action="admin.user.created",
                resource_type="user",
                resource_id="target-user",
                metadata={"role": "operator", "password": "secret"},
            )

        self.assertEqual(event.action, "admin.user.created")
        self.assertEqual(event.tenant_id, self.admin_tenant_id)
        self.assertNotIn("password", event.metadata_json)

    def test_admin_audit_events_are_tenant_scoped(self):
        async def scenario():
            with auth.db_session() as db:
                audit.record_audit_event(
                    db,
                    tenant_id=self.admin_tenant_id,
                    actor_user_id=self.admin_id,
                    action="audit.scope.probe",
                    resource_type="probe",
                    resource_id="default-session",
                )
                audit.record_audit_event(
                    db,
                    tenant_id=self.other_tenant_id,
                    actor_user_id=self.other_admin_id,
                    action="audit.scope.probe",
                    resource_type="probe",
                    resource_id="other-session",
                )

            async with app_client(app) as client:
                await self._login(client, "admin@example.com", "admin-password")
                response = await client.get(
                    "/api/admin/audit-events",
                    params={"action": "audit.scope.probe"},
                )
                self.assertEqual(response.status_code, 200, response.text)
                payload = response.json()

            self.assertEqual([row["resource_id"] for row in payload["events"]], ["default-session"])
            self.assertEqual(payload["events"][0]["tenant_id"], self.admin_tenant_id)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
