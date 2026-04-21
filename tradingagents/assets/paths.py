from __future__ import annotations

import os
from pathlib import Path


def tradingagents_home() -> Path:
    return Path(os.path.expanduser("~")) / ".tradingagents"


def resolve_assets_db_path(db_path: str | Path | None = None) -> Path:
    if db_path is not None:
        path = Path(db_path).expanduser()
    else:
        configured = os.getenv("TRADINGAGENTS_ASSETS_DB")
        if configured:
            path = Path(configured).expanduser()
        else:
            path = tradingagents_home() / "assets.db"

    path.parent.mkdir(parents=True, exist_ok=True)
    return path
