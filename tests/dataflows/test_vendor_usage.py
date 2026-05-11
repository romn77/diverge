import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from diverge.dataflows import vendor_usage
from diverge.dataflows.vendor_usage import QuotaWaitRequired
from diverge.dataflows.interface import execute_vendor_chain
from web.backend import auth
from web.backend.schemas.admin import AdminDataSourceRouteUpdatePayload


class VendorUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.usage_path = os.path.join(self.temp_dir.name, "vendor_usage.json")
        self.env_patch = patch.dict(
            os.environ,
            {
                "AUTH_ENABLED": "false",
                "AUTH_MODE": "disabled",
                "DATA_SOURCE_USAGE_PATH": self.usage_path,
            },
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

    def test_all_exhausted_vendor_chain_raises_quota_wait_required(self):
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

        with self.assertRaises(QuotaWaitRequired) as context:
            execute_vendor_chain(
                method="get_stock_data",
                market="us",
                symbol="AAPL",
                resolved_args=("AAPL", "2026-04-01", "2026-04-26"),
                resolved_kwargs={},
                vendors=["alpha_vantage"],
                vendor_methods={
                    "get_stock_data": {
                        "alpha_vantage": lambda *args, **kwargs: "alpha",
                    }
                },
            )

        self.assertEqual(context.exception.vendor, "alpha_vantage")
        self.assertIn("quota", context.exception.reason.lower())
        self.assertIsNotNone(context.exception.blocked_until)

    def test_hourly_limit_marks_source_unavailable_before_daily_limit(self):
        vendor_usage.update_data_source_config(
            "alpha_vantage",
            enabled=True,
            daily_limit=25,
            hourly_limit=1,
        )
        vendor_usage.record_data_source_call(
            "alpha_vantage",
            module="analysis",
            success=True,
        )

        self.assertFalse(vendor_usage.is_data_source_available("alpha_vantage"))
        sources = {
            source["vendor"]: source
            for source in vendor_usage.get_data_source_usage_summary()["sources"]
        }
        alpha = sources["alpha_vantage"]
        self.assertEqual(alpha["daily_limit"], 25)
        self.assertEqual(alpha["hourly_limit"], 1)
        self.assertEqual(alpha["used_today"], 1)
        self.assertEqual(alpha["used_this_hour"], 1)
        self.assertEqual(alpha["remaining_today"], 24)
        self.assertEqual(alpha["remaining_this_hour"], 0)
        self.assertFalse(alpha["daily_exhausted"])
        self.assertTrue(alpha["hour_exhausted"])
        self.assertTrue(alpha["exhausted"])

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

    def test_unavailable_database_store_falls_back_to_local_state(self):
        class BrokenDatabaseStore:
            def resolve_data_source_route(self, **kwargs):
                raise RuntimeError("database unavailable")

            def update_data_source_config(self, *args, **kwargs):
                raise RuntimeError("database unavailable")

            def is_data_source_available(self, *args, **kwargs):
                raise RuntimeError("database unavailable")

            def record_data_source_call(self, *args, **kwargs):
                raise RuntimeError("database unavailable")

            def get_data_source_usage_summary(self):
                raise RuntimeError("database unavailable")

        with (
            patch.dict(
                os.environ,
                {"DATA_SOURCE_USAGE_ALLOW_LOCAL_FALLBACK": "true"},
                clear=False,
            ),
            patch.object(
                vendor_usage, "_database_store", return_value=BrokenDatabaseStore()
            ),
        ):
            self.assertEqual(
                vendor_usage.get_data_source_route(
                    module="analysis",
                    market="us",
                    category="core_stock_apis",
                ),
                ["massive"],
            )
            vendor_usage.update_data_source_config(
                "alpha_vantage",
                enabled=True,
                daily_limit=1,
            )
            self.assertTrue(vendor_usage.is_data_source_available("alpha_vantage"))
            vendor_usage.record_data_source_call(
                "alpha_vantage",
                module="analysis",
                success=True,
            )
            self.assertFalse(vendor_usage.is_data_source_available("alpha_vantage"))
            sources = {
                source["vendor"]: source
                for source in vendor_usage.get_data_source_usage_summary()["sources"]
            }
            self.assertEqual(sources["alpha_vantage"]["used_today"], 1)


class VendorUsageDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_url = (
            f"sqlite+pysqlite:///{Path(self.temp_dir.name) / 'usage.db'}"
        )
        self.usage_path = Path(self.temp_dir.name) / "should-not-be-used.json"
        self.env_patch = patch.dict(
            os.environ,
            {
                "AUTH_ENABLED": "true",
                "AUTH_MODE": "required",
                "DATABASE_URL": self.database_url,
                "DATA_SOURCE_USAGE_PATH": str(self.usage_path),
            },
            clear=False,
        )
        self.env_patch.start()
        auth.reset_runtime_state()
        auth.create_all_for_testing()

    def tearDown(self):
        auth.reset_runtime_state()
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_vendor_config_and_usage_are_written_to_database_when_available(self):
        from web.backend import data_sources

        vendor_usage.update_data_source_config(
            "alpha_vantage",
            enabled=False,
            daily_limit=7,
            hourly_limit=3,
        )
        vendor_usage.record_data_source_call(
            "massive",
            module="analysis",
            success=True,
        )

        self.assertFalse(self.usage_path.exists())
        with auth.db_session() as db:
            config = db.get(data_sources.DataSourceVendorConfig, "alpha_vantage")
            self.assertIsNotNone(config)
            self.assertFalse(config.enabled)
            self.assertEqual(config.daily_limit, 7)
            self.assertEqual(config.hourly_limit, 3)

            usage = db.scalar(
                data_sources.select_usage_row(
                    vendor="massive",
                    module="analysis",
                    usage_date=vendor_usage.current_usage_date(),
                )
            )
            self.assertIsNotNone(usage)
            self.assertEqual(usage.total_calls, 1)
            self.assertEqual(usage.success_count, 1)
            self.assertEqual(usage.failure_count, 0)

        auth.reset_runtime_state()
        sources = {
            source["vendor"]: source
            for source in vendor_usage.get_data_source_usage_summary()["sources"]
        }
        self.assertFalse(sources["alpha_vantage"]["enabled"])
        self.assertEqual(sources["alpha_vantage"]["daily_limit"], 7)
        self.assertEqual(sources["alpha_vantage"]["hourly_limit"], 3)

    def test_database_usage_upsert_accumulates_and_resets_hour_bucket(self):
        from web.backend import data_sources

        vendor_usage.record_data_source_call(
            "massive",
            module="analysis",
            success=True,
        )
        vendor_usage.record_data_source_call(
            "massive",
            module="analysis",
            success=False,
        )

        usage_date = vendor_usage.current_usage_date()
        with auth.db_session() as db:
            usage = db.scalar(
                data_sources.select_usage_row(
                    vendor="massive",
                    module="analysis",
                    usage_date=usage_date,
                )
            )
            self.assertIsNotNone(usage)
            self.assertEqual(usage.total_calls, 2)
            self.assertEqual(usage.success_count, 1)
            self.assertEqual(usage.failure_count, 1)
            self.assertEqual(usage.hour_total_calls, 2)
            usage.hour_key = "2000-01-01T00"
            usage.hour_total_calls = 9

        vendor_usage.record_data_source_call(
            "massive",
            module="analysis",
            success=True,
        )
        with auth.db_session() as db:
            usage = db.scalar(
                data_sources.select_usage_row(
                    vendor="massive",
                    module="analysis",
                    usage_date=usage_date,
                )
            )
            self.assertEqual(usage.total_calls, 3)
            self.assertEqual(usage.success_count, 2)
            self.assertEqual(usage.failure_count, 1)
            self.assertEqual(usage.hour_total_calls, 1)
            self.assertNotEqual(usage.hour_key, "2000-01-01T00")

    def test_database_store_failure_is_not_silently_ignored_when_database_backed(self):
        class BrokenDatabaseStore:
            def is_data_source_available(self, *args, **kwargs):
                raise RuntimeError("database unavailable")

        with (
            patch.dict(os.environ, {"APP_ENV": "production"}, clear=False),
            patch.object(
                vendor_usage, "_database_store", return_value=BrokenDatabaseStore()
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "data-source governance"):
                vendor_usage.is_data_source_available("alpha_vantage")

    def test_database_route_policy_overrides_analysis_vendor_chain(self):
        from diverge.dataflows.interface import build_vendor_chain
        from web.backend.routers import admin as admin_router
        from web.backend import data_sources

        updated = admin_router.update_admin_data_source_route(
            "analysis",
            "us",
            "core_stock_apis",
            AdminDataSourceRouteUpdatePayload(vendor_chain=["yfinance"]),
        )

        with vendor_usage.data_source_usage_context("analysis"):
            self.assertEqual(build_vendor_chain("get_stock_data", "us"), ["yfinance"])
        self.assertEqual(updated["route"]["vendor_chain"], ["yfinance"])

        summary = data_sources.get_data_source_usage_summary()
        routes = {
            (route["module"], route["market"], route["category"]): route
            for route in summary["routes"]
        }
        self.assertEqual(
            routes[("analysis", "us", "core_stock_apis")]["vendor_chain"],
            ["yfinance"],
        )

    def test_database_route_policy_provides_screener_sources(self):
        from web.backend import data_sources
        from web.backend.routers import screeners as screeners_router

        data_sources.update_data_source_route(
            module="screener",
            market="cn",
            category="core_stock_apis",
            vendor_chain=["akshare", "tushare"],
        )
        data_sources.update_data_source_route(
            module="screener",
            market="us",
            category="core_stock_apis",
            vendor_chain=["yfinance", "massive"],
        )

        sources = screeners_router.resolve_screener_data_sources(["cn", "us"])

        self.assertEqual(sources["cn_data_source"], "akshare")
        self.assertEqual(sources["cn_data_source_fallbacks"], ["tushare"])
        self.assertEqual(sources["us_data_source"], "yfinance")
        self.assertEqual(sources["us_data_source_fallbacks"], ["massive"])


if __name__ == "__main__":
    unittest.main()
