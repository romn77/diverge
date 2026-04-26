import copy
import unittest
from unittest.mock import patch

import tradingagents.default_config as default_config
import tradingagents.dataflows.config as config_module
import tradingagents.dataflows.interface as interface
from tradingagents.dataflows.vendor_errors import VendorRetryableError
from tradingagents.valuation.schemas import ValuationInput


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

    def test_us_analysis_fundamentals_routes_fmp_alpha_vantage_yfinance(self):
        with patch.object(interface.vendor_usage, "_database_store", return_value=None):
            with interface.vendor_usage.data_source_usage_context("analysis"):
                self.assertEqual(
                    interface.build_vendor_chain("get_fundamentals", "us"),
                    ["fmp", "alpha_vantage", "yfinance"],
                )
                self.assertEqual(
                    interface.build_vendor_chain("get_insider_transactions", "us"),
                    ["fmp", "alpha_vantage", "yfinance"],
                )

        for method in (
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement",
            "get_news",
            "get_insider_transactions",
        ):
            self.assertIn("fmp", interface.VENDOR_METHODS[method])

    def test_route_to_normalized_fundamentals_uses_existing_vendor_routing(self):
        payloads = {
            "get_fundamentals": (
                "# Company Fundamentals for MSFT\n"
                "# Data retrieved on: 2026-03-20 10:00:00\n\n"
                "Market Cap: 2500\n"
                "Shares Outstanding: 100\n"
            ),
            "get_balance_sheet": (
                "# Balance Sheet data for MSFT (annual)\n"
                "# Data retrieved on: 2026-03-20 10:00:00\n\n"
                ",2025-12-31\n"
                "Cash And Cash Equivalents,80\n"
                "Total Debt,150\n"
                "Stockholders Equity,600\n"
            ),
            "get_cashflow": (
                "# Cash Flow data for MSFT (annual)\n"
                "# Data retrieved on: 2026-03-20 10:00:00\n\n"
                ",2025-12-31\n"
                "Free Cash Flow,120\n"
            ),
            "get_income_statement": (
                "# Income Statement data for MSFT (annual)\n"
                "# Data retrieved on: 2026-03-20 10:00:00\n\n"
                ",2025-12-31\n"
                "Total Revenue,1000\n"
                "EBITDA,220\n"
                "Net Income,120\n"
            ),
        }

        def fake_route(method, *args, **kwargs):
            return payloads[method]

        with patch.object(interface, "route_to_vendor", side_effect=fake_route):
            result = interface.route_to_normalized_fundamentals(
                "MSFT",
                curr_date="2026-03-20",
                freq="annual",
            )

        self.assertIsInstance(result, ValuationInput)
        self.assertEqual(result.ticker, "MSFT")
        self.assertEqual(result.market.market_cap, 2500.0)
        self.assertEqual(result.latest_financial.revenue, 1000.0)


if __name__ == "__main__":
    unittest.main()
