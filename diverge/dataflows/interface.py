from .vendors.akshare import (
    get_stock as get_akshare_stock,
    get_indicator as get_akshare_indicator,
    get_fundamentals as get_akshare_fundamentals,
    get_balance_sheet as get_akshare_balance_sheet,
    get_cashflow as get_akshare_cashflow,
    get_income_statement as get_akshare_income_statement,
    get_insider_transactions as get_akshare_insider_transactions,
    get_news as get_akshare_news,
    get_global_news as get_akshare_global_news,
)
from .vendors.alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_latest_price as get_alpha_vantage_latest_price,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)
from .vendors.massive import get_stock as get_massive_stock
from .vendors.local.analysis_market_data import get_local_indicator
from .vendors.fmp.fundamentals import (
    get_fundamentals as get_fmp_fundamentals,
    get_balance_sheet as get_fmp_balance_sheet,
    get_cashflow as get_fmp_cashflow,
    get_income_statement as get_fmp_income_statement,
)
from .vendors.fmp.news import (
    get_news as get_fmp_news,
    get_global_news as get_fmp_global_news,
    get_insider_transactions as get_fmp_insider_transactions,
)
from .vendors.alpha_vantage.common import AlphaVantageRateLimitError
from .cn_market_utils import detect_market, normalize_symbol_for_vendor
from .config import get_config
from .fundamentals_normalizer import normalize_fundamentals_payload
from .vendors.tushare import (
    get_stock as get_tushare_stock,
    get_indicator as get_tushare_indicator,
    get_fundamentals as get_tushare_fundamentals,
    get_balance_sheet as get_tushare_balance_sheet,
    get_cashflow as get_tushare_cashflow,
    get_income_statement as get_tushare_income_statement,
    get_insider_transactions as get_tushare_insider_transactions,
    get_news as get_tushare_news,
    get_global_news as get_tushare_global_news,
)
from .vendors.yfinance.stock import (
    get_YFin_data_online,
    get_latest_price as get_yfinance_latest_price,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .vendors.yfinance.news import get_news_yfinance, get_global_news_yfinance
from .vendor_errors import (
    VendorAuthError,
    VendorDataEmptyError,
    VendorNotSupportedError,
    VendorRetryableError,
)
from . import vendor_usage

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": ["get_stock_data", "get_latest_price"],
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": ["get_indicators"],
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement",
        ],
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ],
    },
}

VENDOR_LIST = [
    "local",
    "akshare",
    "tushare",
    "fmp",
    "yfinance",
    "alpha_vantage",
    "massive",
]

MARKET_VENDOR_ALLOWLIST = {
    "cn": {"local", "akshare", "tushare", "yfinance"},
    "us": {"local", "fmp", "yfinance", "alpha_vantage", "massive"},
    "global": {"yfinance", "alpha_vantage", "fmp"},
}

METHOD_ARG_SCHEMA = {
    "get_stock_data": {"symbol_arg": "symbol", "pos": 0},
    "get_latest_price": {"symbol_arg": "symbol", "pos": 0},
    "get_indicators": {"symbol_arg": "symbol", "pos": 0},
    "get_fundamentals": {"symbol_arg": "ticker", "pos": 0},
    "get_balance_sheet": {"symbol_arg": "ticker", "pos": 0},
    "get_cashflow": {"symbol_arg": "ticker", "pos": 0},
    "get_income_statement": {"symbol_arg": "ticker", "pos": 0},
    "get_news": {"symbol_arg": "ticker", "pos": 0},
    "get_insider_transactions": {"symbol_arg": "ticker", "pos": 0},
    "get_global_news": {"symbol_arg": None, "pos": None},
}

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "akshare": get_akshare_stock,
        "tushare": get_tushare_stock,
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "massive": get_massive_stock,
    },
    "get_latest_price": {
        "alpha_vantage": get_alpha_vantage_latest_price,
        "yfinance": get_yfinance_latest_price,
    },
    # technical_indicators
    "get_indicators": {
        "local": get_local_indicator,
        "akshare": get_akshare_indicator,
        "tushare": get_tushare_indicator,
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "akshare": get_akshare_fundamentals,
        "tushare": get_tushare_fundamentals,
        "fmp": get_fmp_fundamentals,
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "akshare": get_akshare_balance_sheet,
        "tushare": get_tushare_balance_sheet,
        "fmp": get_fmp_balance_sheet,
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "akshare": get_akshare_cashflow,
        "tushare": get_tushare_cashflow,
        "fmp": get_fmp_cashflow,
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "akshare": get_akshare_income_statement,
        "tushare": get_tushare_income_statement,
        "fmp": get_fmp_income_statement,
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "akshare": get_akshare_news,
        "tushare": get_tushare_news,
        "fmp": get_fmp_news,
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "akshare": get_akshare_global_news,
        "tushare": get_tushare_global_news,
        "fmp": get_fmp_global_news,
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "akshare": get_akshare_insider_transactions,
        "tushare": get_tushare_insider_transactions,
        "fmp": get_fmp_insider_transactions,
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
}


def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")


FALLBACK_ERRORS = (
    VendorRetryableError,
    VendorAuthError,
    VendorNotSupportedError,
    VendorDataEmptyError,
    AlphaVantageRateLimitError,
)


def get_vendor(category: str, method: str | None = None, market: str = "global") -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    route_vendors = vendor_usage.get_data_source_route(
        category=category,
        market=market,
    )
    if route_vendors:
        return ",".join(route_vendors)

    market_overrides = config.get("market_overrides", {})
    if market in market_overrides:
        market_vendors = market_overrides[market]
        if category in market_vendors:
            return market_vendors[category]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")


def _extract_symbol(method: str, args, kwargs):
    schema = METHOD_ARG_SCHEMA.get(method)
    if not schema or schema["symbol_arg"] is None:
        return None

    arg_name = schema["symbol_arg"]
    if arg_name in kwargs and kwargs[arg_name]:
        return kwargs[arg_name]

    pos = schema["pos"]
    if pos is not None and len(args) > pos:
        return args[pos]

    return None


def _normalize_legacy_vendor_result(result: str, vendor: str, method: str) -> str:
    trimmed = result.strip()
    lowered = trimmed.lower()

    if lowered.startswith("error:"):
        raise VendorRetryableError(
            f"Legacy vendor error string from {vendor} for {method}: {trimmed}"
        )
    if lowered.startswith("error "):
        error_hints = (
            "fail",
            "failure",
            "unavailable",
            "timeout",
            "rate limit",
            "exception",
            "network",
            "invalid",
        )
        if any(hint in lowered for hint in error_hints):
            raise VendorRetryableError(
                f"Legacy vendor error string from {vendor} for {method}: {trimmed}"
            )
    if lowered.startswith("no data found"):
        raise VendorDataEmptyError(
            f"Legacy vendor empty-data string from {vendor} for {method}: {trimmed}"
        )
    return result


def _replace_symbol(method: str, args, kwargs, new_symbol: str):
    schema = METHOD_ARG_SCHEMA.get(method)
    if not schema or schema["symbol_arg"] is None:
        return args, kwargs

    arg_name = schema["symbol_arg"]
    updated_args = list(args)
    updated_kwargs = dict(kwargs)

    if arg_name in updated_kwargs:
        updated_kwargs[arg_name] = new_symbol
    else:
        pos = schema["pos"]
        if pos is not None and len(updated_args) > pos:
            updated_args[pos] = new_symbol

    return tuple(updated_args), updated_kwargs


def resolve_market_and_symbol(method: str, args, kwargs):
    config = get_config()
    forced_market = config.get("market", "auto")
    symbol = _extract_symbol(method, args, kwargs)

    if METHOD_ARG_SCHEMA.get(method, {}).get("symbol_arg") is None:
        market = "global"
        return market, args, kwargs

    if not symbol:
        market = forced_market if forced_market in {"cn", "us"} else "us"
        return market, args, kwargs

    if forced_market in {"cn", "us"}:
        return forced_market, args, kwargs

    market = detect_market(symbol)
    if market == "unknown":
        market = "us"

    return market, args, kwargs


def build_vendor_chain(method: str, market: str):
    category = get_category_for_method(method)
    allowed_vendors = MARKET_VENDOR_ALLOWLIST.get(
        market, set(VENDOR_METHODS[method].keys())
    )
    method_supported_vendors = list(VENDOR_METHODS[method].keys())
    all_available_vendors = [
        vendor for vendor in method_supported_vendors if vendor in allowed_vendors
    ]
    route_vendors = vendor_usage.get_data_source_route(
        category=category,
        market=market,
    )
    if route_vendors:
        return [vendor for vendor in route_vendors if vendor in all_available_vendors]

    vendor_config = get_vendor(category, method, market)
    primary_vendors = [
        vendor.strip() for vendor in vendor_config.split(",") if vendor.strip()
    ]

    fallback_vendors = []
    for vendor in primary_vendors + all_available_vendors:
        if vendor in all_available_vendors and vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    return fallback_vendors


def execute_vendor_chain(
    method: str,
    market: str,
    symbol,
    resolved_args,
    resolved_kwargs,
    vendors,
    vendor_methods=None,
):
    method_vendor_map = vendor_methods or VENDOR_METHODS
    last_error = None
    attempted_vendors = []

    for vendor in vendors:
        if vendor not in method_vendor_map[method]:
            continue

        quota = vendor_usage.acquire_data_source_quota(vendor)
        if not quota.acquired:
            last_error = (
                vendor_usage.QuotaWaitRequired(
                    vendor=quota.vendor,
                    reason=quota.reason or "Data source quota exhausted.",
                    blocked_until=quota.blocked_until,
                )
                if quota.retryable
                else VendorRetryableError(
                    quota.reason
                    or f"Data source '{vendor}' is disabled or unavailable."
                )
            )
            continue

        attempted_vendors.append(vendor)

        vendor_args = resolved_args
        vendor_kwargs = resolved_kwargs
        if symbol and market == "cn":
            try:
                vendor_symbol = normalize_symbol_for_vendor(symbol, market, vendor)
                vendor_args, vendor_kwargs = _replace_symbol(
                    method,
                    resolved_args,
                    resolved_kwargs,
                    vendor_symbol,
                )
            except ValueError:
                vendor_args, vendor_kwargs = resolved_args, resolved_kwargs

        vendor_impl = method_vendor_map[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            result = impl_func(*vendor_args, **vendor_kwargs)
        except FALLBACK_ERRORS as exc:
            try:
                vendor_usage.record_data_source_call(vendor, success=False)
            finally:
                vendor_usage.release_data_source_quota(quota)
            last_error = exc
            continue
        except Exception:
            try:
                vendor_usage.record_data_source_call(vendor, success=False)
            finally:
                vendor_usage.release_data_source_quota(quota)
            raise
        else:
            if isinstance(result, str):
                try:
                    normalized_result = _normalize_legacy_vendor_result(
                        result,
                        vendor,
                        method,
                    )
                except FALLBACK_ERRORS as exc:
                    try:
                        vendor_usage.record_data_source_call(vendor, success=False)
                    finally:
                        vendor_usage.release_data_source_quota(quota)
                    last_error = exc
                    continue
                try:
                    vendor_usage.record_data_source_call(vendor, success=True)
                finally:
                    vendor_usage.release_data_source_quota(quota)
                return normalized_result
            try:
                vendor_usage.record_data_source_call(vendor, success=True)
            finally:
                vendor_usage.release_data_source_quota(quota)
            return result

    if isinstance(last_error, vendor_usage.QuotaWaitRequired):
        raise last_error

    if last_error is not None:
        raise RuntimeError(
            f"No available vendor for '{method}' in market '{market}'. "
            f"Attempted vendors: {', '.join(attempted_vendors)}"
        ) from last_error

    raise RuntimeError(
        f"No available vendor for '{method}' in market '{market}'. "
        f"Attempted vendors: {', '.join(attempted_vendors)}"
    )


def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    market, resolved_args, resolved_kwargs = resolve_market_and_symbol(
        method, args, kwargs
    )
    symbol = _extract_symbol(method, resolved_args, resolved_kwargs)
    vendors = build_vendor_chain(method, market)

    return execute_vendor_chain(
        method=method,
        market=market,
        symbol=symbol,
        resolved_args=resolved_args,
        resolved_kwargs=resolved_kwargs,
        vendors=vendors,
    )


def route_to_normalized_fundamentals(
    ticker: str,
    curr_date: str | None = None,
    freq: str = "quarterly",
):
    market, _, _ = resolve_market_and_symbol(
        "get_fundamentals", (ticker, curr_date), {}
    )
    raw_payload = {
        "fundamentals": route_to_vendor("get_fundamentals", ticker, curr_date),
        "balance_sheet": route_to_vendor("get_balance_sheet", ticker, freq, curr_date),
        "cashflow": route_to_vendor("get_cashflow", ticker, freq, curr_date),
        "income_statement": route_to_vendor(
            "get_income_statement",
            ticker,
            freq,
            curr_date,
        ),
    }

    return normalize_fundamentals_payload(
        raw_payload,
        market=market,
        ticker=ticker,
        frequency=freq,
    )
