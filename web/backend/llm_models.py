from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    case,
    func,
    inspect,
    select,
)
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Mapped, Session, mapped_column

from diverge.llm_clients.model_config import (
    DEEP_MODEL_OPTIONS,
    PROVIDER_OPTIONS,
    QUICK_MODEL_OPTIONS,
    get_provider_base_url,
)
from diverge.llm_clients.model_profiles import (
    PROVIDER_API_KEY_ENV_VARS,
    STATIC_MODEL_PROFILES,
    ModelRoute,
    ResolvedModelSelection,
    get_model_profile,
    list_model_profile_options,
    resolve_model_profile,
    serialize_model_profile,
)
from web.backend import auth


LLM_MODEL_TABLES = (
    "llm_provider_configs",
    "llm_model_configs",
    "llm_model_profiles",
    "llm_model_profile_routes",
    "llm_module_settings",
    "llm_ui_settings",
    "llm_model_usage",
)

VALID_COST_TIERS = {"low", "medium", "high", "premium"}
VALID_PROFILE_MODES = {"quick", "deep"}
VALID_ROLES = {"admin", "operator", "viewer"}
VALID_MODULE_SETTINGS = {"trade_journal_review"}
VALID_OUTPUT_LANGUAGES = {"en", "cn"}
VALID_OPENAI_REASONING_EFFORTS = {"low", "medium", "high"}
VALID_GOOGLE_THINKING_LEVELS = {"high", "minimal"}
SHOW_CUSTOM_ANALYSIS_PROFILE_SETTING = "show_custom_analysis_model_profile"
VALID_UI_SETTINGS = {SHOW_CUSTOM_ANALYSIS_PROFILE_SETTING}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _today_key() -> str:
    return date.today().isoformat()


class LLMProviderConfig(auth.Base):
    __tablename__ = "llm_provider_configs"

    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    api_key_env: Mapped[str | None] = mapped_column(String(128), nullable=True)
    daily_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hourly_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class LLMModelConfig(auth.Base):
    __tablename__ = "llm_model_configs"
    __table_args__ = (Index("ix_llm_model_configs_provider", "provider"),)

    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(192), nullable=False)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supports_quick: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_deep: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cost_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    visible_to_roles: Mapped[str] = mapped_column(
        String(128), nullable=False, default="admin,operator,viewer"
    )
    daily_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weekly_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class LLMModelProfile(auth.Base):
    __tablename__ = "llm_model_profiles"

    profile_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_for_roles: Mapped[str] = mapped_column(
        String(128), nullable=False, default=""
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class LLMModelProfileRoute(auth.Base):
    __tablename__ = "llm_model_profile_routes"
    __table_args__ = (Index("ix_llm_model_profile_routes_profile", "profile_id"),)

    profile_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), primary_key=True)
    route_order: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(192), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LLMModuleSetting(auth.Base):
    __tablename__ = "llm_module_settings"

    module: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model_profile: Mapped[str] = mapped_column(
        String(64), nullable=False, default="balanced"
    )
    output_language: Mapped[str] = mapped_column(
        String(8), nullable=False, default="cn"
    )
    custom_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    custom_model: Mapped[str | None] = mapped_column(String(192), nullable=True)
    openai_reasoning_effort: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    google_thinking_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class LLMUiSetting(auth.Base):
    __tablename__ = "llm_ui_settings"

    setting_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


class LLMModelUsage(auth.Base):
    __tablename__ = "llm_model_usage"
    __table_args__ = (
        Index(
            "ix_llm_model_usage_provider_model_date",
            "provider",
            "model_id",
            "usage_date",
        ),
    )

    usage_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(192), primary_key=True)
    module: Mapped[str] = mapped_column(String(32), primary_key=True)
    total_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hour_key: Mapped[str | None] = mapped_column(String(13), nullable=True)
    hour_total_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_called_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )


def database_backed_llm_models_enabled(
    settings: auth.AuthSettings | None = None,
) -> bool:
    resolved_settings = settings or auth.get_auth_settings()
    return resolved_settings.enabled and bool(resolved_settings.database_url)


def ensure_llm_model_tables(settings: auth.AuthSettings | None = None) -> None:
    resolved_settings = settings or auth.get_auth_settings()
    if not database_backed_llm_models_enabled(resolved_settings):
        return
    inspector = inspect(auth.get_engine(resolved_settings))
    missing_tables = [
        table_name
        for table_name in LLM_MODEL_TABLES
        if not inspector.has_table(table_name)
    ]
    if missing_tables:
        raise RuntimeError(
            "Auth is enabled but the following LLM model tables are missing: "
            f"{', '.join(missing_tables)}. Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )


def initialize_llm_model_runtime() -> None:
    ensure_llm_model_tables()
    ensure_llm_model_defaults()


def _model_pk(provider: str, model_id: str) -> str:
    return f"{provider}:{model_id}"


def _normalize_limit(value: int | None, *, label: str) -> int | None:
    if value is None:
        return None
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{label} must be blank or a non-negative integer")
    return normalized


def _default_provider(provider: str) -> dict[str, Any]:
    provider_map = {
        provider_key: (label, base_url)
        for provider_key, label, base_url in PROVIDER_OPTIONS
    }
    label, base_url = provider_map[provider]
    return {
        "provider": provider,
        "label": label,
        "enabled": True,
        "base_url": base_url,
        "api_key_env": PROVIDER_API_KEY_ENV_VARS.get(provider),
        "daily_limit": None,
        "hourly_limit": None,
    }


def _default_models() -> dict[str, dict[str, Any]]:
    models: dict[str, dict[str, Any]] = {}
    for provider, _label, _base_url in PROVIDER_OPTIONS:
        for label, model_id in QUICK_MODEL_OPTIONS[provider]:
            key = _model_pk(provider, model_id)
            models.setdefault(
                key,
                {
                    "id": key,
                    "provider": provider,
                    "model_id": model_id,
                    "label": label,
                    "enabled": True,
                    "supports_quick": False,
                    "supports_deep": False,
                    "cost_tier": "medium",
                    "visible_to_roles": "admin,operator,viewer",
                    "daily_limit": None,
                    "weekly_limit": None,
                },
            )
            models[key]["supports_quick"] = True
        for label, model_id in DEEP_MODEL_OPTIONS[provider]:
            key = _model_pk(provider, model_id)
            models.setdefault(
                key,
                {
                    "id": key,
                    "provider": provider,
                    "model_id": model_id,
                    "label": label,
                    "enabled": True,
                    "supports_quick": False,
                    "supports_deep": False,
                    "cost_tier": "medium",
                    "visible_to_roles": "admin,operator,viewer",
                    "daily_limit": None,
                    "weekly_limit": None,
                },
            )
            models[key]["supports_deep"] = True
    return models


def _provider_key_status(config: dict[str, Any]) -> str:
    api_key_env = config.get("api_key_env")
    if not api_key_env:
        return "configured"
    return "configured" if os.environ.get(str(api_key_env)) else "missing"


def _provider_payload(db: Session, provider: str) -> dict[str, Any]:
    default = _default_provider(provider)
    row = db.get(LLMProviderConfig, provider)
    payload = (
        default
        if row is None
        else {
            "provider": row.provider,
            "label": row.label,
            "enabled": row.enabled,
            "base_url": row.base_url,
            "api_key_env": row.api_key_env,
            "daily_limit": row.daily_limit,
            "hourly_limit": row.hourly_limit,
        }
    )
    payload["key_status"] = _provider_key_status(payload)
    return payload


def _model_payload(db: Session, provider: str, model_id: str) -> dict[str, Any] | None:
    key = _model_pk(provider, model_id)
    row = db.get(LLMModelConfig, key)
    if row is None:
        return None
    return {
        "id": row.id,
        "provider": row.provider,
        "model_id": row.model_id,
        "label": row.label,
        "enabled": row.enabled,
        "supports_quick": row.supports_quick,
        "supports_deep": row.supports_deep,
        "cost_tier": row.cost_tier,
        "visible_to_roles": row.visible_to_roles,
        "daily_limit": row.daily_limit,
        "weekly_limit": row.weekly_limit,
    }


def _sum_usage(
    db: Session, provider: str, model_id: str, usage_date: str
) -> dict[str, Any]:
    row = db.execute(
        select(
            func.coalesce(func.sum(LLMModelUsage.total_calls), 0),
            func.coalesce(func.sum(LLMModelUsage.success_count), 0),
            func.coalesce(func.sum(LLMModelUsage.failure_count), 0),
            func.max(LLMModelUsage.last_called_at),
        ).where(
            LLMModelUsage.provider == provider,
            LLMModelUsage.model_id == model_id,
            LLMModelUsage.usage_date == usage_date,
        )
    ).one()
    return {
        "total_calls": int(row[0] or 0),
        "success_count": int(row[1] or 0),
        "failure_count": int(row[2] or 0),
        "last_called_at": row[3],
    }


def _sum_hour_usage(db: Session, provider: str, model_id: str, usage_date: str) -> int:
    hour_key = _utcnow().strftime("%Y-%m-%dT%H")
    value = db.scalar(
        select(func.coalesce(func.sum(LLMModelUsage.hour_total_calls), 0)).where(
            LLMModelUsage.provider == provider,
            LLMModelUsage.model_id == model_id,
            LLMModelUsage.usage_date == usage_date,
            LLMModelUsage.hour_key == hour_key,
        )
    )
    return int(value or 0)


def _sum_provider_usage(db: Session, provider: str, usage_date: str) -> int:
    value = db.scalar(
        select(func.coalesce(func.sum(LLMModelUsage.total_calls), 0)).where(
            LLMModelUsage.provider == provider,
            LLMModelUsage.usage_date == usage_date,
        )
    )
    return int(value or 0)


def _sum_provider_hour_usage(db: Session, provider: str, usage_date: str) -> int:
    hour_key = _utcnow().strftime("%Y-%m-%dT%H")
    value = db.scalar(
        select(func.coalesce(func.sum(LLMModelUsage.hour_total_calls), 0)).where(
            LLMModelUsage.provider == provider,
            LLMModelUsage.usage_date == usage_date,
            LLMModelUsage.hour_key == hour_key,
        )
    )
    return int(value or 0)


def _sum_model_week_usage(db: Session, provider: str, model_id: str) -> int:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    value = db.scalar(
        select(func.coalesce(func.sum(LLMModelUsage.total_calls), 0)).where(
            LLMModelUsage.provider == provider,
            LLMModelUsage.model_id == model_id,
            LLMModelUsage.usage_date >= week_start.isoformat(),
            LLMModelUsage.usage_date <= today.isoformat(),
        )
    )
    return int(value or 0)


def _model_summary(
    db: Session, model: dict[str, Any], usage_date: str
) -> dict[str, Any]:
    usage = _sum_usage(db, model["provider"], model["model_id"], usage_date)
    used_this_hour = _sum_hour_usage(
        db, model["provider"], model["model_id"], usage_date
    )
    daily_limit = model["daily_limit"]
    return {
        **model,
        "used_today": usage["total_calls"],
        "used_this_hour": used_this_hour,
        "remaining_today": None
        if daily_limit is None
        else max(daily_limit - usage["total_calls"], 0),
        "success_count": usage["success_count"],
        "failure_count": usage["failure_count"],
        "last_called_at": usage["last_called_at"].isoformat()
        if usage["last_called_at"]
        else None,
    }


def _default_profile_rows() -> list[dict[str, Any]]:
    return [
        {
            "profile_id": profile.value,
            "label": profile.label,
            "description": profile.description,
            "enabled": True,
            "default_for_roles": "admin,operator,viewer"
            if profile.value == "balanced"
            else "",
            "sort_order": index,
        }
        for index, profile in enumerate(STATIC_MODEL_PROFILES)
    ]


def _default_module_settings() -> dict[str, dict[str, Any]]:
    return {
        "trade_journal_review": {
            "module": "trade_journal_review",
            "label": "Trade Journal AI Review",
            "description": "Automatically generate entry and exit trade reviews after manual journal updates.",
            "enabled": False,
            "model_profile": "balanced",
            "output_language": "cn",
            "custom_provider": None,
            "custom_model": None,
            "openai_reasoning_effort": "medium",
            "google_thinking_level": "high",
        }
    }


def _default_ui_settings() -> dict[str, dict[str, Any]]:
    return {
        SHOW_CUSTOM_ANALYSIS_PROFILE_SETTING: {
            "setting_key": SHOW_CUSTOM_ANALYSIS_PROFILE_SETTING,
            "label": "Show Custom profile in analysis",
            "description": "Allow admins to choose a concrete provider and model from the new analysis dialog. Non-admin users never see this option.",
            "enabled": True,
        }
    }


def _default_routes(profile_id: str) -> list[ModelRoute]:
    for profile in STATIC_MODEL_PROFILES:
        if profile.value == profile_id:
            return list(profile.routes)
    return []


def _profile_routes_from_db(db: Session, profile_id: str) -> list[ModelRoute]:
    rows = db.scalars(
        select(LLMModelProfileRoute)
        .where(LLMModelProfileRoute.profile_id == profile_id)
        .where(LLMModelProfileRoute.enabled.is_(True))
        .order_by(
            LLMModelProfileRoute.route_order.asc(), LLMModelProfileRoute.mode.asc()
        )
    ).all()
    grouped: dict[int, dict[str, LLMModelProfileRoute]] = {}
    for row in rows:
        grouped.setdefault(row.route_order, {})[row.mode] = row

    routes: list[ModelRoute] = []
    for route_order in sorted(grouped):
        quick = grouped[route_order].get("quick")
        deep = grouped[route_order].get("deep")
        if quick is None or deep is None or quick.provider != deep.provider:
            continue
        routes.append(ModelRoute(quick.provider, quick.model_id, deep.model_id))
    return routes


def _seed_llm_model_defaults(db: Session) -> None:
    for provider, _label, _base_url in PROVIDER_OPTIONS:
        default = _default_provider(provider)
        row = db.get(LLMProviderConfig, provider)
        if row is None:
            db.add(LLMProviderConfig(**default))
        else:
            row.label = default["label"]
            row.api_key_env = default["api_key_env"]

    for default in _default_models().values():
        row = db.get(LLMModelConfig, default["id"])
        if row is None:
            db.add(LLMModelConfig(**default))
        else:
            row.provider = default["provider"]
            row.model_id = default["model_id"]
            row.label = default["label"]
            row.supports_quick = default["supports_quick"]
            row.supports_deep = default["supports_deep"]

    for default in _default_profile_rows():
        row = db.get(LLMModelProfile, default["profile_id"])
        if row is None:
            db.add(LLMModelProfile(**default))
        else:
            row.label = default["label"]
            row.description = default["description"]
            row.sort_order = default["sort_order"]

    existing_route_profiles = set(
        db.scalars(select(LLMModelProfileRoute.profile_id)).all()
    )
    for profile in STATIC_MODEL_PROFILES:
        if profile.value in existing_route_profiles:
            continue
        for index, route in enumerate(_default_routes(profile.value)):
            db.add(
                LLMModelProfileRoute(
                    profile_id=profile.value,
                    mode="quick",
                    route_order=index,
                    provider=route.provider,
                    model_id=route.quick_model,
                    enabled=True,
                )
            )
            db.add(
                LLMModelProfileRoute(
                    profile_id=profile.value,
                    mode="deep",
                    route_order=index,
                    provider=route.provider,
                    model_id=route.deep_model,
                    enabled=True,
                )
            )

    for module, default in _default_module_settings().items():
        if db.get(LLMModuleSetting, module) is None:
            db.add(
                LLMModuleSetting(
                    module=module,
                    enabled=default["enabled"],
                    model_profile=default["model_profile"],
                    output_language=default["output_language"],
                    custom_provider=default["custom_provider"],
                    custom_model=default["custom_model"],
                    openai_reasoning_effort=default["openai_reasoning_effort"],
                    google_thinking_level=default["google_thinking_level"],
                )
            )
    for setting_key, default in _default_ui_settings().items():
        if db.get(LLMUiSetting, setting_key) is None:
            db.add(
                LLMUiSetting(
                    setting_key=setting_key,
                    label=default["label"],
                    description=default["description"],
                    enabled=default["enabled"],
                )
            )


def ensure_llm_model_defaults() -> None:
    if not database_backed_llm_models_enabled():
        return
    with auth.db_session() as db:
        _seed_llm_model_defaults(db)


def _is_route_available(db: Session, route: ModelRoute) -> bool:
    provider = _provider_payload(db, route.provider)
    if not provider["enabled"] or provider["key_status"] != "configured":
        return False
    usage_date = _today_key()
    if (
        provider["daily_limit"] is not None
        and _sum_provider_usage(db, route.provider, usage_date)
        >= provider["daily_limit"]
    ):
        return False
    if (
        provider["hourly_limit"] is not None
        and _sum_provider_hour_usage(db, route.provider, usage_date)
        >= provider["hourly_limit"]
    ):
        return False
    for mode, model_id in (("quick", route.quick_model), ("deep", route.deep_model)):
        model = _model_payload(db, route.provider, model_id)
        if model is None or not model["enabled"]:
            return False
        if mode == "quick" and not model["supports_quick"]:
            return False
        if mode == "deep" and not model["supports_deep"]:
            return False
        if model["daily_limit"] is not None:
            usage = _sum_usage(db, route.provider, model_id, usage_date)
            if usage["total_calls"] >= model["daily_limit"]:
                return False
        if (
            model["weekly_limit"] is not None
            and _sum_model_week_usage(db, route.provider, model_id)
            >= model["weekly_limit"]
        ):
            return False
    return True


def resolve_model_profile_from_db(profile_id: str) -> ResolvedModelSelection:
    if not database_backed_llm_models_enabled():
        return resolve_model_profile(profile_id)

    ensure_llm_model_defaults()
    normalized = profile_id.strip().lower()
    with auth.db_session() as db:
        profile_row = db.get(LLMModelProfile, normalized)
        if profile_row is not None and not profile_row.enabled:
            raise ValueError(f"Model profile '{normalized}' is disabled")

        for route in _profile_routes_from_db(db, normalized):
            if _is_route_available(db, route):
                provider = _provider_payload(db, route.provider)
                return ResolvedModelSelection(
                    model_profile=normalized,
                    llm_provider=route.provider,
                    quick_think_llm=route.quick_model,
                    deep_think_llm=route.deep_model,
                    backend_url=str(
                        provider["base_url"] or get_provider_base_url(route.provider)
                    ),
                )

    raise ValueError(f"Model profile '{normalized}' has no available provider route")


def _module_setting_payload(
    row: LLMModuleSetting | None, module: str
) -> dict[str, Any]:
    defaults = _default_module_settings()[module]
    if row is None:
        return dict(defaults)
    return {
        **defaults,
        "enabled": row.enabled,
        "model_profile": row.model_profile,
        "output_language": row.output_language,
        "custom_provider": row.custom_provider,
        "custom_model": row.custom_model,
        "openai_reasoning_effort": row.openai_reasoning_effort,
        "google_thinking_level": row.google_thinking_level,
    }


def _ui_setting_payload(row: LLMUiSetting | None, setting_key: str) -> dict[str, Any]:
    defaults = _default_ui_settings()[setting_key]
    if row is None:
        return dict(defaults)
    return {
        "setting_key": row.setting_key,
        "label": row.label,
        "description": row.description,
        "enabled": row.enabled,
    }


def get_module_setting(module: str) -> dict[str, Any]:
    normalized = module.strip().lower()
    if normalized not in VALID_MODULE_SETTINGS:
        raise ValueError(f"Unknown LLM module setting '{module}'")
    if not database_backed_llm_models_enabled():
        return dict(_default_module_settings()[normalized])
    ensure_llm_model_defaults()
    with auth.db_session() as db:
        return _module_setting_payload(db.get(LLMModuleSetting, normalized), normalized)


def resolve_module_model_selection(module: str) -> dict[str, Any] | None:
    setting = get_module_setting(module)
    if not setting["enabled"]:
        return None
    profile = str(setting["model_profile"]).strip().lower()
    if profile == "custom":
        provider = str(setting.get("custom_provider") or "").strip().lower()
        model = str(setting.get("custom_model") or "").strip()
        if not provider or not model:
            raise ValueError("Custom module model settings require provider and model")
        return {
            "module": setting["module"],
            "model_profile": "custom",
            "llm_provider": provider,
            "model": model,
            "output_language": setting["output_language"],
            "openai_reasoning_effort": setting["openai_reasoning_effort"],
            "google_thinking_level": setting["google_thinking_level"],
        }
    resolved = (
        resolve_model_profile_from_db(profile)
        if database_backed_llm_models_enabled()
        else resolve_model_profile(profile)
    )
    return {
        "module": setting["module"],
        "model_profile": resolved.model_profile,
        "llm_provider": resolved.llm_provider,
        "model": resolved.deep_think_llm,
        "output_language": setting["output_language"],
        "openai_reasoning_effort": setting["openai_reasoning_effort"],
        "google_thinking_level": setting["google_thinking_level"],
    }


def ensure_model_selection_available(
    provider: str, quick_model: str, deep_model: str
) -> None:
    if not database_backed_llm_models_enabled():
        return
    ensure_llm_model_defaults()
    route = ModelRoute(
        provider.strip().lower(), quick_model.strip(), deep_model.strip()
    )
    with auth.db_session() as db:
        if not _is_route_available(db, route):
            raise ValueError(
                "Selected model route is disabled, missing credentials, or over its configured limit"
            )


def list_llm_model_summary() -> dict[str, Any]:
    if not database_backed_llm_models_enabled():
        return {
            "date": _today_key(),
            "providers": [],
            "models": [],
            "profiles": [],
            "module_settings": list(_default_module_settings().values()),
            "ui_settings": list(_default_ui_settings().values()),
        }

    ensure_llm_model_defaults()
    usage_date = _today_key()
    with auth.db_session() as db:
        models = []
        for row in db.scalars(
            select(LLMModelConfig).order_by(
                LLMModelConfig.provider.asc(), LLMModelConfig.model_id.asc()
            )
        ).all():
            payload = _model_payload(db, row.provider, row.model_id)
            if payload is not None:
                models.append(_model_summary(db, payload, usage_date))

        profiles = []
        for row in db.scalars(
            select(LLMModelProfile).order_by(
                LLMModelProfile.sort_order.asc(), LLMModelProfile.profile_id.asc()
            )
        ).all():
            profile = {
                "profile_id": row.profile_id,
                "label": row.label,
                "description": row.description,
                "enabled": row.enabled,
                "default_for_roles": row.default_for_roles,
                "sort_order": row.sort_order,
            }
            routes = _profile_routes_from_db(db, profile["profile_id"])
            profile["routes"] = [
                {
                    "route_order": index,
                    "provider": route.provider,
                    "quick_model": route.quick_model,
                    "deep_model": route.deep_model,
                    "available": _is_route_available(db, route),
                }
                for index, route in enumerate(routes)
            ]
            profiles.append(profile)

        return {
            "date": usage_date,
            "providers": [
                _provider_payload(db, provider)
                for provider in db.scalars(
                    select(LLMProviderConfig.provider).order_by(
                        LLMProviderConfig.provider.asc()
                    )
                ).all()
            ],
            "models": models,
            "profiles": sorted(profiles, key=lambda item: int(item["sort_order"])),
            "module_settings": [
                _module_setting_payload(db.get(LLMModuleSetting, module), module)
                for module in sorted(VALID_MODULE_SETTINGS)
            ],
            "ui_settings": [
                _ui_setting_payload(db.get(LLMUiSetting, setting_key), setting_key)
                for setting_key in sorted(VALID_UI_SETTINGS)
            ],
        }


def list_config_model_profiles(
    *,
    include_custom: bool = True,
) -> list[dict[str, object]]:
    if not database_backed_llm_models_enabled():
        options = list_model_profile_options()
        if include_custom:
            return options
        return [option for option in options if option.get("value") != "custom"]

    ensure_llm_model_defaults()
    with auth.db_session() as db:
        options: list[dict[str, object]] = []
        profile_rows = {
            row.profile_id: row for row in db.scalars(select(LLMModelProfile)).all()
        }
        for profile in STATIC_MODEL_PROFILES:
            row = profile_rows.get(profile.value)
            if row is not None and not row.enabled:
                option = serialize_model_profile(profile)
                option["enabled"] = False
                option["disabled_reason"] = "This model profile is disabled."
                options.append(option)
                continue
            route = next(
                (
                    candidate
                    for candidate in _profile_routes_from_db(db, profile.value)
                    if _is_route_available(db, candidate)
                ),
                None,
            )
            options.append(
                {
                    "label": row.label if row is not None else profile.label,
                    "value": profile.value,
                    "description": row.description
                    if row is not None
                    else profile.description,
                    "cost_tier": profile.cost_tier,
                    "enabled": route is not None,
                    "disabled_reason": None
                    if route is not None
                    else "No configured provider is available for this model profile.",
                    "default_provider": route.provider if route is not None else None,
                    "default_quick_model": route.quick_model
                    if route is not None
                    else None,
                    "default_deep_model": route.deep_model
                    if route is not None
                    else None,
                    "default_quick_label": route.quick_model
                    if route is not None
                    else None,
                    "default_deep_label": route.deep_model
                    if route is not None
                    else None,
                }
            )
        if include_custom:
            options.append(serialize_model_profile(get_model_profile("custom")))
        return options


def ui_setting_enabled(setting_key: str) -> bool:
    normalized = setting_key.strip().lower()
    if normalized not in VALID_UI_SETTINGS:
        raise ValueError(f"Unknown LLM UI setting '{setting_key}'")
    if not database_backed_llm_models_enabled():
        return bool(_default_ui_settings()[normalized]["enabled"])

    ensure_llm_model_defaults()
    with auth.db_session() as db:
        payload = _ui_setting_payload(db.get(LLMUiSetting, normalized), normalized)
        return bool(payload["enabled"])


def custom_analysis_profile_visible_for_role(role: str | None) -> bool:
    if not database_backed_llm_models_enabled():
        return True
    return role == auth.UserRole.ADMIN.value and ui_setting_enabled(
        SHOW_CUSTOM_ANALYSIS_PROFILE_SETTING
    )


def update_ui_setting(setting_key: str, *, enabled: bool) -> dict[str, Any]:
    normalized = setting_key.strip().lower()
    if normalized not in VALID_UI_SETTINGS:
        raise ValueError(f"Unknown LLM UI setting '{setting_key}'")
    if not database_backed_llm_models_enabled():
        return {
            **_default_ui_settings()[normalized],
            "enabled": enabled,
        }

    ensure_llm_model_defaults()
    with auth.db_session() as db:
        defaults = _default_ui_settings()[normalized]
        row = db.get(LLMUiSetting, normalized)
        if row is None:
            row = LLMUiSetting(
                setting_key=normalized,
                label=defaults["label"],
                description=defaults["description"],
            )
            db.add(row)
        row.enabled = enabled
        db.flush()
        return _ui_setting_payload(row, normalized)


def update_provider_config(
    provider: str,
    *,
    enabled: bool,
    base_url: str,
    daily_limit: int | None,
    hourly_limit: int | None,
) -> dict[str, Any]:
    provider_key = provider.strip().lower()
    default = _default_provider(provider_key)
    with auth.db_session() as db:
        row = db.get(LLMProviderConfig, provider_key)
        if row is None:
            row = LLMProviderConfig(
                provider=provider_key,
                label=default["label"],
                enabled=enabled,
                base_url=base_url.strip() or default["base_url"],
                api_key_env=default["api_key_env"],
                daily_limit=_normalize_limit(daily_limit, label="daily_limit"),
                hourly_limit=_normalize_limit(hourly_limit, label="hourly_limit"),
            )
            db.add(row)
        else:
            row.label = default["label"]
            row.enabled = enabled
            row.base_url = base_url.strip() or default["base_url"]
            row.api_key_env = default["api_key_env"]
            row.daily_limit = _normalize_limit(daily_limit, label="daily_limit")
            row.hourly_limit = _normalize_limit(hourly_limit, label="hourly_limit")
        db.flush()
        return _provider_payload(db, provider_key)


def update_model_config(
    provider: str,
    model_id: str,
    *,
    enabled: bool,
    cost_tier: str,
    visible_to_roles: list[str],
    daily_limit: int | None,
    weekly_limit: int | None,
) -> dict[str, Any]:
    provider_key = provider.strip().lower()
    model_key = model_id.strip()
    default = _default_models().get(_model_pk(provider_key, model_key))
    if default is None:
        raise ValueError(f"Unknown model '{model_id}' for provider '{provider}'")
    normalized_cost_tier = cost_tier.strip().lower()
    if normalized_cost_tier not in VALID_COST_TIERS:
        raise ValueError("cost_tier must be one of low, medium, high, or premium")
    roles = [role.strip().lower() for role in visible_to_roles if role.strip()]
    if any(role not in VALID_ROLES for role in roles):
        raise ValueError("visible_to_roles contains an unsupported role")
    with auth.db_session() as db:
        row = db.get(LLMModelConfig, default["id"])
        if row is None:
            row = LLMModelConfig(**default)
            db.add(row)
        row.enabled = enabled
        row.cost_tier = normalized_cost_tier
        row.visible_to_roles = ",".join(roles or sorted(VALID_ROLES))
        row.daily_limit = _normalize_limit(daily_limit, label="daily_limit")
        row.weekly_limit = _normalize_limit(weekly_limit, label="weekly_limit")
        db.flush()
        payload = _model_payload(db, provider_key, model_key)
        assert payload is not None
        return _model_summary(db, payload, _today_key())


def update_profile_config(
    profile_id: str,
    *,
    enabled: bool,
    default_for_roles: list[str],
) -> dict[str, Any]:
    normalized = profile_id.strip().lower()
    defaults = {row["profile_id"]: row for row in _default_profile_rows()}
    if normalized not in defaults:
        raise ValueError(f"Unknown model profile '{profile_id}'")
    roles = [role.strip().lower() for role in default_for_roles if role.strip()]
    if any(role not in VALID_ROLES for role in roles):
        raise ValueError("default_for_roles contains an unsupported role")
    ensure_llm_model_defaults()
    with auth.db_session() as db:
        row = db.get(LLMModelProfile, normalized)
        if row is None:
            row = LLMModelProfile(**defaults[normalized])
            db.add(row)
        row.enabled = enabled
        row.default_for_roles = ",".join(roles)
        db.flush()
        routes = _profile_routes_from_db(db, normalized)
        return {
            "profile_id": row.profile_id,
            "label": row.label,
            "description": row.description,
            "enabled": row.enabled,
            "default_for_roles": row.default_for_roles,
            "sort_order": row.sort_order,
            "routes": [
                {
                    "route_order": index,
                    "provider": route.provider,
                    "quick_model": route.quick_model,
                    "deep_model": route.deep_model,
                    "available": _is_route_available(db, route),
                }
                for index, route in enumerate(routes)
            ],
        }


def update_profile_routes(
    profile_id: str, routes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    normalized = profile_id.strip().lower()
    ensure_llm_model_defaults()
    with auth.db_session() as db:
        existing = db.scalars(
            select(LLMModelProfileRoute).where(
                LLMModelProfileRoute.profile_id == normalized
            )
        ).all()
        for row in existing:
            db.delete(row)
        for index, route in enumerate(routes):
            provider = str(route.get("provider", "")).strip().lower()
            quick_model = str(route.get("quick_model", "")).strip()
            deep_model = str(route.get("deep_model", "")).strip()
            if not provider or not quick_model or not deep_model:
                raise ValueError(
                    "Each route requires provider, quick_model, and deep_model"
                )
            if _model_payload(db, provider, quick_model) is None:
                raise ValueError(
                    f"Unknown quick model '{quick_model}' for provider '{provider}'"
                )
            if _model_payload(db, provider, deep_model) is None:
                raise ValueError(
                    f"Unknown deep model '{deep_model}' for provider '{provider}'"
                )
            db.add(
                LLMModelProfileRoute(
                    profile_id=normalized,
                    mode="quick",
                    route_order=index,
                    provider=provider,
                    model_id=quick_model,
                    enabled=True,
                )
            )
            db.add(
                LLMModelProfileRoute(
                    profile_id=normalized,
                    mode="deep",
                    route_order=index,
                    provider=provider,
                    model_id=deep_model,
                    enabled=True,
                )
            )
        db.flush()
        return [
            {
                "route_order": index,
                "provider": route.provider,
                "quick_model": route.quick_model,
                "deep_model": route.deep_model,
                "available": _is_route_available(db, route),
            }
            for index, route in enumerate(_profile_routes_from_db(db, normalized))
        ]


def update_module_setting(
    module: str,
    *,
    enabled: bool,
    model_profile: str,
    output_language: str,
    custom_provider: str | None = None,
    custom_model: str | None = None,
    openai_reasoning_effort: str | None,
    google_thinking_level: str | None,
) -> dict[str, Any]:
    normalized = module.strip().lower()
    if normalized not in VALID_MODULE_SETTINGS:
        raise ValueError(f"Unknown LLM module setting '{module}'")
    profile = model_profile.strip().lower()
    provider = custom_provider.strip().lower() if custom_provider else None
    model = custom_model.strip() if custom_model else None
    if profile == "custom":
        if not provider or not model:
            raise ValueError("Custom module model settings require provider and model")
    else:
        provider = None
        model = None
        try:
            get_model_profile(profile)
        except KeyError as exc:
            raise ValueError(f"Unknown model profile '{model_profile}'") from exc
    language = output_language.strip().lower()
    if language not in VALID_OUTPUT_LANGUAGES:
        raise ValueError("output_language must be en or cn")
    openai_effort = (
        openai_reasoning_effort.strip().lower() if openai_reasoning_effort else None
    )
    if (
        openai_effort is not None
        and openai_effort not in VALID_OPENAI_REASONING_EFFORTS
    ):
        raise ValueError("openai_reasoning_effort must be low, medium, or high")
    google_level = (
        google_thinking_level.strip().lower() if google_thinking_level else None
    )
    if google_level is not None and google_level not in VALID_GOOGLE_THINKING_LEVELS:
        raise ValueError("google_thinking_level must be high or minimal")

    if not database_backed_llm_models_enabled():
        return {
            **_default_module_settings()[normalized],
            "enabled": enabled,
            "model_profile": profile,
            "output_language": language,
            "custom_provider": provider,
            "custom_model": model,
            "openai_reasoning_effort": openai_effort,
            "google_thinking_level": google_level,
        }

    ensure_llm_model_defaults()
    with auth.db_session() as db:
        if profile == "custom":
            model_payload = _model_payload(db, provider or "", model or "")
            if model_payload is None:
                raise ValueError(f"Unknown model '{model}' for provider '{provider}'")
            if not model_payload["supports_deep"]:
                raise ValueError("Custom module model must support deep analysis")
        row = db.get(LLMModuleSetting, normalized)
        if row is None:
            row = LLMModuleSetting(module=normalized)
            db.add(row)
        row.enabled = enabled
        row.model_profile = profile
        row.output_language = language
        row.custom_provider = provider
        row.custom_model = model
        row.openai_reasoning_effort = openai_effort
        row.google_thinking_level = google_level
        db.flush()
        return _module_setting_payload(row, normalized)


def record_model_usage(
    provider: str,
    model_id: str,
    *,
    module: str,
    success: bool = True,
) -> None:
    if not database_backed_llm_models_enabled():
        return
    usage_date = _today_key()
    now = _utcnow()
    hour_key = now.strftime("%Y-%m-%dT%H")
    with auth.db_session() as db:
        dialect_name = db.get_bind().dialect.name
        if dialect_name in {"postgresql", "sqlite"}:
            table = LLMModelUsage.__table__
            insert_factory = (
                postgresql.insert if dialect_name == "postgresql" else sqlite.insert
            )
            statement = insert_factory(table).values(
                usage_date=usage_date,
                provider=provider,
                model_id=model_id,
                module=module,
                total_calls=1,
                success_count=1 if success else 0,
                failure_count=0 if success else 1,
                hour_key=hour_key,
                hour_total_calls=1,
                last_called_at=now,
                updated_at=now,
            )
            db.execute(
                statement.on_conflict_do_update(
                    index_elements=["usage_date", "provider", "model_id", "module"],
                    set_={
                        "total_calls": table.c.total_calls + 1,
                        "success_count": table.c.success_count
                        + (1 if success else 0),
                        "failure_count": table.c.failure_count
                        + (0 if success else 1),
                        "hour_key": hour_key,
                        "hour_total_calls": case(
                            (
                                table.c.hour_key == hour_key,
                                table.c.hour_total_calls + 1,
                            ),
                            else_=1,
                        ),
                        "last_called_at": now,
                        "updated_at": now,
                    },
                )
            )
            db.flush()
            return

        row = db.get(LLMModelUsage, (usage_date, provider, model_id, module))
        if row is None:
            row = LLMModelUsage(
                usage_date=usage_date,
                provider=provider,
                model_id=model_id,
                module=module,
                total_calls=0,
                success_count=0,
                failure_count=0,
                hour_key=hour_key,
                hour_total_calls=0,
            )
            db.add(row)
        if row.hour_key != hour_key:
            row.hour_key = hour_key
            row.hour_total_calls = 0
        row.total_calls += 1
        row.hour_total_calls += 1
        row.last_called_at = now
        if success:
            row.success_count += 1
        else:
            row.failure_count += 1
        row.updated_at = now
        db.flush()
