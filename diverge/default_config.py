import os

from diverge.config.paths import resolve_data_cache_dir, resolve_eval_results_dir
from diverge.llm_clients.model_config import (
    DEFAULT_DEEP_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_QUICK_MODEL,
    get_provider_base_url,
)

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "eval_results_dir": str(resolve_eval_results_dir()),
    "data_cache_dir": str(resolve_data_cache_dir()),
    # LLM settings
    "llm_provider": DEFAULT_LLM_PROVIDER,
    "deep_think_llm": DEFAULT_DEEP_MODEL,
    "quick_think_llm": DEFAULT_QUICK_MODEL,
    "backend_url": get_provider_base_url(DEFAULT_LLM_PROVIDER),
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "en",
    # Provider-specific thinking configuration
    "google_thinking_level": None,  # "high", "minimal", etc.
    "openai_reasoning_effort": None,  # "medium", "high", "low"
    "anthropic_effort": None,  # "high", "medium", "low"
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    "market": "auto",
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "massive,yfinance,alpha_vantage",
        "technical_indicators": "local",
        "fundamental_data": "fmp,alpha_vantage,yfinance",
        "news_data": "fmp,alpha_vantage,yfinance",
    },
    "market_overrides": {
        "cn": {
            "core_stock_apis": "akshare,tushare",
            "technical_indicators": "local",
            "fundamental_data": "tushare,akshare",
            "news_data": "akshare,yfinance",
        },
        "us": {
            "core_stock_apis": "massive",
            "technical_indicators": "local",
            "fundamental_data": "fmp,alpha_vantage,yfinance",
            "news_data": "fmp,alpha_vantage,yfinance",
        },
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
    "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
}
