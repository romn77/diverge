from __future__ import annotations

from typing import Any

from web.backend import app_config

DATA_SYNC_US_MANIFEST_ERROR = (
    "US data sync requires a manifest at DATA_DIR/manifest/us.csv "
    "or SCREEN_US_MANIFEST_PATH."
)


def build_ohlcv_config_payload(
    payload: dict[str, Any],
    *,
    us_manifest_error: str = DATA_SYNC_US_MANIFEST_ERROR,
) -> dict[str, Any]:
    top_k = int(payload.get("top_k") or 100)
    config_payload = {
        "markets": payload["markets"],
        "as_of_date": payload["as_of_date"],
        "top_k": min(max(top_k, 1), 100),
        "output_dir": str(app_config.SCREENER_RESULTS_DIR),
        "cache_dir": str(app_config.SCREENER_CACHE_DIR),
        "history_dir": str(app_config.STOCK_HISTORY_DIR),
        "cn_data_source": payload.get("cn_data_source") or "tushare",
        "cn_data_source_fallbacks": payload.get("cn_data_source_fallbacks") or [],
        "us_data_source": payload.get("us_data_source") or "yfinance",
        "us_data_source_fallbacks": payload.get("us_data_source_fallbacks") or [],
        "cn_manifest_path": payload.get("cn_manifest_path"),
        "us_manifest_path": payload.get("us_manifest_path"),
    }
    if "cn" in payload["markets"] and not config_payload["cn_manifest_path"]:
        manifest_path = app_config.resolve_manifest_path(
            "cn", app_config.PROJECT_ROOT, require_exists=True
        )
        config_payload["cn_manifest_path"] = (
            str(manifest_path) if manifest_path else None
        )
    if "us" in payload["markets"] and not config_payload["us_manifest_path"]:
        manifest_path = app_config.resolve_manifest_path(
            "us", app_config.PROJECT_ROOT, require_exists=True
        )
        if not manifest_path:
            raise RuntimeError(us_manifest_error)
        config_payload["us_manifest_path"] = (
            str(manifest_path) if manifest_path else None
        )
    return config_payload
