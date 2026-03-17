import os

from tradingagents.llm_clients.model_config import (
    DEFAULT_DEEP_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_QUICK_MODEL,
    get_provider_base_url,
)

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": DEFAULT_LLM_PROVIDER,
    "deep_think_llm": DEFAULT_DEEP_MODEL,
    "quick_think_llm": DEFAULT_QUICK_MODEL,
    "backend_url": get_provider_base_url(DEFAULT_LLM_PROVIDER),
    "output_language": "en",
    # Provider-specific thinking configuration
    "google_thinking_level": None,  # "high", "minimal", etc.
    "openai_reasoning_effort": None,  # "medium", "high", "low"
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    "market": "auto",
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance,alpha_vantage",
        "technical_indicators": "yfinance,alpha_vantage",
        "fundamental_data": "yfinance,alpha_vantage",
        "news_data": "yfinance,alpha_vantage",
    },
    "market_overrides": {
        "cn": {
            "core_stock_apis": "akshare,tushare",
            "technical_indicators": "akshare,tushare",
            "fundamental_data": "tushare,akshare",
            "news_data": "akshare,yfinance",
        },
        "us": {
            "core_stock_apis": "yfinance,alpha_vantage",
            "technical_indicators": "yfinance,alpha_vantage",
            "fundamental_data": "yfinance,alpha_vantage",
            "news_data": "yfinance,alpha_vantage",
        },
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
    "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
}
