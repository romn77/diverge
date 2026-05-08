from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Optional

from google.adk.tools import FunctionTool

from diverge.agents.utils.core_stock_tools import get_stock_data as _lc_get_stock_data
from diverge.agents.utils.fundamental_data_tools import (
    get_balance_sheet as _lc_get_balance_sheet,
    get_cashflow as _lc_get_cashflow,
    get_fundamentals as _lc_get_fundamentals,
    get_income_statement as _lc_get_income_statement,
)
from diverge.agents.utils.news_data_tools import (
    get_global_news as _lc_get_global_news,
    get_insider_transactions as _lc_get_insider_transactions,
    get_news as _lc_get_news,
)
from diverge.agents.utils.search_tools import (
    web_search_evidence as _lc_web_search_evidence,
)
from diverge.agents.utils.technical_indicators_tools import (
    get_indicators as _lc_get_indicators,
)


def _invoke_legacy_tool(tool: Any, arguments: dict[str, Any]) -> str:
    if hasattr(tool, "invoke"):
        return str(tool.invoke(arguments))
    if hasattr(tool, "func") and callable(tool.func):
        return str(tool.func(**arguments))
    if callable(tool):
        return str(tool(**arguments))
    raise TypeError(f"Unsupported tool object: {tool!r}")


def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve stock price data (OHLCV) for a ticker and date range."""
    return _invoke_legacy_tool(
        _lc_get_stock_data,
        {"symbol": symbol, "start_date": start_date, "end_date": end_date},
    )


def get_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator name"],
    curr_date: Annotated[str, "Current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "How many days to look back"] = 30,
) -> str:
    """Retrieve one or more technical indicators for a ticker."""
    return _invoke_legacy_tool(
        _lc_get_indicators,
        {
            "symbol": symbol,
            "indicator": indicator,
            "curr_date": curr_date,
            "look_back_days": look_back_days,
        },
    )


def get_fundamentals(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    """Retrieve comprehensive fundamental data for a ticker."""
    return _invoke_legacy_tool(
        _lc_get_fundamentals,
        {"ticker": ticker, "curr_date": curr_date},
    )


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[
        Optional[str], "current date you are trading at, yyyy-mm-dd"
    ] = None,
) -> str:
    """Retrieve balance sheet data for a ticker."""
    return _invoke_legacy_tool(
        _lc_get_balance_sheet,
        {"ticker": ticker, "freq": freq, "curr_date": curr_date},
    )


def get_cashflow(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[
        Optional[str], "current date you are trading at, yyyy-mm-dd"
    ] = None,
) -> str:
    """Retrieve cash flow statement data for a ticker."""
    return _invoke_legacy_tool(
        _lc_get_cashflow,
        {"ticker": ticker, "freq": freq, "curr_date": curr_date},
    )


def get_income_statement(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[
        Optional[str], "current date you are trading at, yyyy-mm-dd"
    ] = None,
) -> str:
    """Retrieve income statement data for a ticker."""
    return _invoke_legacy_tool(
        _lc_get_income_statement,
        {"ticker": ticker, "freq": freq, "curr_date": curr_date},
    )


def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve news data for a ticker and date range."""
    return _invoke_legacy_tool(
        _lc_get_news,
        {"ticker": ticker, "start_date": start_date, "end_date": end_date},
    )


def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 5,
) -> str:
    """Retrieve global macro and market news data."""
    return _invoke_legacy_tool(
        _lc_get_global_news,
        {
            "curr_date": curr_date,
            "look_back_days": look_back_days,
            "limit": limit,
        },
    )


def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Retrieve insider transaction information for a ticker."""
    return _invoke_legacy_tool(
        _lc_get_insider_transactions,
        {"ticker": ticker},
    )


def web_search_evidence(
    query: Annotated[str, "Search query"] = "",
    purpose: Annotated[
        str, "fresh_news, sentiment, risk, catalyst, or default"
    ] = "default",
    max_results: Annotated[int, "Maximum results to return, clamped to 1..5"] = 5,
) -> str:
    """Return controlled Web Search evidence as Markdown for analyst use."""
    return _invoke_legacy_tool(
        _lc_web_search_evidence,
        {
            "query": query,
            "purpose": purpose,
            "max_results": max_results,
        },
    )


@dataclass(frozen=True)
class AdkToolCollection:
    """Small compatibility wrapper for ADK tools grouped by analyst role."""

    tools: tuple[FunctionTool, ...]

    @property
    def tools_by_name(self) -> dict[str, FunctionTool]:
        return {tool.name: tool for tool in self.tools}

    def invoke(self, tool_name: str, arguments: dict[str, Any]) -> str:
        tool = self.tools_by_name[tool_name]
        return str(tool.func(**_filter_arguments(tool.func, arguments)))


def _filter_arguments(func: Callable[..., Any], arguments: dict[str, Any]) -> dict[str, Any]:
    signature = inspect.signature(func)
    return {
        key: value
        for key, value in arguments.items()
        if key in signature.parameters
    }


def create_raw_tool_registry() -> dict[str, list[Callable[..., str]]]:
    """Return pure Python tool functions grouped by analyst role."""
    return {
        "market": [get_stock_data, get_indicators],
        "social": [get_news, web_search_evidence],
        "news": [get_news, get_global_news, get_insider_transactions, web_search_evidence],
        "fundamentals": [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
            get_insider_transactions,
        ],
    }


def create_adk_tool_registry() -> dict[str, list[FunctionTool]]:
    """Return ADK FunctionTool objects grouped by analyst role."""
    return {
        role: [FunctionTool(func) for func in functions]
        for role, functions in create_raw_tool_registry().items()
    }


def create_adk_tool_collections() -> dict[str, AdkToolCollection]:
    """Return grouped ADK tools with a name lookup surface."""
    return {
        role: AdkToolCollection(tuple(tools))
        for role, tools in create_adk_tool_registry().items()
    }
