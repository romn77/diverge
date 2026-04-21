from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from tradingagents.data_layout import DEFAULT_EVAL_RESULTS_DIR
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screener.schema import ScreenRunConfig
from tradingagents import trade_feedback


def test_screen_run_config_defaults_to_data_storage_layout():
    config = ScreenRunConfig(
        markets=["cn"],
        as_of_date="2026-03-24",
        top_k=20,
    )

    assert config.output_dir == "./data/screener/runs"
    assert config.cache_dir == "./data/cache/screener"
    assert config.history_dir == "./data/history"


def test_trade_feedback_root_defaults_under_data_reports(tmp_path):
    with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(trade_feedback, "PROJECT_ROOT", tmp_path),
    ):
        root = trade_feedback.get_trade_feedback_root()

    assert root == Path(tmp_path) / "data" / "reports" / ".trade_feedback"


def test_default_config_uses_data_eval_results_for_legacy_analysis_outputs():
    assert DEFAULT_CONFIG["eval_results_dir"] == DEFAULT_EVAL_RESULTS_DIR
