import unittest

from diverge.markets import resolve_symbol


class MarketResolutionTests(unittest.TestCase):
    def test_resolves_cn_symbol_by_rule(self):
        resolution = resolve_symbol("600519")

        self.assertEqual(resolution["canonical_symbol"], "600519.SH")
        self.assertEqual(resolution["market"], "cn")
        self.assertEqual(resolution["exchange"], "SH")
        self.assertEqual(resolution["confidence"], "high")

    def test_resolves_us_symbol_by_rule(self):
        resolution = resolve_symbol("BRK.B")

        self.assertEqual(resolution["canonical_symbol"], "BRK.B")
        self.assertEqual(resolution["market"], "us")
        self.assertEqual(resolution["asset_type"], "equity")

    def test_unsupported_numeric_symbol_is_unknown(self):
        resolution = resolve_symbol("0700")

        self.assertEqual(resolution["market"], "unknown")
        self.assertEqual(resolution["confidence"], "low")

    def test_manual_override_uses_standard_resolution_shape(self):
        resolution = resolve_symbol("0700", manual_market="unknown")

        self.assertEqual(resolution["source"], "manual")
        self.assertEqual(resolution["confidence"], "manual")
        self.assertIn("Market was manually overridden.", resolution["warnings"])


if __name__ == "__main__":
    unittest.main()
