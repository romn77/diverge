import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class SingleHostDeploymentFilesTests(unittest.TestCase):
    def test_backend_dockerfile_exists_with_full_project_copy_and_uvicorn_entrypoint(self):
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
        self.assertIn('${FRONTEND_PORT:-3000}:3000', source)
        self.assertIn("./data:/app/data", source)
        self.assertIn("./.env:/app/.env:ro", source)
        self.assertIn("REPORTS_DIR: /app/data/reports", source)
        self.assertIn("SCREENER_RUNS_DIR: /app/data/screener/runs", source)
        self.assertIn("FRONTEND_ORIGIN", source)
        self.assertIn("AUTH_ENABLED: ${AUTH_ENABLED:-true}", source)
        self.assertIn("AUTH_MODE", source)
        self.assertIn("POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}", source)
        self.assertIn("DATABASE_URL: ${DATABASE_URL:?Set DATABASE_URL in .env}", source)
        self.assertIn(
            "AUTH_BOOTSTRAP_ADMIN_EMAIL: ${AUTH_BOOTSTRAP_ADMIN_EMAIL:?Set AUTH_BOOTSTRAP_ADMIN_EMAIL in .env}",
            source,
        )
        self.assertIn(
            "AUTH_BOOTSTRAP_ADMIN_PASSWORD: ${AUTH_BOOTSTRAP_ADMIN_PASSWORD:?Set AUTH_BOOTSTRAP_ADMIN_PASSWORD in .env}",
            source,
        )
        self.assertIn("alembic -c alembic.ini upgrade head", source)
        self.assertIn("python -m web.backend.bootstrap_admin", source)

    def test_env_example_documents_frontend_port_and_origin(self):
        env_example = PROJECT_ROOT / ".env.example"
        source = env_example.read_text(encoding="utf-8")

        self.assertIn("FRONTEND_PORT=3000", source)
        self.assertIn("FRONTEND_ORIGIN=http://localhost:3000", source)
        self.assertIn("NEXT_PUBLIC_API_BASE_URL=http://localhost:8000", source)
        self.assertIn("TRADINGAGENTS_EVAL_RESULTS_DIR=./data/eval_results", source)
        self.assertIn("POSTGRES_PASSWORD=", source)
        self.assertIn("AUTH_ENABLED=true", source)
        self.assertIn("AUTH_MODE=required", source)
        self.assertIn("DATABASE_URL=", source)
        self.assertIn("AUTH_BOOTSTRAP_ADMIN_EMAIL=", source)
        self.assertIn("AUTH_BOOTSTRAP_ADMIN_PASSWORD=", source)

    def test_deploy_script_exists_with_docker_compose_commands(self):
        deploy_script = PROJECT_ROOT / "scripts" / "deploy-single-host.sh"
        self.assertTrue(deploy_script.is_file())

        source = deploy_script.read_text(encoding="utf-8")
        self.assertIn("docker compose build", source)
        self.assertIn("docker compose up -d", source)
        self.assertIn("mkdir -p", source)

    def test_dockerignore_excludes_env_and_data_artifacts(self):
        dockerignore = PROJECT_ROOT / ".dockerignore"
        self.assertTrue(dockerignore.is_file())

        source = dockerignore.read_text(encoding="utf-8")
        self.assertIn(".env", source)
        self.assertIn("data", source)
        self.assertIn(".venv", source)


if __name__ == "__main__":
    unittest.main()
