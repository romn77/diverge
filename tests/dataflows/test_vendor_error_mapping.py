import copy
import unittest
from unittest.mock import patch

import diverge.default_config as default_config
import diverge.dataflows.config as config_module
import diverge.dataflows.interface as interface


class VendorErrorMappingTests(unittest.TestCase):
    def setUp(self):
        config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)

    def test_legacy_error_string_triggers_fallback(self):
        config_module.set_config(
            {
                "market": "cn",
                "market_overrides": {
                    "cn": {
                        "core_stock_apis": "akshare,tushare",
                    }
                },
            }
        )

        calls = []

        def first_vendor(symbol, start_date, end_date):
            calls.append(("akshare", symbol))
            return "Error: temporary vendor outage"

        def second_vendor(symbol, start_date, end_date):
            calls.append(("tushare", symbol))
            return "ok"

        vendor_methods = copy.deepcopy(interface.VENDOR_METHODS)
        vendor_methods["get_stock_data"] = {
            "akshare": first_vendor,
            "tushare": second_vendor,
        }

        with patch.object(interface, "VENDOR_METHODS", vendor_methods):
            result = interface.route_to_vendor(
                "get_stock_data", "600519", "2024-01-01", "2024-02-01"
            )

        self.assertEqual(result, "ok")
        self.assertEqual(calls[0][0], "akshare")
        self.assertEqual(calls[1][0], "tushare")

    def test_non_error_string_passthrough(self):
        config_module.set_config(
            {"market": "cn", "market_overrides": {"cn": {"core_stock_apis": "akshare"}}}
        )

        def first_vendor(symbol, start_date, end_date):
            return "Error budget report for period"

        vendor_methods = copy.deepcopy(interface.VENDOR_METHODS)
        vendor_methods["get_stock_data"] = {"akshare": first_vendor}

        with patch.object(interface, "VENDOR_METHODS", vendor_methods):
            result = interface.route_to_vendor(
                "get_stock_data", "600519", "2024-01-01", "2024-02-01"
            )

        self.assertEqual(result, "Error budget report for period")

    def test_exhausted_chain_error_contains_attempted_vendors(self):
        config_module.set_config(
            {
                "market": "cn",
                "market_overrides": {"cn": {"core_stock_apis": "akshare,tushare"}},
            }
        )

        def failing_akshare(symbol, start_date, end_date):
            return "Error: akshare unavailable"

        def failing_tushare(symbol, start_date, end_date):
            return "Error: tushare unavailable"

        vendor_methods = copy.deepcopy(interface.VENDOR_METHODS)
        vendor_methods["get_stock_data"] = {
            "akshare": failing_akshare,
            "tushare": failing_tushare,
        }

        with patch.object(interface, "VENDOR_METHODS", vendor_methods):
            with self.assertRaises(RuntimeError) as ctx:
                interface.route_to_vendor(
                    "get_stock_data", "600519", "2024-01-01", "2024-02-01"
                )

        message = str(ctx.exception).lower()
        self.assertIn("attempted", message)
        self.assertIn("akshare", message)
        self.assertIn("tushare", message)


if __name__ == "__main__":
    unittest.main()
