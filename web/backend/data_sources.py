from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, Integer, String, delete, func, inspect, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from tradingagents.dataflows import vendor_usage as vendor_defaults
from web.backend import auth


DATA_SOURCE_TABLES = (
    "data_source_vendor_configs",
    "data_source_route_policies",
    "data_source_usage",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _today_key() -> str:
    return date.today().isoformat()


class DataSourceVendorConfig(auth.Base):
    __tablename__ = "data_source_vendor_configs"

    vendor: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    daily_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hourly_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class DataSourceUsage(auth.Base):
    __tablename__ = "data_source_usage"
    __table_args__ = (
        Index("ix_data_source_usage_date_vendor", "usage_date", "vendor"),
        Index("ix_data_source_usage_module_date", "module", "usage_date"),
    )

    usage_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    vendor: Mapped[str] = mapped_column(String(64), primary_key=True)
    module: Mapped[str] = mapped_column(String(32), primary_key=True)
    total_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hour_key: Mapped[str | None] = mapped_column(String(13), nullable=True)
    hour_total_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class DataSourceRoutePolicy(auth.Base):
    __tablename__ = "data_source_route_policies"
    __table_args__ = (
        Index("ix_data_source_route_policies_module_market", "module", "market"),
    )

    module: Mapped[str] = mapped_column(String(32), primary_key=True)
    market: Mapped[str] = mapped_column(String(32), primary_key=True)
    category: Mapped[str] = mapped_column(String(64), primary_key=True)
    vendor_chain: Mapped[str] = mapped_column(String(512), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


def database_backed_usage_enabled(settings: auth.AuthSettings | None = None) -> bool:
    resolved_settings = settings or auth.get_auth_settings()
    return resolved_settings.enabled and bool(resolved_settings.database_url)


def ensure_data_source_tables(settings: auth.AuthSettings | None = None) -> None:
    resolved_settings = settings or auth.get_auth_settings()
    if not database_backed_usage_enabled(resolved_settings):
        return

    inspector = inspect(auth.get_engine(resolved_settings))
    missing_tables = [
        table_name for table_name in DATA_SOURCE_TABLES if not inspector.has_table(table_name)
    ]
    if missing_tables:
        joined = ", ".join(missing_tables)
        raise RuntimeError(
            "Auth is enabled but the following data source tables are missing: "
            f"{joined}. Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )


def initialize_data_source_runtime() -> None:
    ensure_data_source_tables()


def select_usage_row(*, vendor: str, module: str, usage_date: str):
    return select(DataSourceUsage).where(
        DataSourceUsage.vendor == vendor,
        DataSourceUsage.module == module,
        DataSourceUsage.usage_date == usage_date,
    )


def reset_data_source_state() -> None:
    if not database_backed_usage_enabled():
        return
    with auth.db_session() as db:
        db.execute(delete(DataSourceUsage))
        db.execute(delete(DataSourceRoutePolicy))
        db.execute(delete(DataSourceVendorConfig))


def _normalize_limit(value: int | None, *, label: str = "daily_limit") -> int | None:
    if value is None:
        return None
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{label} must be blank or a non-negative integer")
    return normalized


def _default_config(vendor: str) -> dict[str, Any]:
    default = vendor_defaults.DEFAULT_VENDOR_CONFIGS[vendor]
    return {
        "label": default["label"],
        "enabled": default["enabled"],
        "daily_limit": default["daily_limit"],
        "hourly_limit": default["hourly_limit"],
    }


def _normalize_module(value: str) -> str:
    candidate = str(value or "").strip().lower()
    if candidate not in vendor_defaults.MODULE_ORDER:
        raise ValueError(f"module must be one of {', '.join(vendor_defaults.MODULE_ORDER)}")
    return candidate


def _normalize_market(value: str) -> str:
    candidate = str(value or "").strip().lower()
    if candidate not in {"cn", "us", "global"}:
        raise ValueError("market must be one of cn, us, or global")
    return candidate


def _normalize_category(value: str) -> str:
    candidate = str(value or "").strip().lower()
    if candidate not in {"core_stock_apis", "technical_indicators", "fundamental_data", "news_data"}:
        raise ValueError(
            "category must be one of core_stock_apis, technical_indicators, fundamental_data, or news_data"
        )
    return candidate


def _normalize_vendor_chain(vendor_chain: list[str]) -> list[str]:
    normalized_chain: list[str] = []
    for vendor in vendor_chain:
        candidate = str(vendor or "").strip().lower()
        if not candidate:
            continue
        if candidate not in vendor_defaults.DEFAULT_VENDOR_CONFIGS:
            raise ValueError(f"Unknown data source vendor '{vendor}'")
        if candidate not in normalized_chain:
            normalized_chain.append(candidate)
    if not normalized_chain:
        raise ValueError("vendor_chain must include at least one vendor")
    return normalized_chain


def _serialize_vendor_chain(vendor_chain: list[str]) -> str:
    return ",".join(_normalize_vendor_chain(vendor_chain))


def _parse_vendor_chain(value: str | None) -> list[str]:
    if not value:
        return []
    return [vendor for vendor in (item.strip().lower() for item in value.split(",")) if vendor]


def _default_route(module: str, market: str, category: str) -> list[str]:
    return list(
        vendor_defaults.DEFAULT_ROUTE_POLICIES.get(
            (module, market, category),
            [],
        )
    )


def _route_payload(
    *,
    module: str,
    market: str,
    category: str,
    vendor_chain: list[str],
) -> dict[str, Any]:
    return {
        "module": module,
        "market": market,
        "category": category,
        "vendor_chain": vendor_chain,
        "default_vendor_chain": _default_route(module, market, category),
    }


def _sorted_route_keys() -> list[tuple[str, str, str]]:
    module_rank = {value: index for index, value in enumerate(vendor_defaults.MODULE_ORDER)}
    market_rank = {"cn": 0, "us": 1, "global": 2}
    category_rank = {
        "core_stock_apis": 0,
        "technical_indicators": 1,
        "fundamental_data": 2,
        "news_data": 3,
    }
    return sorted(
        vendor_defaults.DEFAULT_ROUTE_POLICIES,
        key=lambda item: (
            module_rank.get(item[0], 99),
            market_rank.get(item[1], 99),
            category_rank.get(item[2], 99),
        ),
    )


def _config_payload(db: Session, vendor: str) -> dict[str, Any]:
    row = db.get(DataSourceVendorConfig, vendor)
    if row is None:
        return _default_config(vendor)
    return {
        "label": row.label,
        "enabled": row.enabled,
        "daily_limit": row.daily_limit,
        "hourly_limit": row.hourly_limit,
    }


def _sum_usage(db: Session, vendor: str, usage_date: str) -> dict[str, Any]:
    row = db.execute(
        select(
            func.coalesce(func.sum(DataSourceUsage.total_calls), 0),
            func.coalesce(func.sum(DataSourceUsage.success_count), 0),
            func.coalesce(func.sum(DataSourceUsage.failure_count), 0),
            func.max(DataSourceUsage.last_called_at),
        ).where(
            DataSourceUsage.vendor == vendor,
            DataSourceUsage.usage_date == usage_date,
        )
    ).one()
    return {
        "total_calls": int(row[0] or 0),
        "success_count": int(row[1] or 0),
        "failure_count": int(row[2] or 0),
        "last_called_at": row[3],
    }


def _current_hour_key() -> str:
    return _utcnow().strftime("%Y-%m-%dT%H")


def _sum_hour_usage(db: Session, vendor: str, usage_date: str, hour_key: str) -> int:
    value = db.scalar(
        select(func.coalesce(func.sum(DataSourceUsage.hour_total_calls), 0)).where(
            DataSourceUsage.vendor == vendor,
            DataSourceUsage.usage_date == usage_date,
            DataSourceUsage.hour_key == hour_key,
        )
    )
    return int(value or 0)


def _module_usage(db: Session, vendor: str, usage_date: str, module: str) -> dict[str, int]:
    row = db.scalar(select_usage_row(vendor=vendor, module=module, usage_date=usage_date))
    if row is None:
        return {"total_calls": 0, "success_count": 0, "failure_count": 0}
    return {
        "total_calls": row.total_calls,
        "success_count": row.success_count,
        "failure_count": row.failure_count,
    }


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def build_source_summary(db: Session, vendor: str, usage_date: str) -> dict[str, Any]:
    config = _config_payload(db, vendor)
    usage = _sum_usage(db, vendor, usage_date)
    daily_limit = config["daily_limit"]
    hourly_limit = config["hourly_limit"]
    used_this_hour = _sum_hour_usage(db, vendor, usage_date, _current_hour_key())
    remaining = None if daily_limit is None else max(daily_limit - usage["total_calls"], 0)
    hourly_remaining = (
        None if hourly_limit is None else max(hourly_limit - used_this_hour, 0)
    )
    daily_exhausted = daily_limit is not None and usage["total_calls"] >= daily_limit
    hour_exhausted = hourly_limit is not None and used_this_hour >= hourly_limit
    return {
        "vendor": vendor,
        "label": config["label"],
        "enabled": config["enabled"],
        "daily_limit": daily_limit,
        "hourly_limit": hourly_limit,
        "used_today": usage["total_calls"],
        "used_this_hour": used_this_hour,
        "remaining_today": remaining,
        "remaining_this_hour": hourly_remaining,
        "daily_exhausted": daily_exhausted,
        "hour_exhausted": hour_exhausted,
        "exhausted": daily_exhausted or hour_exhausted,
        "success_count": usage["success_count"],
        "failure_count": usage["failure_count"],
        "last_called_at": _serialize_datetime(usage["last_called_at"]),
        "modules": {
            module: _module_usage(db, vendor, usage_date, module)
            for module in vendor_defaults.MODULE_ORDER
            if module != "unknown"
        },
    }


def get_data_source_usage_summary() -> dict[str, Any]:
    usage_date = _today_key()
    with auth.db_session() as db:
        return {
            "date": usage_date,
            "sources": [
                build_source_summary(db, vendor, usage_date)
                for vendor in vendor_defaults.VENDOR_ORDER
            ],
            "routes": list_data_source_routes(db),
        }


def list_data_source_routes(db: Session) -> list[dict[str, Any]]:
    configured_routes = {
        (row.module, row.market, row.category): _parse_vendor_chain(row.vendor_chain)
        for row in db.scalars(select(DataSourceRoutePolicy)).all()
    }
    routes: list[dict[str, Any]] = []
    for module, market, category in _sorted_route_keys():
        routes.append(
            _route_payload(
                module=module,
                market=market,
                category=category,
                vendor_chain=configured_routes.get(
                    (module, market, category),
                    _default_route(module, market, category),
                ),
            )
        )
    return routes


def resolve_data_source_route(
    *,
    module: str,
    market: str,
    category: str,
) -> list[str]:
    normalized_module = _normalize_module(module)
    normalized_market = _normalize_market(market)
    normalized_category = _normalize_category(category)
    with auth.db_session() as db:
        row = db.get(
            DataSourceRoutePolicy,
            (normalized_module, normalized_market, normalized_category),
        )
        if row is None:
            return _default_route(normalized_module, normalized_market, normalized_category)
        return _parse_vendor_chain(row.vendor_chain)


def update_data_source_route(
    *,
    module: str,
    market: str,
    category: str,
    vendor_chain: list[str],
) -> dict[str, Any]:
    normalized_module = _normalize_module(module)
    normalized_market = _normalize_market(market)
    normalized_category = _normalize_category(category)
    serialized_chain = _serialize_vendor_chain(vendor_chain)
    now = _utcnow()
    with auth.db_session() as db:
        row = db.get(
            DataSourceRoutePolicy,
            (normalized_module, normalized_market, normalized_category),
        )
        if row is None:
            row = DataSourceRoutePolicy(
                module=normalized_module,
                market=normalized_market,
                category=normalized_category,
                vendor_chain=serialized_chain,
                updated_at=now,
            )
            db.add(row)
        else:
            row.vendor_chain = serialized_chain
            row.updated_at = now
        db.flush()
        return _route_payload(
            module=normalized_module,
            market=normalized_market,
            category=normalized_category,
            vendor_chain=_parse_vendor_chain(row.vendor_chain),
        )


def update_data_source_config(
    vendor: str,
    *,
    enabled: bool,
    daily_limit: int | None,
    hourly_limit: int | None = None,
    preserve_hourly_limit: bool = False,
) -> dict[str, Any]:
    usage_date = _today_key()
    default = _default_config(vendor)
    normalized_limit = _normalize_limit(daily_limit, label="daily_limit")
    normalized_hourly_limit = _normalize_limit(hourly_limit, label="hourly_limit")
    now = _utcnow()
    with auth.db_session() as db:
        row = db.get(DataSourceVendorConfig, vendor)
        if row is None:
            row = DataSourceVendorConfig(
                vendor=vendor,
                label=default["label"],
                enabled=bool(enabled),
                daily_limit=normalized_limit,
                hourly_limit=default["hourly_limit"] if preserve_hourly_limit else normalized_hourly_limit,
                updated_at=now,
            )
            db.add(row)
        else:
            row.label = default["label"]
            row.enabled = bool(enabled)
            row.daily_limit = normalized_limit
            if not preserve_hourly_limit:
                row.hourly_limit = normalized_hourly_limit
            row.updated_at = now
        db.flush()
        return build_source_summary(db, vendor, usage_date)


def is_data_source_available(vendor: str) -> bool:
    usage_date = _today_key()
    with auth.db_session() as db:
        config = _config_payload(db, vendor)
        if not config["enabled"]:
            return False
        daily_limit = config["daily_limit"]
        hourly_limit = config["hourly_limit"]
        usage = _sum_usage(db, vendor, usage_date)
        if daily_limit is not None and usage["total_calls"] >= daily_limit:
            return False
        if hourly_limit is None:
            return True
        used_this_hour = _sum_hour_usage(db, vendor, usage_date, _current_hour_key())
        return used_this_hour < hourly_limit


def record_data_source_call(
    vendor: str,
    *,
    module: str,
    success: bool,
) -> dict[str, Any]:
    usage_date = _today_key()
    now = _utcnow()
    hour_key = now.strftime("%Y-%m-%dT%H")
    with auth.db_session() as db:
        row = db.scalar(select_usage_row(vendor=vendor, module=module, usage_date=usage_date))
        if row is None:
            row = DataSourceUsage(
                usage_date=usage_date,
                vendor=vendor,
                module=module,
                total_calls=0,
                success_count=0,
                failure_count=0,
                hour_key=hour_key,
                hour_total_calls=0,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        if row.hour_key != hour_key:
            row.hour_key = hour_key
            row.hour_total_calls = 0
        row.total_calls += 1
        row.hour_total_calls += 1
        row.last_called_at = now
        row.updated_at = now
        if success:
            row.success_count += 1
        else:
            row.failure_count += 1
        db.flush()
        return build_source_summary(db, vendor, usage_date)
