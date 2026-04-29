import inspect
import unittest

from diverge.agents.utils.core_stock_tools import get_stock_data
from diverge.agents.utils.fundamental_data_tools import get_fundamentals
from diverge.agents.utils.news_data_tools import get_news
from diverge.agents.utils.technical_indicators_tools import get_indicators


class RoutingContractTests(unittest.TestCase):
    @staticmethod
    def _signature_shape(tool_obj):
        sig = inspect.signature(tool_obj.func)
        return tuple(sig.parameters.keys()), sig.return_annotation

    def test_public_tool_signatures_unchanged(self):
        self.assertEqual(
            self._signature_shape(get_stock_data),
            (("symbol", "start_date", "end_date"), str),
        )
        self.assertEqual(
            self._signature_shape(get_indicators),
            (("symbol", "indicator", "curr_date", "look_back_days"), str),
        )
        self.assertEqual(
            self._signature_shape(get_fundamentals), (("ticker", "curr_date"), str)
        )
        self.assertEqual(
            self._signature_shape(get_news), (("ticker", "start_date", "end_date"), str)
        )


if __name__ == "__main__":
    unittest.main()
