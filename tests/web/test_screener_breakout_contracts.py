import unittest
from unittest.mock import patch

from web.backend import main as backend_main


class ScreenerBreakoutContractTests(unittest.TestCase):
    def tearDown(self):
        backend_main.screener_tasks.clear()

    def test_screener_config_options_expose_breakout_choices_and_default_selection(self):
        payload = backend_main._get_screener_config_options_payload()

        self.assertEqual(
            [option["value"] for option in payload["breakout_types"]],
            ["platform_breakout", "box_breakout", "wedge_breakout"],
        )
        self.assertEqual(payload["defaults"]["breakout_types"], [])

    def test_create_screener_task_preserves_breakout_type_selection(self):
        payload = {
            "markets": ["cn"],
            "as_of_date": "2026-03-24",
            "top_k": 20,
            "cn_data_source": "akshare",
            "breakout_types": ["platform_breakout", "wedge_breakout"],
        }

        with (
            patch("web.backend.main._require_screener_user", return_value=None),
            patch("web.backend.main._start_screener_task_thread"),
        ):
            body = backend_main.create_screener_task(
                backend_main.ScreenTaskCreatePayload(**payload)
            )

        task = backend_main.screener_tasks[body["task_id"]]
        self.assertEqual(
            task.request_payload["breakout_types"],
            ["platform_breakout", "wedge_breakout"],
        )
        self.assertEqual(
            task.config_payload["breakout_types"],
            ["platform_breakout", "wedge_breakout"],
        )
