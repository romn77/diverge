import unittest

from diverge.agents.utils.agent_utils import build_instrument_context
from diverge.common.symbols import (
    detect_market,
    normalize_symbol_for_vendor,
    normalize_ticker_symbol,
    parse_and_normalize_cn_ticker,
    resolve_symbol_market,
)


class SymbolUtilityTests(unittest.TestCase):
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

    def test_parse_plain_growth_board_ticker_with_302_prefix(self):
        parsed = parse_and_normalize_cn_ticker("302132")

        self.assertEqual(parsed["raw"], "302132")
        self.assertEqual(parsed["exchange"], "SZ")
        self.assertEqual(parsed["tushare"], "302132.SZ")
        self.assertEqual(parsed["yfinance"], "302132.SZ")

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

    def test_resolve_symbol_market_accepts_aliases(self):
        self.assertEqual(resolve_symbol_market("600519", "sse"), "cn")
        self.assertEqual(resolve_symbol_market("AAPL", "nasdaq"), "us")
        self.assertEqual(resolve_symbol_market("MSFT"), "us")

    def test_normalize_symbol_for_vendor(self):
        self.assertEqual(
            normalize_symbol_for_vendor("600519.SH", market="cn", vendor="akshare"),
            "600519",
        )

    def test_normalize_ticker_symbol_preserves_exchange_suffix(self):
        self.assertEqual(normalize_ticker_symbol(" cnc.to "), "CNC.TO")

    def test_normalize_ticker_symbol_rejects_path_components(self):
        for ticker in ("../../SPY", "/SPY", "SPY/QQQ", r"SPY\QQQ", "SPY..QQQ"):
            with self.subTest(ticker=ticker):
                with self.assertRaises(ValueError):
                    normalize_ticker_symbol(ticker)

    def test_normalize_ticker_symbol_accepts_common_symbol_punctuation(self):
        self.assertEqual(normalize_ticker_symbol(" brk-b "), "BRK-B")
        self.assertEqual(normalize_ticker_symbol("600519.sh"), "600519.SH")

    def test_build_instrument_context_mentions_exact_symbol(self):
        context = build_instrument_context("7203.T")
        self.assertIn("7203.T", context)
        self.assertIn("exchange suffix", context)


if __name__ == "__main__":
    unittest.main()
