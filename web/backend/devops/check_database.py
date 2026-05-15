from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from web.backend import auth


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"

REQUIRED_TABLES = (
    "tenants",
    "users",
    "auth_sessions",
    "user_permissions",
    "audit_events",
    "trade_entries",
    "screener_runs",
    "report_runs",
    "report_files",
    "asset_accounts",
    "asset_positions",
    "asset_valuation_snapshots",
    "analysis_role_limits",
    "analysis_task_usage",
    "data_source_vendor_configs",
    "data_source_route_policies",
    "data_source_usage",
    "llm_provider_configs",
    "llm_model_configs",
    "llm_model_profiles",
    "llm_model_profile_routes",
    "llm_module_settings",
    "llm_ui_settings",
    "llm_model_usage",
    "search_global_configs",
    "search_provider_configs",
    "search_provider_usage",
    "opportunity_runs",
    "backtest_runs",
    "watchlist_items",
    "job_records",
)


@dataclass(frozen=True)
class DatabaseCheckResult:
    exit_code: int
    auth_enabled: bool
    current_heads: tuple[str, ...] = ()
    script_heads: tuple[str, ...] = ()
    missing_tables: tuple[str, ...] = ()
    upgraded: bool = False


def load_env_file(path: Path, *, override: bool = False) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_env_value(value.strip())
        if not key or (not override and key in os.environ):
            continue
        os.environ[key] = value


def run_database_check(
    *,
    upgrade: bool = False,
    bootstrap_admin: bool = False,
    backfill: bool = False,
    stream: TextIO | None = None,
) -> DatabaseCheckResult:
    output = stream or sys.stdout
    settings = auth.get_auth_settings()
    print(
        f"Auth: {'enabled' if settings.enabled else 'disabled'} mode={settings.mode}",
        file=output,
    )

    if not settings.enabled:
        print(
            "Database: skipped because AUTH_ENABLED is false or AUTH_MODE is disabled",
            file=output,
        )
        return DatabaseCheckResult(exit_code=0, auth_enabled=False)

    if not settings.database_url:
        print("Database: failed because DATABASE_URL is not set", file=output)
        return DatabaseCheckResult(exit_code=1, auth_enabled=True)

    print(f"Database URL: {_mask_database_url(settings.database_url)}", file=output)

    config = _alembic_config()
    script_heads = _script_heads(config)

    if upgrade:
        print("Applying migrations: alembic upgrade head", file=output)
        command.upgrade(config, "head")

    engine = auth.get_engine(settings)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        current_heads = tuple(
            MigrationContext.configure(connection).get_current_heads()
        )
        existing_tables = set(inspect(connection).get_table_names())

    missing_tables = tuple(
        table for table in REQUIRED_TABLES if table not in existing_tables
    )
    schema_up_to_date = set(current_heads) == set(script_heads)

    print("Connection: ok", file=output)
    print(f"Alembic current: {_format_revisions(current_heads)}", file=output)
    print(f"Alembic head: {_format_revisions(script_heads)}", file=output)
    print(
        f"Schema: {'up to date' if schema_up_to_date else 'pending migrations'}",
        file=output,
    )
    if missing_tables:
        print(f"Missing tables: {', '.join(missing_tables)}", file=output)
    else:
        print("Required tables: ok", file=output)

    exit_code = 0 if schema_up_to_date and not missing_tables else 1

    if exit_code == 0 and bootstrap_admin:
        created = auth.bootstrap_admin_from_env()
        print(
            f"Bootstrap admin: {'created' if created else 'already present'}",
            file=output,
        )

    if exit_code == 0 and backfill:
        from web.backend.devops import backfill_metadata

        summary = backfill_metadata.backfill_all_metadata()
        print(
            "Backfill: "
            f"reports={summary.reports} "
            f"report_files={summary.report_files} "
            f"trades={summary.trades} "
            f"screener_runs={summary.screener_runs}",
            file=output,
        )

    return DatabaseCheckResult(
        exit_code=exit_code,
        auth_enabled=True,
        current_heads=current_heads,
        script_heads=script_heads,
        missing_tables=missing_tables,
        upgraded=upgrade,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check the Diverge auth database and optionally apply migrations."
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Apply Alembic migrations to head before verifying the schema.",
    )
    parser.add_argument(
        "--bootstrap-admin",
        action="store_true",
        help="Ensure the bootstrap admin user exists after the schema check passes.",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Backfill historical report, trade, and screener metadata after the schema check passes.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Environment file to load before checking the database.",
    )
    parser.add_argument(
        "--override-env",
        action="store_true",
        help="Let values from --env-file override existing process environment variables.",
    )
    args = parser.parse_args(argv)

    load_env_file(args.env_file, override=args.override_env)
    try:
        result = run_database_check(
            upgrade=args.upgrade,
            bootstrap_admin=args.bootstrap_admin,
            backfill=args.backfill,
        )
    except Exception as exc:  # pragma: no cover - shell-facing guard
        print(f"Database check failed: {exc}", file=sys.stderr)
        return 1
    return result.exit_code


def _alembic_config() -> Config:
    return Config(str(ALEMBIC_INI))


def _script_heads(config: Config) -> tuple[str, ...]:
    return tuple(ScriptDirectory.from_config(config).get_heads())


def _format_revisions(revisions: tuple[str, ...]) -> str:
    return ", ".join(revisions) if revisions else "<none>"


def _mask_database_url(database_url: str) -> str:
    try:
        return make_url(database_url).render_as_string(hide_password=True)
    except Exception:
        return "<invalid DATABASE_URL>"


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
