import unittest
from unittest.mock import patch

import requests

from diverge.dataflows.alpha_vantage_common import (
    ALPHA_VANTAGE_TIMEOUT_SECONDS,
    _make_api_request,
)
from diverge.dataflows.vendor_errors import VendorRetryableError


class AlphaVantageCommonTests(unittest.TestCase):
    def test_make_api_request_sets_explicit_timeout(self):
        class Response:
            text = "timestamp,open\n2026-04-24,1.0\n"

            def raise_for_status(self):
                return None

        with patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"}):
            with patch(
                "diverge.dataflows.alpha_vantage_common.requests.get",
                return_value=Response(),
            ) as get:
                payload = _make_api_request("TIME_SERIES_INTRADAY", {"symbol": "MSFT"})

        self.assertEqual(payload, Response.text)
        self.assertEqual(get.call_args.kwargs["timeout"], ALPHA_VANTAGE_TIMEOUT_SECONDS)

    def test_make_api_request_maps_request_failures_to_retryable_error(self):
        with patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test-key"}):
            with patch(
                "diverge.dataflows.alpha_vantage_common.requests.get",
                side_effect=requests.Timeout("slow"),
            ):
                with self.assertRaises(VendorRetryableError):
                    _make_api_request("TIME_SERIES_INTRADAY", {"symbol": "MSFT"})


if __name__ == "__main__":
    unittest.main()
