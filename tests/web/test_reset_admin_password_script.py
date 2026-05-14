import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from web.backend import auth


class ResetAdminPasswordScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "auth.db"
        self.env = {
            "AUTH_ENABLED": "true",
            "AUTH_MODE": "required",
            "DATABASE_URL": f"sqlite+pysqlite:///{self.database_path}",
            "AUTH_BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
            "AUTH_BOOTSTRAP_ADMIN_USERNAME": "admin",
            "AUTH_BOOTSTRAP_ADMIN_PASSWORD": "NewPass123",
            "AUTH_BOOTSTRAP_ADMIN_DISPLAY_NAME": "Administrator",
        }
        auth.reset_runtime_state()

    def tearDown(self):
        auth.reset_runtime_state()
        self.temp_dir.cleanup()

    def _load_module(self):
        try:
            from web.backend.devops import reset_admin_password
        except ImportError as exc:
            self.fail(
                f"Expected web.backend.devops.reset_admin_password module to exist: {exc}"
            )
        return reset_admin_password

    def test_reset_script_resets_existing_bootstrap_admin_password(self):
        stream = io.StringIO()
        reset_admin_password = self._load_module()

        with patch.dict(os.environ, self.env, clear=False):
            auth.create_all_for_testing()
            with auth.db_session() as db:
                user = auth.create_user(
                    db,
                    email="admin@example.com",
                    display_name="Administrator",
                    password="OldPass123",
                    role=auth.UserRole.ADMIN.value,
                    status=auth.UserStatus.ACTIVE.value,
                    must_change_password=True,
                )
                user_id = user.id

            result = reset_admin_password.run_admin_password_reset(stream=stream)

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.email, "admin@example.com")
            self.assertFalse(result.must_change_password)

            with auth.db_session() as db:
                updated_user = auth.get_user_by_id(db, user_id)
                self.assertEqual(updated_user.username, "admin")
                self.assertTrue(
                    auth.verify_password(updated_user.password_hash, "NewPass123")
                )
                self.assertFalse(updated_user.must_change_password)

        output = stream.getvalue()
        self.assertIn("Password reset for admin@example.com", output)

    def test_reset_script_requires_existing_user(self):
        stream = io.StringIO()
        reset_admin_password = self._load_module()

        with patch.dict(os.environ, self.env, clear=False):
            auth.create_all_for_testing()
            result = reset_admin_password.run_admin_password_reset(stream=stream)

        self.assertEqual(result.exit_code, 1)
        self.assertIn("User not found: admin@example.com", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
