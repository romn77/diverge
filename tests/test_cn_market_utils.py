import unittest

from tradingagents.dataflows.cn_market_utils import (
    detect_market,
    parse_and_normalize_cn_ticker,
)


class TickerParsingTests(unittest.TestCase):
    def test_parse_plain_shanghai_ticker(self):
        parsed = parse_and_normalize_cn_ticker("600519")

        self.assertEqual(parsed["raw"], "600519")
        self.assertEqual(parsed["exchange"], "SH")
        self.assertEqual(parsed["akshare"], "600519")
        self.assertEqual(parsed["tushare"], "600519.SH")
        self.assertEqual(parsed["yfinance"], "600519.SS")

    def test_parse_prefixed_and_suffixed_tickers(self):
        sh_prefixed = parse_and_normalize_cn_ticker("sh600519")
        sz_suffixed = parse_and_normalize_cn_ticker("000001.SZ")

        self.assertEqual(sh_prefixed["tushare"], "600519.SH")
        self.assertEqual(sz_suffixed["akshare"], "000001")
        self.assertEqual(sz_suffixed["yfinance"], "000001.SZ")

    def test_parse_plain_beijing_exchange_ticker_with_920_prefix(self):
        parsed = parse_and_normalize_cn_ticker("920000")

        self.assertEqual(parsed["raw"], "920000")
        self.assertEqual(parsed["exchange"], "BJ")
        self.assertEqual(parsed["tushare"], "920000.BJ")
        self.assertEqual(parsed["yfinance"], "920000.BJ")

    def test_detect_market(self):
        self.assertEqual(detect_market("600519"), "cn")
        self.assertEqual(detect_market("000001.SZ"), "cn")
        self.assertEqual(detect_market("AAPL"), "us")
        self.assertEqual(detect_market("BRK.B"), "us")


if __name__ == "__main__":
    unittest.main()
