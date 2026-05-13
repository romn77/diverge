import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class SingleHostDeploymentFilesTests(unittest.TestCase):
    def test_backend_dockerfile_exists_with_full_project_copy_and_uvicorn_entrypoint(
        self,
    ):
        dockerfile = PROJECT_ROOT / "web" / "backend" / "Dockerfile"
        self.assertTrue(dockerfile.is_file())

        source = dockerfile.read_text(encoding="utf-8")
        self.assertIn("FROM python:3.13-slim", source)
        self.assertIn("COPY . .", source)
        self.assertIn("COPY pyproject.toml uv.lock README.md", source)
        self.assertIn("requirements.txt", source)
        self.assertIn("web/backend/requirements.txt", source)
        self.assertIn("pip install --no-cache-dir uv", source)
        self.assertIn("uv sync --frozen --no-dev --extra web", source)
        self.assertIn('CMD ["uvicorn", "web.backend.main:app"', source)

    def test_frontend_dockerfile_exists_with_build_arg_for_api_base_url(self):
        dockerfile = PROJECT_ROOT / "web" / "frontend" / "Dockerfile"
        self.assertTrue(dockerfile.is_file())

        source = dockerfile.read_text(encoding="utf-8")
        self.assertIn("ARG NEXT_PUBLIC_API_BASE_URL", source)
        self.assertIn('CMD ["npm", "start"]', source)

    def test_compose_file_uses_frontend_port_variable_and_mounts_data_root(self):
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        self.assertTrue(compose_file.is_file())

        source = compose_file.read_text(encoding="utf-8")
        self.assertIn("postgres:16-alpine", source)
        self.assertIn("${POSTGRES_PORT:-5432}:5432", source)
        self.assertIn("postgres-data:/var/lib/postgresql/data", source)
        self.assertIn("${FRONTEND_PORT:-3000}:3000", source)
        self.assertIn("./data:/app/data", source)
        self.assertIn("./.env:/app/.env:ro", source)
        self.assertIn("DATA_DIR: /app/data", source)
        self.assertNotIn("REPORTS_DIR: /app/data/reports", source)
        self.assertNotIn("SCREENER_RUNS_DIR: /app/data/screener/runs", source)
        self.assertIn("FRONTEND_ORIGIN", source)
        self.assertIn("AUTH_ENABLED: ${AUTH_ENABLED:-true}", source)
        self.assertIn("AUTH_MODE", source)
        self.assertIn(
            "TASK_GLOBAL_RUNNING_LIMIT: ${TASK_GLOBAL_RUNNING_LIMIT:-2}", source
        )
        self.assertIn(
            "TASK_USER_PENDING_LIMIT_OPERATOR: ${TASK_USER_PENDING_LIMIT_OPERATOR:-5}",
            source,
        )
        self.assertIn(
            "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}",
            source,
        )
        self.assertIn("DATABASE_URL: ${DATABASE_URL:?Set DATABASE_URL in .env}", source)
        self.assertIn(
            "AUTH_BOOTSTRAP_ADMIN_EMAIL: ${AUTH_BOOTSTRAP_ADMIN_EMAIL:?Set AUTH_BOOTSTRAP_ADMIN_EMAIL in .env}",
            source,
        )
        self.assertIn(
            "AUTH_BOOTSTRAP_ADMIN_PASSWORD: ${AUTH_BOOTSTRAP_ADMIN_PASSWORD:?Set AUTH_BOOTSTRAP_ADMIN_PASSWORD in .env}",
            source,
        )
        self.assertIn("alembic -c web/backend/alembic.ini upgrade head", source)
        self.assertIn("python -m web.backend.devops.bootstrap_admin", source)
        self.assertNotIn("cd /app/web/backend", source)

    def test_prod_compose_adds_nginx_redis_worker_and_backup_without_public_datastores(
        self,
    ):
        compose_file = PROJECT_ROOT / "compose.prod.yml"
        self.assertTrue(compose_file.is_file())

        source = compose_file.read_text(encoding="utf-8")
        self.assertIn("nginx:", source)
        self.assertIn("redis:", source)
        self.assertIn("worker:", source)
        self.assertIn("prewarm-scheduler:", source)
        self.assertIn("prewarm-worker:", source)
        self.assertIn("backup:", source)
        self.assertIn("${HTTP_PORT:-80}:80", source)
        self.assertIn("${HTTPS_PORT:-443}:443", source)
        self.assertIn("127.0.0.1:${POSTGRES_PORT:-5432}:5432", source)
        self.assertIn("127.0.0.1:${REDIS_PORT:-6379}:6379", source)
        self.assertNotIn('      - "${POSTGRES_PORT:-5432}:5432"', source)
        self.assertNotIn('      - "${REDIS_PORT:-6379}:6379"', source)
        self.assertIn("TASK_BACKEND: redis", source)
        self.assertIn(
            'command: ["arq", "web.backend.runtime.prewarm_arq.PrewarmSchedulerSettings"]',
            source,
        )
        self.assertIn(
            'command: ["arq", "web.backend.runtime.prewarm_arq.PrewarmWorkerSettings"]',
            source,
        )
        self.assertIn("PREWARM_CN_READY_TIME: ${PREWARM_CN_READY_TIME:-18:10}", source)
        self.assertNotIn("SCREENER_PREWARM_ENABLED", source)
        self.assertIn(
            "TASK_GLOBAL_RUNNING_LIMIT: ${TASK_GLOBAL_RUNNING_LIMIT:-2}", source
        )
        self.assertIn("TASK_USER_RUNNING_LIMIT: ${TASK_USER_RUNNING_LIMIT:-1}", source)
        self.assertIn(
            "TASK_GLOBAL_PENDING_LIMIT: ${TASK_GLOBAL_PENDING_LIMIT:-100}", source
        )
        self.assertIn("STORAGE_BACKEND: ${STORAGE_BACKEND:-tencent_cos}", source)
        self.assertIn("SESSION_COOKIE_SECURE: ${SESSION_COOKIE_SECURE:-true}", source)

    def test_no_nginx_compose_supports_public_ip_http_deployment(self):
        compose_file = PROJECT_ROOT / "compose.no-nginx.yml"
        self.assertTrue(compose_file.is_file())

        source = compose_file.read_text(encoding="utf-8")
        self.assertNotIn("nginx:", source)
        self.assertIn("redis:", source)
        self.assertIn("worker:", source)
        self.assertIn("prewarm-scheduler:", source)
        self.assertIn("prewarm-worker:", source)
        self.assertIn("backup:", source)
        self.assertIn("${BACKEND_PORT:-8000}:8000", source)
        self.assertIn("${FRONTEND_PORT:-3000}:3000", source)
        self.assertIn("127.0.0.1:${POSTGRES_PORT:-5432}:5432", source)
        self.assertIn("127.0.0.1:${REDIS_PORT:-6379}:6379", source)
        self.assertNotIn('      - "${POSTGRES_PORT:-5432}:5432"', source)
        self.assertNotIn('      - "${REDIS_PORT:-6379}:6379"', source)
        self.assertIn(
            "FRONTEND_ORIGIN: ${FRONTEND_ORIGIN:?Set FRONTEND_ORIGIN in .env}", source
        )
        self.assertIn(
            'command: ["arq", "web.backend.runtime.prewarm_arq.PrewarmSchedulerSettings"]',
            source,
        )
        self.assertIn(
            'command: ["arq", "web.backend.runtime.prewarm_arq.PrewarmWorkerSettings"]',
            source,
        )
        self.assertNotIn("SCREENER_PREWARM_ENABLED", source)
        self.assertIn(
            "NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL:?Set NEXT_PUBLIC_API_BASE_URL in .env}",
            source,
        )
        self.assertIn("SESSION_COOKIE_SECURE: ${SESSION_COOKIE_SECURE:-false}", source)
        self.assertIn(
            "TASK_USER_PENDING_LIMIT_VIEWER: ${TASK_USER_PENDING_LIMIT_VIEWER:-2}",
            source,
        )

    def test_nginx_production_config_routes_frontend_api_and_sse(self):
        nginx_config = PROJECT_ROOT / "deploy" / "nginx" / "diverge.conf"
        self.assertTrue(nginx_config.is_file())

        source = nginx_config.read_text(encoding="utf-8")
        self.assertIn("proxy_pass http://backend:8000", source)
        self.assertIn("proxy_pass http://frontend:3000", source)
        self.assertIn("proxy_read_timeout 3600s", source)
        self.assertIn("text/event-stream", source)
        self.assertIn("ssl_certificate", source)

    def test_env_example_documents_frontend_port_and_origin(self):
        env_example = PROJECT_ROOT / ".env.example"
        source = env_example.read_text(encoding="utf-8")

        self.assertIn("FRONTEND_PORT=3000", source)
        self.assertIn("FRONTEND_ORIGIN=http://localhost:3000", source)
        self.assertIn("NEXT_PUBLIC_API_BASE_URL=http://localhost:8000", source)
        self.assertIn("DATA_DIR=./data", source)
        self.assertNotIn("DIVERGE_EVAL_RESULTS_DIR=./data/eval_results", source)
        self.assertNotIn("STORAGE_LOCAL_ROOT=./data", source)
        self.assertIn("POSTGRES_PASSWORD=", source)
        self.assertIn("AUTH_ENABLED=true", source)
        self.assertIn("AUTH_MODE=required", source)
        self.assertIn("DATABASE_URL=", source)
        self.assertIn("AUTH_BOOTSTRAP_ADMIN_EMAIL=", source)
        self.assertIn("AUTH_BOOTSTRAP_ADMIN_PASSWORD=", source)
        self.assertIn("TASK_GLOBAL_RUNNING_LIMIT=2", source)
        self.assertIn("TASK_USER_RUNNING_LIMIT=1", source)
        self.assertIn("TASK_GLOBAL_PENDING_LIMIT=100", source)
        self.assertIn("TASK_USER_PENDING_LIMIT_VIEWER=2", source)

    def test_deploy_script_exists_with_docker_compose_commands(self):
        deploy_script = PROJECT_ROOT / "scripts" / "deploy-single-host.sh"
        self.assertTrue(deploy_script.is_file())

        source = deploy_script.read_text(encoding="utf-8")
        self.assertIn('DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data}"', source)
        self.assertIn('mkdir -p "$DATA_DIR/reports" "$DATA_DIR/manifest"', source)
        self.assertLess(
            source.index('source "$ENV_FILE"'),
            source.index('DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data}"'),
        )
        self.assertLess(
            source.index('DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data}"'),
            source.index('mkdir -p "$DATA_DIR/reports" "$DATA_DIR/manifest"'),
        )
        self.assertNotIn("$PROJECT_ROOT/reports", source)
        self.assertIn("docker compose build", source)
        self.assertIn("docker compose up -d", source)
        self.assertIn("mkdir -p", source)

    def test_offline_image_script_builds_amd64_tarball_and_compose_override(self):
        script = PROJECT_ROOT / "scripts" / "build-offline-images.sh"
        self.assertTrue(script.is_file())

        source = script.read_text(encoding="utf-8")
        self.assertIn('PLATFORM="${PLATFORM:-linux/amd64}"', source)
        self.assertIn('BACKEND_IMAGE="${BACKEND_IMAGE:-diverge-backend}"', source)
        self.assertIn('FRONTEND_IMAGE="${FRONTEND_IMAGE:-diverge-frontend}"', source)
        self.assertIn("docker buildx build", source)
        self.assertIn("--load", source)
        self.assertIn("docker save", source)
        self.assertIn("${BACKEND_IMAGE}:${TAG}", source)
        self.assertIn("${FRONTEND_IMAGE}:${TAG}", source)
        self.assertIn("compose.images-${TAG}.yml", source)

    def test_offline_image_script_prefers_explicit_api_base_url_over_env_file(self):
        script = PROJECT_ROOT / "scripts" / "build-offline-images.sh"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            docker_log = tmp_path / "docker.log"
            fake_docker = fake_bin / "docker"
            fake_docker.write_text(
                """#!/bin/bash
set -euo pipefail
printf '%s\\n' "$*" >> "$DOCKER_LOG"
if [ "${1:-}" = "buildx" ] && [ "${2:-}" = "version" ]; then
  exit 0
fi
if [ "${1:-}" = "buildx" ] && [ "${2:-}" = "build" ]; then
  exit 0
fi
if [ "${1:-}" = "save" ]; then
  printf 'fake image archive'
  exit 0
fi
if [ "${1:-}" = "pull" ]; then
  exit 0
fi
exit 1
""",
                encoding="utf-8",
            )
            fake_docker.chmod(0o755)
            env_file = tmp_path / ".env"
            env_file.write_text(
                "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000\n"
                "PUBLIC_HOSTNAME=example.com\n",
                encoding="utf-8",
            )
            output_dir = tmp_path / "dist"

            env = os.environ.copy()
            env.update(
                {
                    "DOCKER_LOG": str(docker_log),
                    "ENV_FILE": str(env_file),
                    "NEXT_PUBLIC_API_BASE_URL": "http://124.222.28.71:8000",
                    "OUTPUT_DIR": str(output_dir),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                    "TAG": "explicit-api-test",
                }
            )

            result = subprocess.run(
                [str(script)],
                cwd=PROJECT_ROOT,
                env=env,
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            log = docker_log.read_text(encoding="utf-8")
            self.assertIn(
                "--build-arg NEXT_PUBLIC_API_BASE_URL=http://124.222.28.71:8000",
                log,
            )
            self.assertNotIn(
                "--build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8000",
                log,
            )

    def test_dockerignore_excludes_env_and_data_artifacts(self):
        dockerignore = PROJECT_ROOT / ".dockerignore"
        self.assertTrue(dockerignore.is_file())

        source = dockerignore.read_text(encoding="utf-8")
        self.assertIn(".env", source)
        self.assertIn("data", source)
        self.assertIn(".venv", source)


if __name__ == "__main__":
    unittest.main()
