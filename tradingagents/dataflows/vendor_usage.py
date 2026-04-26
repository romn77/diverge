from __future__ import annotations

import contextlib
import contextvars
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator, TypeVar

from tradingagents.data_layout import resolve_data_dir


VENDOR_ORDER = ("local", "akshare", "tushare", "fmp", "alpha_vantage", "yfinance", "massive")
MODULE_ORDER = ("analysis", "screener", "trade_journal", "unknown")
DEFAULT_VENDOR_CONFIGS = {
    "local": {"label": "Local Cache", "enabled": True, "daily_limit": None, "hourly_limit": None},
    "akshare": {"label": "AkShare", "enabled": True, "daily_limit": None, "hourly_limit": None},
    "tushare": {"label": "Tushare", "enabled": True, "daily_limit": None, "hourly_limit": None},
    "fmp": {"label": "Financial Modeling Prep", "enabled": True, "daily_limit": 250, "hourly_limit": None},
    "alpha_vantage": {"label": "Alpha Vantage", "enabled": True, "daily_limit": 25, "hourly_limit": None},
    "yfinance": {"label": "Yahoo Finance", "enabled": True, "daily_limit": None, "hourly_limit": None},
    "massive": {"label": "Massive", "enabled": True, "daily_limit": None, "hourly_limit": None},
}
DEFAULT_ROUTE_POLICIES = {
    ("analysis", "cn", "core_stock_apis"): ["tushare", "akshare"],
    ("analysis", "cn", "technical_indicators"): ["local"],
    ("analysis", "cn", "fundamental_data"): ["tushare", "akshare"],
    ("analysis", "cn", "news_data"): ["akshare", "yfinance"],
    ("analysis", "us", "core_stock_apis"): ["massive"],
    ("analysis", "us", "technical_indicators"): ["local"],
    ("analysis", "us", "fundamental_data"): ["fmp", "alpha_vantage", "yfinance"],
    ("analysis", "us", "news_data"): ["fmp", "alpha_vantage", "yfinance"],
    ("analysis", "global", "core_stock_apis"): ["yfinance"],
    ("analysis", "global", "technical_indicators"): ["yfinance"],
    ("analysis", "global", "fundamental_data"): ["yfinance"],
    ("analysis", "global", "news_data"): ["yfinance"],
    ("screener", "cn", "core_stock_apis"): ["tushare"],
    ("screener", "us", "core_stock_apis"): ["massive"],
    ("trade_journal", "cn", "core_stock_apis"): ["tushare", "akshare"],
    ("trade_journal", "us", "core_stock_apis"): ["massive", "yfinance"],
    ("trade_journal", "global", "core_stock_apis"): ["yfinance"],
}

T = TypeVar("T")
_DATABASE_FALLBACK = object()
_LIMIT_UNSET = object()

_current_module: contextvars.ContextVar[str] = contextvars.ContextVar(
    "data_source_usage_module",
    default="unknown",
)


@dataclass(slots=True)
class DataSourceQuotaAcquisition:
    vendor: str
    acquired: bool
    reason: str | None = None
    blocked_until: str | None = None
    retryable: bool = False
    reservation_keys: list[str] = field(default_factory=list)


class QuotaWaitRequired(Exception):
    def __init__(
        self,
        *,
        vendor: str,
        reason: str,
        blocked_until: str | None,
    ) -> None:
        self.vendor = vendor
        self.reason = reason
        self.blocked_until = blocked_until
        super().__init__(
            f"Data source '{vendor}' is waiting for quota recovery"
            + (f" until {blocked_until}" if blocked_until else "")
            + f": {reason}"
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
                "hourly_limit": config["hourly_limit"],
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
        hourly_limit = existing.get("hourly_limit", default_config["hourly_limit"])
        if hourly_limit is not None:
            hourly_limit = max(0, int(hourly_limit))
        normalized_configs[vendor] = {
            "label": default_config["label"],
            "enabled": bool(existing.get("enabled", default_config["enabled"])),
            "daily_limit": daily_limit,
            "hourly_limit": hourly_limit,
        }
    usage = state.get("usage") if isinstance(state.get("usage"), dict) else {}
    return {"configs": normalized_configs, "usage": usage}


def _today_key() -> str:
    return date.today().isoformat()


def current_usage_date() -> str:
    return _today_key()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_hour_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")


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
    vendor_usage.setdefault("hours", {})
    return vendor_usage


def _ensure_vendor_hour_usage(
    state: dict,
    vendor: str,
    day_key: str,
    hour_key: str,
) -> dict:
    vendor_usage = _ensure_vendor_day_usage(state, vendor, day_key)
    return vendor_usage.setdefault("hours", {}).setdefault(
        hour_key,
        {"total_calls": 0},
    )


def _normalize_vendor(vendor: str) -> str:
    normalized = str(vendor).strip().lower()
    if normalized not in DEFAULT_VENDOR_CONFIGS:
        raise ValueError(f"Unknown data source vendor '{vendor}'")
    return normalized


def _normalize_module(module: str | None) -> str:
    normalized = str(module or _current_module.get() or "unknown").strip().lower()
    return normalized if normalized in MODULE_ORDER else "unknown"


def reset_data_source_usage_state() -> None:
    database_store = _database_store()
    if database_store is not None:
        with contextlib.suppress(Exception):
            database_store.reset_data_source_state()

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


def _try_database_store(operation: Callable[[object], T]) -> T | object:
    database_store = _database_store()
    if database_store is None:
        if _database_governance_required():
            raise RuntimeError("Database-backed data-source governance is required but unavailable")
        return _DATABASE_FALLBACK
    try:
        return operation(database_store)
    except Exception as exc:
        if _database_governance_required():
            raise RuntimeError("Database-backed data-source governance failed") from exc
        return _DATABASE_FALLBACK


def get_data_source_route(
    *,
    category: str,
    market: str,
    module: str | None = None,
) -> list[str]:
    normalized_module = _normalize_module(module)
    normalized_market = str(market or "global").strip().lower()
    normalized_category = str(category).strip().lower()
    database_result = _try_database_store(
        lambda store: store.resolve_data_source_route(
            module=normalized_module,
            market=normalized_market,
            category=normalized_category,
        )
    )
    if database_result is not _DATABASE_FALLBACK:
        return database_result
    return list(
        DEFAULT_ROUTE_POLICIES.get(
            (normalized_module, normalized_market, normalized_category),
            [],
        )
    )


def update_data_source_config(
    vendor: str,
    *,
    enabled: bool,
    daily_limit: int | None,
    hourly_limit: int | None | object = _LIMIT_UNSET,
) -> dict:
    normalized_vendor = _normalize_vendor(vendor)
    if daily_limit is not None and daily_limit < 0:
        raise ValueError("daily_limit must be blank or a non-negative integer")
    if hourly_limit is not _LIMIT_UNSET and hourly_limit is not None and hourly_limit < 0:
        raise ValueError("hourly_limit must be blank or a non-negative integer")
    database_result = _try_database_store(
        lambda store: store.update_data_source_config(
            normalized_vendor,
            enabled=enabled,
            daily_limit=daily_limit,
            hourly_limit=None if hourly_limit is _LIMIT_UNSET else hourly_limit,
            preserve_hourly_limit=hourly_limit is _LIMIT_UNSET,
        )
    )
    if database_result is not _DATABASE_FALLBACK:
        return database_result
    with _exclusive_state() as state:
        state["configs"][normalized_vendor]["enabled"] = bool(enabled)
        state["configs"][normalized_vendor]["daily_limit"] = daily_limit
        if hourly_limit is not _LIMIT_UNSET:
            state["configs"][normalized_vendor]["hourly_limit"] = hourly_limit
        return _build_source_summary(state, normalized_vendor, _today_key())


def is_data_source_available(vendor: str) -> bool:
    normalized_vendor = _normalize_vendor(vendor)
    database_result = _try_database_store(
        lambda store: store.is_data_source_available(normalized_vendor)
    )
    if database_result is not _DATABASE_FALLBACK:
        return database_result
    with _exclusive_state() as state:
        config = state["configs"][normalized_vendor]
        if not config["enabled"]:
            return False
        daily_limit = config["daily_limit"]
        hourly_limit = config["hourly_limit"]
        used_today = _ensure_vendor_day_usage(
            state,
            normalized_vendor,
            _today_key(),
        )["total_calls"]
        if daily_limit is not None and used_today >= daily_limit:
            return False
        if hourly_limit is None:
            return True
        used_this_hour = _ensure_vendor_hour_usage(
            state,
            normalized_vendor,
            _today_key(),
            _current_hour_key(),
        )["total_calls"]
        return used_this_hour < hourly_limit


def acquire_data_source_quota(vendor: str) -> DataSourceQuotaAcquisition:
    normalized_vendor = _normalize_vendor(vendor)
    source = _source_summary_by_vendor(normalized_vendor)
    if not source["enabled"]:
        return DataSourceQuotaAcquisition(
            vendor=normalized_vendor,
            acquired=False,
            reason="Data source is disabled.",
            retryable=False,
        )

    blocked_until = _blocked_until_for_source(source)
    if blocked_until is not None:
        return DataSourceQuotaAcquisition(
            vendor=normalized_vendor,
            acquired=False,
            reason="Data source quota exhausted.",
            blocked_until=blocked_until,
            retryable=True,
        )

    acquisition = _reserve_redis_quota(normalized_vendor, source)
    if acquisition is not None:
        return acquisition

    return DataSourceQuotaAcquisition(vendor=normalized_vendor, acquired=True)


def release_data_source_quota(acquisition: DataSourceQuotaAcquisition | None) -> None:
    if acquisition is None or not acquisition.reservation_keys:
        return
    client = _quota_redis_client()
    if client is None:
        return
    for key in acquisition.reservation_keys:
        with contextlib.suppress(Exception):
            client.decr(key)


def _source_summary_by_vendor(vendor: str) -> dict:
    sources = {
        source["vendor"]: source
        for source in get_data_source_usage_summary()["sources"]
    }
    return sources[vendor]


def _blocked_until_for_source(source: dict) -> str | None:
    daily_exhausted = bool(source.get("daily_exhausted"))
    hour_exhausted = bool(source.get("hour_exhausted"))
    if hour_exhausted:
        return _next_hour_iso()
    if daily_exhausted:
        return _next_day_iso()
    return None


def _next_hour_iso() -> str:
    now = datetime.now(timezone.utc)
    next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    return next_hour.isoformat()


def _next_day_iso() -> str:
    now = datetime.now(timezone.utc)
    next_day = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    return next_day.isoformat()


def _seconds_until(iso_value: str | None, *, default: int) -> int:
    if not iso_value:
        return default
    try:
        target = datetime.fromisoformat(iso_value)
    except ValueError:
        return default
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    return max(int((target - datetime.now(timezone.utc)).total_seconds()), 1)


def _quota_redis_client():
    if os.environ.get("TASK_BACKEND", "local").strip().lower() != "redis":
        return None
    try:
        import redis
    except ImportError:
        return None
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    return redis.Redis.from_url(redis_url, decode_responses=False)


def _reserve_redis_quota(
    vendor: str,
    source: dict,
) -> DataSourceQuotaAcquisition | None:
    client = _quota_redis_client()
    if client is None:
        return None

    daily_limit = source.get("daily_limit")
    hourly_limit = source.get("hourly_limit")
    if daily_limit is None and hourly_limit is None:
        return DataSourceQuotaAcquisition(vendor=vendor, acquired=True)

    prefix = os.environ.get("TASK_STORE_PREFIX", "tradingagents").strip(":")
    day_key = current_usage_date()
    hour_key = _current_hour_key()
    daily_redis_key = f"{prefix}:quota:{vendor}:day:{day_key}"
    hourly_redis_key = f"{prefix}:quota:{vendor}:hour:{hour_key}"
    daily_ttl = _seconds_until(_next_day_iso(), default=24 * 60 * 60)
    hourly_ttl = _seconds_until(_next_hour_iso(), default=60 * 60)

    script = """
local daily_key = KEYS[1]
local hourly_key = KEYS[2]
local daily_limit = tonumber(ARGV[1])
local daily_used = tonumber(ARGV[2])
local hourly_limit = tonumber(ARGV[3])
local hourly_used = tonumber(ARGV[4])
local daily_ttl = tonumber(ARGV[5])
local hourly_ttl = tonumber(ARGV[6])
local daily_reserved = tonumber(redis.call('GET', daily_key) or '0')
local hourly_reserved = tonumber(redis.call('GET', hourly_key) or '0')
if daily_limit >= 0 and daily_used + daily_reserved >= daily_limit then
  return 2
end
if hourly_limit >= 0 and hourly_used + hourly_reserved >= hourly_limit then
  return 3
end
if daily_limit >= 0 then
  redis.call('INCR', daily_key)
  redis.call('EXPIRE', daily_key, daily_ttl)
end
if hourly_limit >= 0 then
  redis.call('INCR', hourly_key)
  redis.call('EXPIRE', hourly_key, hourly_ttl)
end
return 1
"""
    try:
        result = int(
            client.eval(
                script,
                2,
                daily_redis_key,
                hourly_redis_key,
                -1 if daily_limit is None else int(daily_limit),
                int(source.get("used_today") or 0),
                -1 if hourly_limit is None else int(hourly_limit),
                int(source.get("used_this_hour") or 0),
                daily_ttl,
                hourly_ttl,
            )
        )
    except Exception:
        return None

    if result == 1:
        keys = []
        if daily_limit is not None:
            keys.append(daily_redis_key)
        if hourly_limit is not None:
            keys.append(hourly_redis_key)
        return DataSourceQuotaAcquisition(
            vendor=vendor,
            acquired=True,
            reservation_keys=keys,
        )
    if result == 3:
        return DataSourceQuotaAcquisition(
            vendor=vendor,
            acquired=False,
            reason="Data source hourly quota exhausted.",
            blocked_until=_next_hour_iso(),
            retryable=True,
        )
    return DataSourceQuotaAcquisition(
        vendor=vendor,
        acquired=False,
        reason="Data source daily quota exhausted.",
        blocked_until=_next_day_iso(),
        retryable=True,
    )


def record_data_source_call(
    vendor: str,
    *,
    module: str | None = None,
    success: bool,
) -> dict:
    normalized_vendor = _normalize_vendor(vendor)
    normalized_module = _normalize_module(module)
    database_result = _try_database_store(
        lambda store: store.record_data_source_call(
            normalized_vendor,
            module=normalized_module,
            success=success,
        )
    )
    if database_result is not _DATABASE_FALLBACK:
        return database_result
    with _exclusive_state() as state:
        day_key = _today_key()
        usage = _ensure_vendor_day_usage(state, normalized_vendor, day_key)
        hour_usage = _ensure_vendor_hour_usage(
            state,
            normalized_vendor,
            day_key,
            _current_hour_key(),
        )
        usage["total_calls"] += 1
        hour_usage["total_calls"] += 1
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
    acquisition = acquire_data_source_quota(vendor)
    if not acquisition.acquired:
        if acquisition.retryable:
            raise QuotaWaitRequired(
                vendor=acquisition.vendor,
                reason=acquisition.reason or "Data source quota exhausted.",
                blocked_until=acquisition.blocked_until,
            )
        raise RuntimeError(acquisition.reason or f"Data source '{vendor}' is unavailable.")
    try:
        result = callback()
    except Exception:
        try:
            record_data_source_call(vendor, success=False)
        finally:
            release_data_source_quota(acquisition)
        raise
    try:
        record_data_source_call(vendor, success=True)
    finally:
        release_data_source_quota(acquisition)
    return result


def _build_source_summary(state: dict, vendor: str, day_key: str) -> dict:
    config = state["configs"][vendor]
    usage = _ensure_vendor_day_usage(state, vendor, day_key)
    daily_limit = config["daily_limit"]
    hourly_limit = config["hourly_limit"]
    hour_usage = _ensure_vendor_hour_usage(state, vendor, day_key, _current_hour_key())
    remaining = None if daily_limit is None else max(daily_limit - usage["total_calls"], 0)
    hourly_remaining = (
        None if hourly_limit is None else max(hourly_limit - hour_usage["total_calls"], 0)
    )
    daily_exhausted = daily_limit is not None and usage["total_calls"] >= daily_limit
    hour_exhausted = hourly_limit is not None and hour_usage["total_calls"] >= hourly_limit
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
        "hourly_limit": hourly_limit,
        "used_today": usage["total_calls"],
        "used_this_hour": hour_usage["total_calls"],
        "remaining_today": remaining,
        "remaining_this_hour": hourly_remaining,
        "daily_exhausted": daily_exhausted,
        "hour_exhausted": hour_exhausted,
        "exhausted": daily_exhausted or hour_exhausted,
        "success_count": usage["success_count"],
        "failure_count": usage["failure_count"],
        "last_called_at": usage["last_called_at"],
        "modules": modules,
    }


def _build_default_route_summary() -> list[dict]:
    return [
        {
            "module": module,
            "market": market,
            "category": category,
            "vendor_chain": list(vendor_chain),
            "default_vendor_chain": list(vendor_chain),
        }
        for (module, market, category), vendor_chain in sorted(DEFAULT_ROUTE_POLICIES.items())
    ]


def get_data_source_usage_summary() -> dict:
    database_result = _try_database_store(
        lambda store: store.get_data_source_usage_summary()
    )
    if database_result is not _DATABASE_FALLBACK:
        return database_result
    day_key = _today_key()
    with _exclusive_state() as state:
        return {
            "date": day_key,
            "sources": [
                _build_source_summary(state, vendor, day_key)
                for vendor in VENDOR_ORDER
            ],
            "routes": _build_default_route_summary(),
        }


def _database_store():
    try:
        from web.backend import data_sources
    except Exception:
        return None
    try:
        if data_sources.database_backed_usage_enabled():
            return data_sources
    except Exception:
        return None
    return None


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _database_governance_required() -> bool:
    if _env_bool("DATA_SOURCE_USAGE_ALLOW_LOCAL_FALLBACK", False):
        return False
    strict_env = os.environ.get("APP_ENV", "").strip().lower() == "production"
    if not strict_env and not _env_bool("DATA_SOURCE_GOVERNANCE_STRICT", False):
        return False
    try:
        from web.backend import auth

        settings = auth.get_auth_settings()
    except Exception:
        return False
    return settings.enabled and bool(settings.database_url)
