from __future__ import annotations

import sys

from web.backend import auth


def main() -> int:
    try:
        created = auth.bootstrap_admin_from_env()
    except auth.AuthDisabledError:
        return 0
    except Exception as exc:  # pragma: no cover - exercised through shell invocation
        print(str(exc), file=sys.stderr)
        return 1

    if created:
        print("Bootstrap admin created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
