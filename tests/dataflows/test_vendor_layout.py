from pathlib import Path
import importlib


DATAFLOWS_ROOT = Path(__file__).resolve().parents[2] / "diverge" / "dataflows"

LEGACY_VENDOR_ALIASES = {
    "akshare": "diverge.dataflows.vendors.akshare",
    "akshare_fundamentals": "diverge.dataflows.vendors.akshare.fundamentals",
    "akshare_indicator": "diverge.dataflows.vendors.akshare.indicator",
    "akshare_news": "diverge.dataflows.vendors.akshare.news",
    "akshare_rate_limit": "diverge.dataflows.vendors.akshare.rate_limit",
    "akshare_stock": "diverge.dataflows.vendors.akshare.stock",
    "akshare_valuation": "diverge.dataflows.vendors.akshare.valuation",
    "alpha_vantage": "diverge.dataflows.vendors.alpha_vantage",
    "alpha_vantage_common": "diverge.dataflows.vendors.alpha_vantage.common",
    "alpha_vantage_fundamentals": "diverge.dataflows.vendors.alpha_vantage.fundamentals",
    "alpha_vantage_indicator": "diverge.dataflows.vendors.alpha_vantage.indicator",
    "alpha_vantage_news": "diverge.dataflows.vendors.alpha_vantage.news",
    "alpha_vantage_stock": "diverge.dataflows.vendors.alpha_vantage.stock",
    "analysis_market_data": "diverge.dataflows.vendors.local.analysis_market_data",
    "fmp_common": "diverge.dataflows.vendors.fmp.common",
    "fmp_fundamentals": "diverge.dataflows.vendors.fmp.fundamentals",
    "fmp_news": "diverge.dataflows.vendors.fmp.news",
    "massive": "diverge.dataflows.vendors.massive",
    "massive_common": "diverge.dataflows.vendors.massive.common",
    "massive_stock": "diverge.dataflows.vendors.massive.stock",
    "stockstats_utils": "diverge.dataflows.vendors.yfinance.stockstats_utils",
    "tushare": "diverge.dataflows.vendors.tushare",
    "tushare_common": "diverge.dataflows.vendors.tushare.common",
    "tushare_fundamentals": "diverge.dataflows.vendors.tushare.fundamentals",
    "tushare_indicator": "diverge.dataflows.vendors.tushare.indicator",
    "tushare_news": "diverge.dataflows.vendors.tushare.news",
    "tushare_stock": "diverge.dataflows.vendors.tushare.stock",
    "y_finance": "diverge.dataflows.vendors.yfinance.stock",
    "yfinance_news": "diverge.dataflows.vendors.yfinance.news",
    "yfinance_valuation": "diverge.dataflows.vendors.yfinance.valuation",
}


def test_vendor_implementations_live_under_vendor_packages():
    for target_path in LEGACY_VENDOR_ALIASES.values():
        assert importlib.import_module(target_path).__name__ == target_path


def test_legacy_vendor_imports_alias_new_modules():
    for legacy_name, target_path in LEGACY_VENDOR_ALIASES.items():
        legacy_module = importlib.import_module(f"diverge.dataflows.{legacy_name}")
        target_module = importlib.import_module(target_path)

        assert legacy_module is target_module


def test_vendor_implementation_files_are_not_left_at_dataflows_root():
    legacy_files = {f"{module_name}.py" for module_name in LEGACY_VENDOR_ALIASES}
    root_vendor_files = sorted(path.name for path in DATAFLOWS_ROOT.glob("*.py") if path.name in legacy_files)

    assert root_vendor_files == []
