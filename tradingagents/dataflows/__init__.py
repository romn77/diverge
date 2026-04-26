from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from types import ModuleType


_LEGACY_MODULE_ALIASES = {
    f"{__name__}.akshare": f"{__name__}.vendors.akshare",
    f"{__name__}.akshare_fundamentals": f"{__name__}.vendors.akshare.fundamentals",
    f"{__name__}.akshare_indicator": f"{__name__}.vendors.akshare.indicator",
    f"{__name__}.akshare_news": f"{__name__}.vendors.akshare.news",
    f"{__name__}.akshare_rate_limit": f"{__name__}.vendors.akshare.rate_limit",
    f"{__name__}.akshare_stock": f"{__name__}.vendors.akshare.stock",
    f"{__name__}.akshare_valuation": f"{__name__}.vendors.akshare.valuation",
    f"{__name__}.alpha_vantage": f"{__name__}.vendors.alpha_vantage",
    f"{__name__}.alpha_vantage_common": f"{__name__}.vendors.alpha_vantage.common",
    f"{__name__}.alpha_vantage_fundamentals": f"{__name__}.vendors.alpha_vantage.fundamentals",
    f"{__name__}.alpha_vantage_indicator": f"{__name__}.vendors.alpha_vantage.indicator",
    f"{__name__}.alpha_vantage_news": f"{__name__}.vendors.alpha_vantage.news",
    f"{__name__}.alpha_vantage_stock": f"{__name__}.vendors.alpha_vantage.stock",
    f"{__name__}.analysis_market_data": f"{__name__}.vendors.local.analysis_market_data",
    f"{__name__}.fmp_common": f"{__name__}.vendors.fmp.common",
    f"{__name__}.fmp_fundamentals": f"{__name__}.vendors.fmp.fundamentals",
    f"{__name__}.fmp_news": f"{__name__}.vendors.fmp.news",
    f"{__name__}.massive": f"{__name__}.vendors.massive",
    f"{__name__}.massive_common": f"{__name__}.vendors.massive.common",
    f"{__name__}.massive_stock": f"{__name__}.vendors.massive.stock",
    f"{__name__}.stockstats_utils": f"{__name__}.vendors.yfinance.stockstats_utils",
    f"{__name__}.tushare": f"{__name__}.vendors.tushare",
    f"{__name__}.tushare_common": f"{__name__}.vendors.tushare.common",
    f"{__name__}.tushare_fundamentals": f"{__name__}.vendors.tushare.fundamentals",
    f"{__name__}.tushare_indicator": f"{__name__}.vendors.tushare.indicator",
    f"{__name__}.tushare_news": f"{__name__}.vendors.tushare.news",
    f"{__name__}.tushare_stock": f"{__name__}.vendors.tushare.stock",
    f"{__name__}.y_finance": f"{__name__}.vendors.yfinance.stock",
    f"{__name__}.yfinance_news": f"{__name__}.vendors.yfinance.news",
    f"{__name__}.yfinance_valuation": f"{__name__}.vendors.yfinance.valuation",
}


def _load_legacy_module(fullname: str) -> ModuleType:
    module = importlib.import_module(_LEGACY_MODULE_ALIASES[fullname])
    sys.modules[fullname] = module
    globals()[fullname.rsplit(".", 1)[-1]] = module
    return module


class _LegacyDataflowsLoader(importlib.abc.Loader):
    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        return _load_legacy_module(spec.name)

    def exec_module(self, module: ModuleType) -> None:
        return None


class _LegacyDataflowsFinder(importlib.abc.MetaPathFinder):
    _tradingagents_dataflows_alias_finder = True

    def find_spec(
        self,
        fullname: str,
        path: object | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname not in _LEGACY_MODULE_ALIASES:
            return None
        return importlib.util.spec_from_loader(fullname, _LegacyDataflowsLoader())


if not any(
    getattr(finder, "_tradingagents_dataflows_alias_finder", False)
    for finder in sys.meta_path
):
    sys.meta_path.insert(0, _LegacyDataflowsFinder())


def __getattr__(name: str) -> ModuleType:
    fullname = f"{__name__}.{name}"
    if fullname in _LEGACY_MODULE_ALIASES:
        return _load_legacy_module(fullname)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["vendors"]
