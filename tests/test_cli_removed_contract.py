import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_core_and_web_imports_do_not_depend_on_cli_package():
    script = """
import importlib
import sys

importlib.import_module("diverge.runner")
importlib.import_module("web.backend.services.config")

loaded = [name for name in sys.modules if name == "cli" or name.startswith("cli.")]
if loaded:
    raise SystemExit(f"cli modules loaded: {loaded}")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_project_no_longer_exposes_or_ships_cli_module():
    assert not (PROJECT_ROOT / "cli").exists()

    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'diverge = "cli.main:app"' not in pyproject
    assert '"typer' not in pyproject
    assert '"questionary' not in pyproject

    assert not (PROJECT_ROOT / "main.py").exists()
