import copy
import unittest
from unittest.mock import patch

import diverge.default_config as default_config
import diverge.dataflows.config as config_module
import diverge.dataflows.interface as interface


class RouterPrecedenceTests(unittest.TestCase):
    def setUp(self):
        config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)

    def test_tool_vendor_overrides_market_and_category(self):
        config_module.set_config(
            {
                "market": "cn",
                "tool_vendors": {"get_stock_data": "tushare"},
                "market_overrides": {"cn": {"core_stock_apis": "akshare"}},
                "data_vendors": {"core_stock_apis": "yfinance"},
            }
        )

        calls = []

        def akshare_vendor(symbol, start_date, end_date):
            calls.append("akshare")
            return "ak"

        def tushare_vendor(symbol, start_date, end_date):
            calls.append("tushare")
            return "ts"

        vendor_methods = copy.deepcopy(interface.VENDOR_METHODS)
        vendor_methods["get_stock_data"] = {
            "akshare": akshare_vendor,
            "tushare": tushare_vendor,
        }

        with patch.object(interface, "VENDOR_METHODS", vendor_methods):
            result = interface.route_to_vendor(
                "get_stock_data", "600519", "2024-01-01", "2024-02-01"
            )

        self.assertEqual(result, "ts")
        self.assertEqual(calls[0], "tushare")

    def test_forced_cn_market_on_us_symbol(self):
        config_module.set_config(
            {
                "market": "cn",
                "market_overrides": {"cn": {"core_stock_apis": "akshare"}},
            }
        )

        calls = []

        def akshare_vendor(symbol, start_date, end_date):
            calls.append(symbol)
            return "ok"

        vendor_methods = copy.deepcopy(interface.VENDOR_METHODS)
        vendor_methods["get_stock_data"] = {"akshare": akshare_vendor}

        with patch.object(interface, "VENDOR_METHODS", vendor_methods):
            interface.route_to_vendor(
                "get_stock_data", "AAPL", "2024-01-01", "2024-02-01"
            )

        self.assertEqual(calls, ["AAPL"])


if __name__ == "__main__":
    unittest.main()
