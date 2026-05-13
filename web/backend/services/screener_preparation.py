from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from diverge.dataflows.routes import dual_market_history_source_kwargs
from diverge.screener.schema import ScreenRunConfig
from web.backend import app_config, screener_results
from web.backend.runtime import data_sync_tasks

DEFAULT_US_MANIFEST_ERROR = (
    "US screening requires a manifest at DATA_DIR/manifest/us.csv. "
    "SCREEN_US_MANIFEST_PATH remains available as a compatibility override."
)


class ScreenerPreparationError(ValueError):
    """Raised when a screener request cannot be prepared for execution."""


@dataclass(slots=True)
class PreparedScreenerRun:
    request_payload: dict[str, Any]
    config_payload: dict[str, Any]
    screener_key: str
    cached_run_id: str | None = None

    @property
    def cached(self) -> bool:
        return self.cached_run_id is not None


DataSourceResolver = Callable[[list[str]], dict[str, object]]
AsOfDateResolver = Callable[[list[str], dict[str, Any]], str]


def resolve_screener_data_sources(markets: list[str]) -> dict[str, object]:
    return dual_market_history_source_kwargs(module="screener")


def resolve_screener_as_of_date(
    markets: list[str], data_sources: dict[str, Any] | None = None
) -> str:
    sources = data_sources or {}
    trading_days = []
    for market in markets:
        normalized_market = str(market).strip().lower()
        source = (
            str(sources.get("cn_data_source") or "tushare")
            if normalized_market == "cn"
            else str(sources.get("us_data_source") or "massive")
        )
        trading_days.append(
            data_sync_tasks.resolve_latest_ready_trading_day(
                normalized_market,
                source,
            )
        )
    if not trading_days:
        raise ScreenerPreparationError("Unable to resolve screener trading date.")
    return min(trading_days).isoformat()


def _markets_from_payload(payload: dict[str, Any]) -> list[str]:
    return [str(market).strip().lower() for market in payload.get("markets") or []]


def _inject_manifest_paths(
    config_payload: dict[str, Any],
    *,
    us_manifest_error: str,
) -> None:
    markets = _markets_from_payload(config_payload)
    if "cn" in markets:
        manifest_path = app_config.resolve_manifest_path(
            "cn", app_config.PROJECT_ROOT, require_exists=True
        )
        if manifest_path:
            config_payload["cn_manifest_path"] = str(manifest_path)
    if "us" in markets:
        manifest_path = app_config.resolve_manifest_path(
            "us",
            app_config.PROJECT_ROOT,
            require_exists=True,
        )
        if not manifest_path:
            raise ScreenerPreparationError(us_manifest_error)
        config_payload["us_manifest_path"] = str(manifest_path)


def build_screener_config_payload(
    request_payload: dict[str, Any],
    *,
    data_sources: dict[str, object] | None = None,
    data_source_resolver: DataSourceResolver = resolve_screener_data_sources,
    us_manifest_error: str = DEFAULT_US_MANIFEST_ERROR,
) -> dict[str, Any]:
    config_payload = dict(request_payload)
    resolved_sources = data_sources
    if resolved_sources is None:
        resolved_sources = data_source_resolver(_markets_from_payload(config_payload))
    config_payload.update(resolved_sources)
    config_payload["output_dir"] = str(app_config.SCREENER_RESULTS_DIR)
    config_payload["cache_dir"] = str(app_config.SCREENER_CACHE_DIR)
    config_payload["history_dir"] = str(app_config.STOCK_HISTORY_DIR)
    config_payload["fundamental_dir"] = str(app_config.FUNDAMENTALS_DIR)
    _inject_manifest_paths(config_payload, us_manifest_error=us_manifest_error)

    try:
        ScreenRunConfig(**config_payload)
    except ValueError as exc:
        raise ScreenerPreparationError(str(exc)) from exc
    return config_payload


def prepare_screener_run(
    raw_payload: dict[str, Any],
    *,
    data_source_resolver: DataSourceResolver = resolve_screener_data_sources,
    as_of_date_resolver: AsOfDateResolver = resolve_screener_as_of_date,
    us_manifest_error: str = DEFAULT_US_MANIFEST_ERROR,
) -> PreparedScreenerRun:
    request_payload = dict(raw_payload)
    request_payload["history_cache_policy"] = "cache_only"
    data_sources = data_source_resolver(_markets_from_payload(request_payload))
    request_payload.update(data_sources)
    if not request_payload.get("as_of_date"):
        request_payload["as_of_date"] = as_of_date_resolver(
            _markets_from_payload(request_payload),
            request_payload,
        )

    config_payload = build_screener_config_payload(
        request_payload,
        data_sources=data_sources,
        us_manifest_error=us_manifest_error,
    )
    screener_key = screener_results.screener_key_for_config(config_payload)
    request_payload["screener_key"] = screener_key
    cached_snapshot = screener_results.get_cached_screener_result(config_payload)
    return PreparedScreenerRun(
        request_payload=request_payload,
        config_payload=config_payload,
        screener_key=screener_key,
        cached_run_id=(
            cached_snapshot.source_run_id if cached_snapshot is not None else None
        ),
    )
