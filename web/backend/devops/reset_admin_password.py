from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from web.backend import auth
from web.backend.devops.check_database import DEFAULT_ENV_FILE, load_env_file


@dataclass(frozen=True)
class AdminPasswordResetResult:
    exit_code: int
    email: str | None = None
    must_change_password: bool = False


def run_admin_password_reset(
    *,
    must_change_password: bool = False,
    stream: TextIO | None = None,
) -> AdminPasswordResetResult:
    output = stream or sys.stdout
    settings = auth.get_auth_settings()

    if not settings.enabled:
        print("Auth is disabled; no admin password reset was needed.", file=output)
        return AdminPasswordResetResult(exit_code=0)

    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        print(
            "AUTH_BOOTSTRAP_ADMIN_EMAIL and AUTH_BOOTSTRAP_ADMIN_PASSWORD are required.",
            file=output,
        )
        return AdminPasswordResetResult(exit_code=1)

    with auth.db_session() as db:
        user = auth.get_user_by_email(db, settings.bootstrap_admin_email)
        if user is None:
            print(f"User not found: {settings.bootstrap_admin_email}", file=output)
            return AdminPasswordResetResult(
                exit_code=1, email=settings.bootstrap_admin_email
            )

        if settings.bootstrap_admin_username:
            auth.update_user(
                db,
                user.id,
                username=settings.bootstrap_admin_username,
            )
        updated_user = auth.reset_user_password(
            db,
            user.id,
            new_password=settings.bootstrap_admin_password,
            must_change_password=must_change_password,
        )
        email = updated_user.email
        reset_requires_change = updated_user.must_change_password

    print(f"Password reset for {email}", file=output)
    return AdminPasswordResetResult(
        exit_code=0,
        email=email,
        must_change_password=reset_requires_change,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reset the configured bootstrap admin password."
    )
    parser.add_argument(
        "--must-change-password",
        action="store_true",
        help="Require the admin to change the password after the reset.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Environment file to load before resetting the password.",
    )
    parser.add_argument(
        "--override-env",
        action="store_true",
        help="Let values from --env-file override existing process environment variables.",
    )
    args = parser.parse_args(argv)

    load_env_file(args.env_file, override=args.override_env)
    try:
        result = run_admin_password_reset(
            must_change_password=args.must_change_password
        )
    except Exception as exc:  # pragma: no cover - shell-facing guard
        print(f"Admin password reset failed: {exc}", file=sys.stderr)
        return 1
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
