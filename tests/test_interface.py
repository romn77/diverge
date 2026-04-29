import copy
import unittest
from unittest.mock import patch

import diverge.default_config as default_config
import diverge.dataflows.config as config_module
import diverge.dataflows.interface as interface
from diverge.dataflows.vendor_errors import VendorRetryableError


class InterfaceRoutingTests(unittest.TestCase):
    def setUp(self):
        config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)

    def test_cn_market_override_formats_symbol_for_tushare(self):
        config_module._config.update(
            {
                "market": "auto",
                "market_overrides": {
                    "cn": {"fundamental_data": "tushare"},
                },
            }
        )

        captured = {}

        def fake_tushare_fundamentals(ticker, curr_date=None):
            captured["ticker"] = ticker
            captured["curr_date"] = curr_date
            return "ok"

        vendor_methods = copy.deepcopy(interface.VENDOR_METHODS)
        vendor_methods["get_fundamentals"] = {"tushare": fake_tushare_fundamentals}

        with patch.object(interface, "VENDOR_METHODS", vendor_methods):
            result = interface.route_to_vendor("get_fundamentals", "600519", None)

        self.assertEqual(result, "ok")
        self.assertEqual(captured["ticker"], "600519.SH")

    def test_global_news_does_not_treat_date_as_ticker(self):
        config_module._config.update(
            {
                "market": "auto",
                "data_vendors": {"news_data": "yfinance"},
            }
        )

        captured = {}

        def fake_global_news(curr_date, look_back_days=7, limit=5):
            captured["curr_date"] = curr_date
            captured["look_back_days"] = look_back_days
            captured["limit"] = limit
            return "global-news"

        vendor_methods = copy.deepcopy(interface.VENDOR_METHODS)
        vendor_methods["get_global_news"] = {"yfinance": fake_global_news}

        with patch.object(interface, "VENDOR_METHODS", vendor_methods):
            result = interface.route_to_vendor("get_global_news", "2024-06-01", 7, 5)

        self.assertEqual(result, "global-news")
        self.assertEqual(captured["curr_date"], "2024-06-01")

    def test_retryable_error_falls_back_to_next_vendor(self):
        config_module._config.update(
            {
                "market": "auto",
                "market_overrides": {
                    "cn": {"core_stock_apis": "akshare,tushare"},
                },
            }
        )

        calls = []

        def flaky_vendor(symbol, start_date, end_date):
            calls.append(("akshare", symbol))
            raise VendorRetryableError("temporary failure")

        def backup_vendor(symbol, start_date, end_date):
            calls.append(("tushare", symbol))
            return "stock-ok"

        vendor_methods = copy.deepcopy(interface.VENDOR_METHODS)
        vendor_methods["get_stock_data"] = {
            "akshare": flaky_vendor,
            "tushare": backup_vendor,
        }

        with patch.object(interface, "VENDOR_METHODS", vendor_methods):
            result = interface.route_to_vendor(
                "get_stock_data",
                "600519",
                "2024-01-01",
                "2024-02-01",
            )

        self.assertEqual(result, "stock-ok")
        self.assertEqual(
            calls,
            [
                ("akshare", "600519"),
                ("tushare", "600519.SH"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
