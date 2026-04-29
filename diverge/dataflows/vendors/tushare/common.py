from __future__ import annotations

import os

from ...config import get_config
from ...vendor_errors import VendorAuthError, VendorRetryableError


def get_tushare_pro_client():
    try:
        import tushare as ts
    except ModuleNotFoundError as exc:
        raise VendorAuthError(
            "tushare is not installed. Add the dependency before using CN vendors."
        ) from exc

    config = get_config()
    token = config.get("tushare_token") or os.getenv("TUSHARE_TOKEN")
    if not token:
        raise VendorAuthError("TUSHARE_TOKEN is not configured.")

    try:
        ts.set_token(token)
        return ts.pro_api(token)
    except Exception as exc:
        raise VendorRetryableError(f"Failed to initialize tushare client: {exc}") from exc


def to_tushare_date(value: str) -> str:
    return value.replace("-", "")
