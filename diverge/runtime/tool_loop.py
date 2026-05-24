from __future__ import annotations

import json
import re
from typing import Any

from diverge.common.dates import days_before_or_original
from diverge.common.market_calendar import last_n_trading_days
from diverge.common.symbols import resolve_symbol_market


DEFAULT_STOCK_DATA_TRADING_DAYS = 90
DEFAULT_STOCK_DATA_CALENDAR_FALLBACK_DAYS = 126
TOOL_INVOCATION_RE = re.compile(
    r"\b(?:get_stock_data|get_indicators|get_news|get_global_news|"
    r"get_fundamentals|get_balance_sheet|get_cashflow|get_income_statement|"
    r"get_insider_transactions|web_search_evidence)\s*\(",
    re.IGNORECASE,
)


def normalize_tool_args(args: Any) -> dict[str, Any]:
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def contextual_tool_args(
    state: dict[str, Any],
    tool_name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(args)
    ticker = str(state.get("company_of_interest") or "").strip().upper()
    trade_date = str(state.get("trade_date") or "").strip()

    if tool_name in {
        "get_news",
        "get_fundamentals",
        "get_balance_sheet",
        "get_cashflow",
        "get_income_statement",
        "get_insider_transactions",
    }:
        if "ticker" not in normalized and "symbol" in normalized:
            normalized["ticker"] = normalized["symbol"]
        if "ticker" not in normalized and ticker:
            normalized["ticker"] = ticker

    if tool_name in {"get_stock_data", "get_indicators"}:
        if "symbol" not in normalized and "ticker" in normalized:
            normalized["symbol"] = normalized["ticker"]
        if "symbol" not in normalized and ticker:
            normalized["symbol"] = ticker

    if tool_name == "get_news" and trade_date:
        normalized.setdefault("end_date", trade_date)
        normalized.setdefault("start_date", date_days_before(trade_date, 7))

    if tool_name == "get_stock_data":
        if trade_date:
            normalized.setdefault("end_date", trade_date)
        end_date = str(normalized.get("end_date") or "").strip()
        if "start_date" not in normalized and end_date:
            symbol = str(normalized.get("symbol") or ticker).strip()
            normalized["start_date"] = stock_data_start_date(symbol, end_date)

    if tool_name == "get_global_news" and trade_date:
        normalized.setdefault("curr_date", trade_date)

    if tool_name == "get_indicators" and trade_date:
        normalized.setdefault("curr_date", trade_date)

    return normalized


def date_days_before(date_text: str, days: int) -> str:
    return days_before_or_original(date_text, days)


def stock_data_start_date(symbol: str, end_date: str) -> str:
    market = "us"
    if symbol:
        try:
            market = resolve_symbol_market(symbol)
        except ValueError:
            market = "us"
    trading_days = last_n_trading_days(
        market,
        end_date,
        DEFAULT_STOCK_DATA_TRADING_DAYS,
    )
    if trading_days:
        return trading_days[0].isoformat()
    return days_before_or_original(end_date, DEFAULT_STOCK_DATA_CALENDAR_FALLBACK_DAYS)


def looks_like_incomplete_tool_preface(message: Any) -> bool:
    content = str(getattr(message, "content", "") or "").strip()
    if not content or "json-highlights" in content:
        return False

    lowered = content.lower()
    if TOOL_INVOCATION_RE.search(content):
        tool_preface_markers = (
            "call",
            "calling",
            "tool",
            "first",
            "retrieve",
            "gather",
            "calculate",
            "调用",
            "工具",
            "获取",
            "计算",
            "指标",
            "首先",
            "然后",
            "我将",
            "我会",
            "我们需要",
            "需要先",
            "开始调用",
        )
        if any(marker in lowered for marker in tool_preface_markers):
            return True

    if len(content) > 800:
        return False

    intent_markers = (
        "i'll",
        "i’ll",
        "i will",
        "let me",
        "i need to",
        "first pull",
        "first retrieve",
        "first gather",
        "我将",
        "我会",
        "我们需要",
        "需要先",
        "先调用",
        "开始调用",
    )
    tool_markers = (
        "tool",
        "get_",
        "pull",
        "retrieve",
        "gather",
        "calculate",
        "调用",
        "工具",
        "获取",
        "计算",
        "指标",
    )
    return any(marker in lowered for marker in intent_markers) and any(
        marker in lowered for marker in tool_markers
    )
