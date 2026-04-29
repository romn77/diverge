import copy
import unittest

import diverge.default_config as default_config
import diverge.dataflows.config as config_module


class ConfigMergeTests(unittest.TestCase):
    def setUp(self):
        config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)

    def test_market_override_deep_merge(self):
        config_module.set_config(
            {"market_overrides": {"cn": {"fundamental_data": "tushare"}}}
        )
        merged = config_module.get_config()

        self.assertIn("cn", merged["market_overrides"])
        self.assertIn("us", merged["market_overrides"])
        self.assertEqual(
            merged["market_overrides"]["cn"]["fundamental_data"], "tushare"
        )
        self.assertIn("core_stock_apis", merged["market_overrides"]["cn"])

    def test_legacy_config_payload_still_valid(self):
        config_module.set_config({"data_vendors": {"news_data": "yfinance"}})
        merged = config_module.get_config()
        self.assertIn("core_stock_apis", merged["data_vendors"])
        self.assertEqual(merged["data_vendors"]["news_data"], "yfinance")


if __name__ == "__main__":
    unittest.main()
