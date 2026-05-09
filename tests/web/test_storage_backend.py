import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from web.backend import app_config, storage
from web.backend.devops import migrate_local_data_to_storage


class StorageBackendTests(unittest.TestCase):
    def test_local_storage_round_trips_bytes_and_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = storage.LocalStorage(Path(temp_dir))

            backend.put_text("reports/SPY/complete_report.md", "# Report\n")
            backend.put_bytes("history/us/AAPL.csv", b"Date,Close\n2026-01-01,1\n")

            self.assertEqual(
                backend.get_text("reports/SPY/complete_report.md"),
                "# Report\n",
            )
            self.assertEqual(
                backend.get_bytes("history/us/AAPL.csv"),
                b"Date,Close\n2026-01-01,1\n",
            )
            self.assertEqual(
                backend.list("reports"),
                ["reports/SPY/complete_report.md"],
            )

            signed_url = backend.presign("reports/SPY/complete_report.md")
            self.assertTrue(signed_url.startswith("file://"))

    def test_storage_factory_supports_local_and_reserves_s3_compatible(self):
        with patch.dict(
            storage.os.environ,
            {
                "STORAGE_BACKEND": "local",
                "STORAGE_LOCAL_ROOT": "/tmp/diverge-storage",
            },
            clear=True,
        ):
            self.assertIsInstance(storage.get_storage(), storage.LocalStorage)

        with patch.dict(
            storage.os.environ, {"STORAGE_BACKEND": "s3_compatible"}, clear=True
        ):
            with self.assertRaises(NotImplementedError):
                storage.get_storage()

    def test_tencent_cos_storage_wraps_sdk_without_importing_in_business_code(self):
        mock_client = Mock()
        backend = storage.TencentCOSStorage(
            bucket="bucket-123",
            region="ap-guangzhou",
            prefix="prod",
            client=mock_client,
        )

        backend.put_text("reports/a.md", "hello")
        backend.get_bytes("reports/a.md")
        backend.delete("reports/a.md")
        backend.presign("reports/a.md", expires=60)

        mock_client.put_object.assert_called_once()
        self.assertEqual(
            mock_client.put_object.call_args.kwargs["Key"], "prod/reports/a.md"
        )
        mock_client.get_object.assert_called_once_with(
            Bucket="bucket-123", Key="prod/reports/a.md"
        )
        mock_client.delete_object.assert_called_once_with(
            Bucket="bucket-123", Key="prod/reports/a.md"
        )
        mock_client.get_presigned_url.assert_called_once()

    def test_local_data_migration_uploads_expected_dataset_prefixes(self):
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            tempfile.TemporaryDirectory() as storage_dir,
        ):
            root = Path(temp_dir)
            original_dirs = (
                app_config.REPORTS_DIR,
                app_config.SCREENER_RESULTS_DIR,
                app_config.STOCK_HISTORY_DIR,
                app_config.SCREENER_CACHE_DIR,
            )
            try:
                app_config.REPORTS_DIR = root / "data" / "reports"
                app_config.SCREENER_RESULTS_DIR = root / "data" / "screener" / "runs"
                app_config.STOCK_HISTORY_DIR = root / "data" / "history"
                app_config.SCREENER_CACHE_DIR = root / "data" / "cache" / "screener"
                (app_config.REPORTS_DIR / "SPY" / "complete_report.md").parent.mkdir(
                    parents=True
                )
                (app_config.REPORTS_DIR / "SPY" / "complete_report.md").write_text(
                    "report", encoding="utf-8"
                )
                (app_config.SCREENER_RESULTS_DIR / "run1").mkdir(parents=True)
                (
                    app_config.SCREENER_RESULTS_DIR / "run1" / "candidates.csv"
                ).write_text("symbol\nAAPL\n", encoding="utf-8")
                (app_config.STOCK_HISTORY_DIR / "us").mkdir(parents=True)
                (app_config.STOCK_HISTORY_DIR / "us" / "AAPL.csv").write_text(
                    "Date,Close\n", encoding="utf-8"
                )
                (app_config.SCREENER_CACHE_DIR / "checkpoint.json").parent.mkdir(
                    parents=True
                )
                (app_config.SCREENER_CACHE_DIR / "checkpoint.json").write_text(
                    "{}", encoding="utf-8"
                )

                with patch.dict(
                    storage.os.environ,
                    {
                        "STORAGE_BACKEND": "local",
                        "STORAGE_LOCAL_ROOT": storage_dir,
                    },
                    clear=True,
                ):
                    storage.reset_storage_cache()
                    self.assertEqual(migrate_local_data_to_storage.main([]), 0)
                    uploaded = storage.LocalStorage(storage_dir)

                self.assertEqual(
                    uploaded.list(),
                    [
                        "cache/screener/checkpoint.json",
                        "history/us/AAPL.csv",
                        "reports/SPY/complete_report.md",
                        "screener/runs/run1/candidates.csv",
                    ],
                )
            finally:
                (
                    app_config.REPORTS_DIR,
                    app_config.SCREENER_RESULTS_DIR,
                    app_config.STOCK_HISTORY_DIR,
                    app_config.SCREENER_CACHE_DIR,
                ) = original_dirs
                storage.reset_storage_cache()


if __name__ == "__main__":
    unittest.main()
