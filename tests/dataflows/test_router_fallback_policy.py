import copy
import unittest
from unittest.mock import patch

import diverge.default_config as default_config
import diverge.dataflows.config as config_module
import diverge.dataflows.interface as interface
from diverge.dataflows.vendor_errors import (
    VendorAuthError,
    VendorDataEmptyError,
    VendorNotSupportedError,
    VendorRetryableError,
)


class RouterFallbackPolicyTests(unittest.TestCase):
    def setUp(self):
        config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)

    def _run_with_first_failure(self, first_exc):
        config_module.set_config(
            {
                "market": "cn",
                "market_overrides": {"cn": {"core_stock_apis": "akshare,tushare"}},
            }
        )

        calls = []

        def first_vendor(symbol, start_date, end_date):
            calls.append("akshare")
            raise first_exc

        def second_vendor(symbol, start_date, end_date):
            calls.append("tushare")
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
        self.assertEqual(calls, ["akshare", "tushare"])

    def test_retryable_error_fallback(self):
        self._run_with_first_failure(VendorRetryableError("temporary"))

    def test_auth_error_fallback(self):
        self._run_with_first_failure(VendorAuthError("token missing"))

    def test_not_supported_error_fallback(self):
        self._run_with_first_failure(VendorNotSupportedError("not supported"))

    def test_data_empty_error_fallback(self):
        self._run_with_first_failure(VendorDataEmptyError("empty"))


if __name__ == "__main__":
    unittest.main()
