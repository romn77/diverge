from __future__ import annotations

import contextlib
import contextvars
import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, TypeVar

from tradingagents.data_layout import resolve_data_dir


VENDOR_ORDER = ("akshare", "tushare", "yfinance", "alpha_vantage", "massive")
MODULE_ORDER = ("analysis", "screener", "trade_journal", "unknown")
DEFAULT_VENDOR_CONFIGS = {
    "akshare": {"label": "AkShare", "enabled": True, "daily_limit": None},
    "tushare": {"label": "Tushare", "enabled": True, "daily_limit": None},
    "yfinance": {"label": "Yahoo Finance", "enabled": True, "daily_limit": None},
    "alpha_vantage": {"label": "Alpha Vantage", "enabled": True, "daily_limit": 25},
    "massive": {"label": "Massive", "enabled": True, "daily_limit": None},
}

T = TypeVar("T")

_current_module: contextvars.ContextVar[str] = contextvars.ContextVar(
    "data_source_usage_module",
    default="unknown",
)


def _usage_path() -> Path:
    configured = os.environ.get("DATA_SOURCE_USAGE_PATH")
    if configured:
        return Path(configured).resolve()
    return (resolve_data_dir() / "data_source_usage.json").resolve()


@contextlib.contextmanager
def _exclusive_state() -> Iterator[dict]:
    path = _usage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        try:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass

        state = _load_state(path)
        try:
            yield state
        finally:
            _write_state(path, state)
            try:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass


def _load_state(path: Path) -> dict:
    if not path.is_file():
        return _default_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return _default_state()
    if not isinstance(payload, dict):
        return _default_state()
    return _normalize_state(payload)


def _write_state(path: Path, state: dict) -> None:
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(_normalize_state(state), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _default_state() -> dict:
    return {
        "configs": {
            vendor: {
                "label": config["label"],
                "enabled": config["enabled"],
                "daily_limit": config["daily_limit"],
            }
            for vendor, config in DEFAULT_VENDOR_CONFIGS.items()
        },
        "usage": {},
    }


def _normalize_state(state: dict) -> dict:
    configs = dict(state.get("configs") or {})
    normalized_configs = {}
    for vendor, default_config in DEFAULT_VENDOR_CONFIGS.items():
        existing = configs.get(vendor) if isinstance(configs.get(vendor), dict) else {}
        daily_limit = existing.get("daily_limit", default_config["daily_limit"])
        if daily_limit is not None:
            daily_limit = max(0, int(daily_limit))
        normalized_configs[vendor] = {
            "label": default_config["label"],
            "enabled": bool(existing.get("enabled", default_config["enabled"])),
            "daily_limit": daily_limit,
        }
    usage = state.get("usage") if isinstance(state.get("usage"), dict) else {}
    return {"configs": normalized_configs, "usage": usage}


def _today_key() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_module_usage() -> dict:
    return {"total_calls": 0, "success_count": 0, "failure_count": 0}


def _ensure_vendor_day_usage(state: dict, vendor: str, day_key: str) -> dict:
    day_usage = state.setdefault("usage", {}).setdefault(day_key, {})
    vendor_usage = day_usage.setdefault(
        vendor,
        {
            "total_calls": 0,
            "success_count": 0,
            "failure_count": 0,
            "last_called_at": None,
            "modules": {},
        },
    )
    modules = vendor_usage.setdefault("modules", {})
    for module in MODULE_ORDER:
        modules.setdefault(module, _empty_module_usage())
    return vendor_usage


def _normalize_vendor(vendor: str) -> str:
    normalized = str(vendor).strip().lower()
    if normalized not in DEFAULT_VENDOR_CONFIGS:
        raise ValueError(f"Unknown data source vendor '{vendor}'")
    return normalized


def _normalize_module(module: str | None) -> str:
    normalized = str(module or _current_module.get() or "unknown").strip().lower()
    return normalized if normalized in MODULE_ORDER else "unknown"


def reset_data_source_usage_state() -> None:
    path = _usage_path()
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
    with contextlib.suppress(FileNotFoundError):
        path.with_suffix(path.suffix + ".lock").unlink()


@contextlib.contextmanager
def data_source_usage_context(module: str) -> Iterator[None]:
    token = _current_module.set(_normalize_module(module))
    try:
        yield
    finally:
        _current_module.reset(token)


def update_data_source_config(
    vendor: str,
    *,
    enabled: bool,
    daily_limit: int | None,
) -> dict:
    normalized_vendor = _normalize_vendor(vendor)
    if daily_limit is not None and daily_limit < 0:
        raise ValueError("daily_limit must be blank or a non-negative integer")
    with _exclusive_state() as state:
        state["configs"][normalized_vendor]["enabled"] = bool(enabled)
        state["configs"][normalized_vendor]["daily_limit"] = daily_limit
        return _build_source_summary(state, normalized_vendor, _today_key())


def is_data_source_available(vendor: str) -> bool:
    normalized_vendor = _normalize_vendor(vendor)
    with _exclusive_state() as state:
        config = state["configs"][normalized_vendor]
        if not config["enabled"]:
            return False
        daily_limit = config["daily_limit"]
        if daily_limit is None:
            return True
        used_today = _ensure_vendor_day_usage(
            state,
            normalized_vendor,
            _today_key(),
        )["total_calls"]
        return used_today < daily_limit


def record_data_source_call(
    vendor: str,
    *,
    module: str | None = None,
    success: bool,
) -> dict:
    normalized_vendor = _normalize_vendor(vendor)
    normalized_module = _normalize_module(module)
    with _exclusive_state() as state:
        usage = _ensure_vendor_day_usage(state, normalized_vendor, _today_key())
        usage["total_calls"] += 1
        usage["last_called_at"] = _now_iso()
        if success:
            usage["success_count"] += 1
        else:
            usage["failure_count"] += 1

        module_usage = usage["modules"].setdefault(normalized_module, _empty_module_usage())
        module_usage["total_calls"] += 1
        if success:
            module_usage["success_count"] += 1
        else:
            module_usage["failure_count"] += 1
        return _build_source_summary(state, normalized_vendor, _today_key())


def track_data_source_call(vendor: str, callback: Callable[[], T]) -> T:
    try:
        result = callback()
    except Exception:
        record_data_source_call(vendor, success=False)
        raise
    record_data_source_call(vendor, success=True)
    return result


def _build_source_summary(state: dict, vendor: str, day_key: str) -> dict:
    config = state["configs"][vendor]
    usage = _ensure_vendor_day_usage(state, vendor, day_key)
    daily_limit = config["daily_limit"]
    remaining = None if daily_limit is None else max(daily_limit - usage["total_calls"], 0)
    modules = {
        module: dict(usage["modules"].get(module) or _empty_module_usage())
        for module in MODULE_ORDER
        if module != "unknown"
    }
    return {
        "vendor": vendor,
        "label": config["label"],
        "enabled": config["enabled"],
        "daily_limit": daily_limit,
        "used_today": usage["total_calls"],
        "remaining_today": remaining,
        "exhausted": daily_limit is not None and usage["total_calls"] >= daily_limit,
        "success_count": usage["success_count"],
        "failure_count": usage["failure_count"],
        "last_called_at": usage["last_called_at"],
        "modules": modules,
    }


def get_data_source_usage_summary() -> dict:
    day_key = _today_key()
    with _exclusive_state() as state:
        return {
            "date": day_key,
            "sources": [
                _build_source_summary(state, vendor, day_key)
                for vendor in VENDOR_ORDER
            ],
        }
