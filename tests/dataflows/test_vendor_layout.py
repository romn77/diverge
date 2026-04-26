from pathlib import Path
import importlib


DATAFLOWS_ROOT = Path(__file__).resolve().parents[2] / "tradingagents" / "dataflows"

LEGACY_VENDOR_ALIASES = {
    "akshare": "tradingagents.dataflows.vendors.akshare",
    "akshare_fundamentals": "tradingagents.dataflows.vendors.akshare.fundamentals",
    "akshare_indicator": "tradingagents.dataflows.vendors.akshare.indicator",
    "akshare_news": "tradingagents.dataflows.vendors.akshare.news",
    "akshare_rate_limit": "tradingagents.dataflows.vendors.akshare.rate_limit",
    "akshare_stock": "tradingagents.dataflows.vendors.akshare.stock",
    "akshare_valuation": "tradingagents.dataflows.vendors.akshare.valuation",
    "alpha_vantage": "tradingagents.dataflows.vendors.alpha_vantage",
    "alpha_vantage_common": "tradingagents.dataflows.vendors.alpha_vantage.common",
    "alpha_vantage_fundamentals": "tradingagents.dataflows.vendors.alpha_vantage.fundamentals",
    "alpha_vantage_indicator": "tradingagents.dataflows.vendors.alpha_vantage.indicator",
    "alpha_vantage_news": "tradingagents.dataflows.vendors.alpha_vantage.news",
    "alpha_vantage_stock": "tradingagents.dataflows.vendors.alpha_vantage.stock",
    "analysis_market_data": "tradingagents.dataflows.vendors.local.analysis_market_data",
    "fmp_common": "tradingagents.dataflows.vendors.fmp.common",
    "fmp_fundamentals": "tradingagents.dataflows.vendors.fmp.fundamentals",
    "fmp_news": "tradingagents.dataflows.vendors.fmp.news",
    "massive": "tradingagents.dataflows.vendors.massive",
    "massive_common": "tradingagents.dataflows.vendors.massive.common",
    "massive_stock": "tradingagents.dataflows.vendors.massive.stock",
    "stockstats_utils": "tradingagents.dataflows.vendors.yfinance.stockstats_utils",
    "tushare": "tradingagents.dataflows.vendors.tushare",
    "tushare_common": "tradingagents.dataflows.vendors.tushare.common",
    "tushare_fundamentals": "tradingagents.dataflows.vendors.tushare.fundamentals",
    "tushare_indicator": "tradingagents.dataflows.vendors.tushare.indicator",
    "tushare_news": "tradingagents.dataflows.vendors.tushare.news",
    "tushare_stock": "tradingagents.dataflows.vendors.tushare.stock",
    "y_finance": "tradingagents.dataflows.vendors.yfinance.stock",
    "yfinance_news": "tradingagents.dataflows.vendors.yfinance.news",
    "yfinance_valuation": "tradingagents.dataflows.vendors.yfinance.valuation",
}


def test_vendor_implementations_live_under_vendor_packages():
    for target_path in LEGACY_VENDOR_ALIASES.values():
        assert importlib.import_module(target_path).__name__ == target_path


def test_legacy_vendor_imports_alias_new_modules():
    for legacy_name, target_path in LEGACY_VENDOR_ALIASES.items():
        legacy_module = importlib.import_module(f"tradingagents.dataflows.{legacy_name}")
        target_module = importlib.import_module(target_path)

        assert legacy_module is target_module


def test_vendor_implementation_files_are_not_left_at_dataflows_root():
    legacy_files = {f"{module_name}.py" for module_name in LEGACY_VENDOR_ALIASES}
    root_vendor_files = sorted(path.name for path in DATAFLOWS_ROOT.glob("*.py") if path.name in legacy_files)

    assert root_vendor_files == []
