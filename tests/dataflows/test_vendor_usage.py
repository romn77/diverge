import os
import tempfile
import unittest
from unittest.mock import patch

from tradingagents.dataflows import vendor_usage
from tradingagents.dataflows.interface import execute_vendor_chain


class VendorUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.usage_path = os.path.join(self.temp_dir.name, "vendor_usage.json")
        self.env_patch = patch.dict(
            os.environ,
            {"DATA_SOURCE_USAGE_PATH": self.usage_path},
            clear=False,
        )
        self.env_patch.start()
        vendor_usage.reset_data_source_usage_state()

    def tearDown(self):
        vendor_usage.reset_data_source_usage_state()
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_alpha_vantage_daily_limit_skips_to_next_vendor(self):
        vendor_usage.update_data_source_config(
            "alpha_vantage",
            enabled=True,
            daily_limit=1,
        )
        vendor_usage.record_data_source_call(
            "alpha_vantage",
            module="analysis",
            success=True,
        )
        calls = []

        def alpha_vendor(*args, **kwargs):
            calls.append("alpha_vantage")
            return "alpha"

        def yfinance_vendor(*args, **kwargs):
            calls.append("yfinance")
            return "yfinance"

        result = execute_vendor_chain(
            method="get_stock_data",
            market="us",
            symbol="AAPL",
            resolved_args=("AAPL", "2026-04-01", "2026-04-26"),
            resolved_kwargs={},
            vendors=["alpha_vantage", "yfinance"],
            vendor_methods={
                "get_stock_data": {
                    "alpha_vantage": alpha_vendor,
                    "yfinance": yfinance_vendor,
                }
            },
        )

        self.assertEqual(result, "yfinance")
        self.assertEqual(calls, ["yfinance"])
        sources = {
            source["vendor"]: source
            for source in vendor_usage.get_data_source_usage_summary()["sources"]
        }
        self.assertTrue(sources["alpha_vantage"]["exhausted"])
        self.assertEqual(sources["alpha_vantage"]["used_today"], 1)

    def test_vendor_call_counts_are_scoped_by_module_and_status(self):
        with vendor_usage.data_source_usage_context("trade_journal"):
            vendor_usage.record_data_source_call("massive", success=True)
            vendor_usage.record_data_source_call("massive", success=False)

        sources = {
            source["vendor"]: source
            for source in vendor_usage.get_data_source_usage_summary()["sources"]
        }
        massive = sources["massive"]

        self.assertEqual(massive["used_today"], 2)
        self.assertEqual(massive["success_count"], 1)
        self.assertEqual(massive["failure_count"], 1)
        self.assertEqual(massive["modules"]["trade_journal"]["total_calls"], 2)
        self.assertEqual(massive["modules"]["trade_journal"]["success_count"], 1)
        self.assertEqual(massive["modules"]["trade_journal"]["failure_count"], 1)


if __name__ == "__main__":
    unittest.main()
