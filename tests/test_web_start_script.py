import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class WebStartScriptTests(unittest.TestCase):
    def test_start_script_supports_configurable_frontend_and_backend_ports(self):
        script = PROJECT_ROOT / "web" / "start.sh"
        self.assertTrue(script.is_file())

        source = script.read_text(encoding="utf-8")

        self.assertIn('ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"', source)
        self.assertIn('BACKEND_PORT="${BACKEND_PORT:-8000}"', source)
        self.assertIn('FRONTEND_PORT="${FRONTEND_PORT:-3000}"', source)
        self.assertIn('FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-http://localhost:${FRONTEND_PORT}}"', source)
        self.assertIn('NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:${BACKEND_PORT}}"', source)
        self.assertIn('AUTH_ENABLED="${AUTH_ENABLED:-false}"', source)
        self.assertIn('AUTH_MODE="${AUTH_MODE:-required}"', source)
        self.assertIn('lsof -ti :"$port"', source)
        self.assertIn('kill_port "$BACKEND_PORT"', source)
        self.assertIn('kill_port "$FRONTEND_PORT"', source)
        self.assertIn('alembic -c alembic.ini upgrade head', source)
        self.assertIn('python -m web.backend.devops.bootstrap_admin', source)
        self.assertIn('python -m web.backend.devops.backfill_metadata', source)
        self.assertIn('if [ "$AUTH_MODE" = "optional" ]; then', source)
        self.assertIn('cd "$ROOT_DIR"', source)
        self.assertIn('uvicorn web.backend.main:app --port "$BACKEND_PORT"', source)
        self.assertIn('npm run dev -- --port "$FRONTEND_PORT"', source)
        self.assertIn('wait_for_http "http://localhost:${BACKEND_PORT}/api/healthz"', source)
        self.assertIn('wait_for_http "http://localhost:${FRONTEND_PORT}"', source)

    def test_start_script_supports_redis_worker_mode(self):
        script = PROJECT_ROOT / "web" / "start.sh"
        source = script.read_text(encoding="utf-8")

        self.assertIn('TASK_BACKEND="${TASK_BACKEND:-local}"', source)
        self.assertIn('TASK_QUEUE_LIMIT="${TASK_QUEUE_LIMIT:-2}"', source)
        self.assertIn('TASK_GLOBAL_RUNNING_LIMIT="${TASK_GLOBAL_RUNNING_LIMIT:-$TASK_QUEUE_LIMIT}"', source)
        self.assertIn('TASK_USER_RUNNING_LIMIT="${TASK_USER_RUNNING_LIMIT:-1}"', source)
        self.assertIn('TASK_GLOBAL_PENDING_LIMIT="${TASK_GLOBAL_PENDING_LIMIT:-100}"', source)
        self.assertIn('TASK_USER_PENDING_LIMIT_OPERATOR="${TASK_USER_PENDING_LIMIT_OPERATOR:-5}"', source)
        self.assertIn('REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"', source)
        self.assertIn('WORKER_LOG="${WORKER_LOG:-/tmp/tradingagents-worker.log}"', source)
        self.assertIn('WORKER_PID=""', source)
        self.assertIn('ensure_redis_available() {', source)
        self.assertIn('if [ "$TASK_BACKEND" != "redis" ]; then', source)
        self.assertIn('START_REDIS_DOCKER="${START_REDIS_DOCKER:-false}"', source)
        self.assertIn('docker run -d --name "$REDIS_CONTAINER_NAME"', source)
        self.assertIn('export TASK_BACKEND="$TASK_BACKEND"', source)
        self.assertIn('export TASK_QUEUE_LIMIT="$TASK_QUEUE_LIMIT"', source)
        self.assertIn('export TASK_GLOBAL_RUNNING_LIMIT="$TASK_GLOBAL_RUNNING_LIMIT"', source)
        self.assertIn('export TASK_USER_RUNNING_LIMIT="$TASK_USER_RUNNING_LIMIT"', source)
        self.assertIn('export TASK_GLOBAL_PENDING_LIMIT="$TASK_GLOBAL_PENDING_LIMIT"', source)
        self.assertIn('export REDIS_URL="$REDIS_URL"', source)
        self.assertIn('python -m web.backend.worker', source)
        self.assertIn('WORKER_PID=$!', source)
        self.assertIn('Task backend: $TASK_BACKEND', source)
        self.assertIn('Running limits: global=$TASK_GLOBAL_RUNNING_LIMIT user=$TASK_USER_RUNNING_LIMIT', source)

    def test_start_script_cleans_up_when_auth_bootstrap_fails_before_backend_pid_exists(self):
        script = PROJECT_ROOT / "web" / "start.sh"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            temp_script = temp_root / "web" / "start.sh"
            temp_backend_dir = temp_root / "web" / "backend"
            temp_bin_dir = temp_root / "bin"
            temp_frontend_dir = temp_root / "web" / "frontend"

            temp_backend_dir.mkdir(parents=True)
            temp_frontend_dir.mkdir(parents=True)
            temp_bin_dir.mkdir(parents=True)
            shutil.copy(script, temp_script)
            (temp_root / ".env").write_text(
                "\n".join(
                    [
                        "AUTH_ENABLED=true",
                        "AUTH_MODE=required",
                        "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tradingagents",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (temp_backend_dir / "requirements.txt").write_text("", encoding="utf-8")
            (temp_bin_dir / "pip").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
            (temp_bin_dir / "alembic").write_text(
                "#!/bin/bash\n"
                "echo 'simulated alembic failure: postgres unavailable' >&2\n"
                "exit 1\n",
                encoding="utf-8",
            )
            os.chmod(temp_bin_dir / "pip", 0o755)
            os.chmod(temp_bin_dir / "alembic", 0o755)

            env = os.environ.copy()
            env["PATH"] = f"{temp_bin_dir}:{env['PATH']}"

            result = subprocess.run(
                ["bash", str(temp_script)],
                cwd=temp_root,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

        combined_output = f"{result.stdout}\n{result.stderr}"

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("simulated alembic failure: postgres unavailable", combined_output)
        self.assertNotIn("unbound variable", combined_output)
        self.assertIn("AUTH_ENABLED=false", combined_output)
        self.assertIn("Stopped.", combined_output)


if __name__ == "__main__":
    unittest.main()
