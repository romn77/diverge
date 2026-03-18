import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class WebStartScriptTests(unittest.TestCase):
    def test_start_script_supports_configurable_frontend_and_backend_ports(self):
        script = PROJECT_ROOT / "web" / "start.sh"
        self.assertTrue(script.is_file())

        source = script.read_text(encoding="utf-8")

        self.assertIn('BACKEND_PORT="${BACKEND_PORT:-8000}"', source)
        self.assertIn('FRONTEND_PORT="${FRONTEND_PORT:-3000}"', source)
        self.assertIn('FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-http://localhost:${FRONTEND_PORT}}"', source)
        self.assertIn('NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:${BACKEND_PORT}}"', source)
        self.assertIn('lsof -ti :"$port"', source)
        self.assertIn('kill_port "$BACKEND_PORT"', source)
        self.assertIn('kill_port "$FRONTEND_PORT"', source)
        self.assertIn('uvicorn main:app --port "$BACKEND_PORT"', source)
        self.assertIn('npm run dev -- --port "$FRONTEND_PORT"', source)
        self.assertIn('wait_for_http "http://localhost:${BACKEND_PORT}/api/reports"', source)
        self.assertIn('wait_for_http "http://localhost:${FRONTEND_PORT}"', source)


if __name__ == "__main__":
    unittest.main()
