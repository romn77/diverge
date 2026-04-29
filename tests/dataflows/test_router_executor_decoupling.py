import copy
import unittest

import diverge.dataflows.interface as interface
from diverge.dataflows.vendor_errors import VendorRetryableError


class RouterExecutorDecouplingTests(unittest.TestCase):
    def test_execute_vendor_chain_isolated_from_selection(self):
        vendor_methods = copy.deepcopy(interface.VENDOR_METHODS)

        calls = []

        def first_vendor(symbol, start_date, end_date):
            calls.append(("akshare", symbol))
            raise VendorRetryableError("temporary")

        def second_vendor(symbol, start_date, end_date):
            calls.append(("tushare", symbol))
            return "ok"

        vendor_methods["get_stock_data"] = {
            "akshare": first_vendor,
            "tushare": second_vendor,
        }

        result = interface.execute_vendor_chain(
            method="get_stock_data",
            market="cn",
            symbol="600519",
            resolved_args=("600519", "2024-01-01", "2024-02-01"),
            resolved_kwargs={},
            vendors=["akshare", "tushare"],
            vendor_methods=vendor_methods,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(calls[0], ("akshare", "600519"))
        self.assertEqual(calls[1], ("tushare", "600519.SH"))


if __name__ == "__main__":
    unittest.main()
