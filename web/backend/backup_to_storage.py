from __future__ import annotations

import sys
from pathlib import Path

from web.backend import storage


def upload_backup(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    key = f"backups/postgres/{path.name}"
    storage.get_storage().put_bytes(
        key,
        path.read_bytes(),
        content_type="application/gzip",
    )
    return key


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("Usage: python -m web.backend.backup_to_storage /path/to/backup.sql.gz", file=sys.stderr)
        return 2
    key = upload_backup(Path(args[0]))
    print(f"Uploaded backup to storage key: {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
