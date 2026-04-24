import unittest

from cli.utils import normalize_ticker_symbol
from tradingagents.agents.utils.agent_utils import build_instrument_context


class TickerSymbolHandlingTests(unittest.TestCase):
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
