import unittest
from unittest.mock import ANY, patch

import pandas as pd

from diverge.dataflows import y_finance


class IndicatorSourceDecouplingTests(unittest.TestCase):
    def _sample_ohlcv(self):
        return pd.DataFrame(
            {
                "Date": pd.to_datetime(["2024-01-03", "2024-01-04", "2024-01-05"]),
                "Open": [10.0, 10.5, 11.0],
                "High": [10.2, 10.8, 11.3],
                "Low": [9.8, 10.2, 10.7],
                "Close": [10.1, 10.6, 11.1],
                "Volume": [1000, 1200, 1300],
            }
        )

    def test_indicator_path_uses_shared_ohlcv_fetcher(self):
        with patch.object(
            y_finance, "_fetch_yfinance_ohlcv_df", return_value=self._sample_ohlcv()
        ) as mocked:
            result = y_finance.get_stock_stats_indicators_window(
                "AAPL", "rsi", "2024-01-05", 2
            )

        self.assertIn("rsi", result.lower())
        mocked.assert_called_once_with(
            "AAPL",
            ANY,
            ANY,
            use_cache=True,
            auto_adjust=True,
        )

    def test_stock_data_path_uses_shared_ohlcv_fetcher(self):
        with patch.object(
            y_finance, "_fetch_yfinance_ohlcv_df", return_value=self._sample_ohlcv()
        ) as mocked:
            result = y_finance.get_YFin_data_online("AAPL", "2024-01-03", "2024-01-06")

        self.assertIn("Stock data for AAPL", result)
        mocked.assert_called_once_with(
            "AAPL",
            "2024-01-03",
            "2024-01-06",
            use_cache=True,
            auto_adjust=False,
        )


if __name__ == "__main__":
    unittest.main()
