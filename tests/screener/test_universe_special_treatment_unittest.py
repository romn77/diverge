import unittest
from unittest.mock import Mock, patch

import pandas as pd

from diverge.screener.universe import load_cn_universe


class SpecialTreatmentUniverseTests(unittest.TestCase):
    def test_load_cn_universe_filters_special_treatment_names_from_tushare(self):
        mock_client = Mock()
        mock_client.stock_basic.return_value = pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "name": "Ping An Bank",
                    "exchange": "SZSE",
                    "industry": "Banking",
                    "list_date": "19910403",
                },
                {
                    "ts_code": "000004.SZ",
                    "name": "ST Guonong",
                    "exchange": "SZSE",
                    "industry": "Agriculture",
                    "list_date": "19901201",
                },
                {
                    "ts_code": "600001.SH",
                    "name": "*ST Example",
                    "exchange": "SSE",
                    "industry": "Industry",
                    "list_date": "19920101",
                },
            ]
        )

        with patch(
            "diverge.screener.universe.get_tushare_pro_client",
            return_value=mock_client,
        ):
            result = load_cn_universe()

        self.assertEqual(list(result["symbol"]), ["000001.SZ"])
        self.assertEqual(list(result["name"]), ["Ping An Bank"])

    def test_load_cn_universe_filters_special_treatment_names_from_akshare(self):
        akshare_df = pd.DataFrame(
            [
                {
                    "code": "000001",
                    "name": "Ping An Bank",
                },
                {
                    "code": "000004",
                    "name": "ST Guonong",
                },
                {
                    "code": "600001",
                    "name": "*ST Example",
                },
            ]
        )

        with patch(
            "diverge.screener.universe._load_akshare_cn_universe_rows",
            return_value=akshare_df,
        ):
            result = load_cn_universe(data_source="akshare")

        self.assertEqual(list(result["symbol"]), ["000001.SZ"])
        self.assertEqual(list(result["name"]), ["Ping An Bank"])


if __name__ == "__main__":
    unittest.main()
