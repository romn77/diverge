from __future__ import annotations

import argparse
from pathlib import Path

from web.backend import app_config, storage


def datasets() -> dict[str, Path]:
    return {
        "reports": app_config.REPORTS_DIR,
        "screener/runs": app_config.SCREENER_RESULTS_DIR,
        "history": app_config.STOCK_HISTORY_DIR,
        "cache/screener": app_config.SCREENER_CACHE_DIR,
    }


def migrate_dataset(name: str, source_dir: Path, *, dry_run: bool) -> list[str]:
    if not source_dir.is_dir():
        return []

    keys: list[str] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        key = f"{name}/{path.relative_to(source_dir).as_posix()}"
        keys.append(key)
        if not dry_run:
            storage.get_storage().put_bytes(key, path.read_bytes())
    return keys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate local data files into configured object storage."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--backfill-metadata",
        action="store_true",
        help="Run the existing Postgres metadata backfill after upload.",
    )
    args = parser.parse_args(argv)

    total = 0
    for name, source_dir in datasets().items():
        keys = migrate_dataset(name, source_dir, dry_run=args.dry_run)
        total += len(keys)
        print(f"{name}: {len(keys)} file(s)")
    if args.backfill_metadata and not args.dry_run:
        from web.backend.devops import backfill_metadata

        backfill_metadata.main()
    print(f"total: {total} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
