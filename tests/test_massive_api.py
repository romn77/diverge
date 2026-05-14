import os
import unittest

import requests
from dotenv import load_dotenv


@unittest.skipUnless(
    os.getenv("RUN_MASSIVE_INTEGRATION_TESTS") == "1",
    "Set RUN_MASSIVE_INTEGRATION_TESTS=1 to run live Massive API checks.",
)
class MassiveApiIntegrationTests(unittest.TestCase):
    def test_fetch_stock_bars(self):
        load_dotenv()
        api_key = os.getenv("MASSIVE_API_KEY")
        if not api_key:
            self.skipTest("MASSIVE_API_KEY is not configured")

        base_url = os.getenv(
            "MASSIVE_BASE_URL", "http://bcprivateserver.site/api/v1"
        ).rstrip("/")
        response = requests.get(
            f"{base_url}/market/stocks/bars",
            headers={"X-API-KEY": api_key},
            params={
                "tickers": ["SMH"],
                "interval": "1Day",
                "start_time": "2016-01-01T00:00:00Z",
            },
            timeout=30,
        )

        print(response.text)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsInstance(response.json(), dict)


if __name__ == "__main__":
    unittest.main()
