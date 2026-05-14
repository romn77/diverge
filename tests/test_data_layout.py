from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from diverge.config.paths import (
    resolve_data_cache_dir,
    resolve_eval_results_dir,
    resolve_manifest_path,
    resolve_reports_dir,
)
from diverge.data_layout import resolve_manifest_path as legacy_resolve_manifest_path
from diverge.markets import resolve_symbol
from diverge.default_config import DEFAULT_CONFIG
from diverge.screener.schema import ScreenRunConfig
from diverge import trade_feedback


def test_screen_run_config_defaults_to_data_storage_layout(tmp_path):
    with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}, clear=True):
        config = ScreenRunConfig(
            markets=["cn"],
            as_of_date="2026-03-24",
            top_k=20,
        )

    assert config.output_dir == str(tmp_path / "screener" / "runs")
    assert config.cache_dir == str(tmp_path / "cache" / "screener")
    assert config.history_dir == str(tmp_path / "history")


def test_trade_feedback_root_defaults_under_data_reports(tmp_path):
    with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(trade_feedback, "PROJECT_ROOT", tmp_path),
    ):
        root = trade_feedback.get_trade_feedback_root()

    assert root == Path(tmp_path) / "data" / "reports" / ".trade_feedback"


def test_default_config_uses_data_eval_results_for_legacy_analysis_outputs():
    assert Path(DEFAULT_CONFIG["eval_results_dir"]) == resolve_eval_results_dir()
    assert Path(DEFAULT_CONFIG["data_cache_dir"]) == resolve_data_cache_dir()


def test_path_resolvers_derive_from_data_dir_only(tmp_path):
    data_dir = tmp_path / "data"
    legacy_reports_dir = tmp_path / "legacy-reports"
    with patch.dict(
        os.environ,
        {"DATA_DIR": str(data_dir), "REPORTS_DIR": str(legacy_reports_dir)},
        clear=True,
    ):
        assert resolve_reports_dir() == data_dir / "reports"


def test_resolve_manifest_path_requires_existing_file(tmp_path):
    with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}, clear=True):
        assert resolve_manifest_path("us", tmp_path, require_exists=True) is None

        manifest_path = tmp_path / "manifest" / "us.csv"
        manifest_path.parent.mkdir()
        manifest_path.write_text("symbol\nAAPL\n", encoding="utf-8")

        assert (
            resolve_manifest_path("us", tmp_path, require_exists=True) == manifest_path
        )


def test_data_layout_reexports_central_path_resolvers():
    assert legacy_resolve_manifest_path is resolve_manifest_path


def test_symbol_resolver_uses_data_dir_manifest_default(tmp_path):
    manifest_path = tmp_path / "manifest" / "us.csv"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        "symbol,name,exchange,asset_type\nXYZ,Example Corp,NASDAQ,equity\n",
        encoding="utf-8",
    )

    with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}, clear=True):
        resolution = resolve_symbol("XYZ")

    assert resolution["market"] == "us"
    assert resolution["exchange"] == "NASDAQ"
    assert resolution["source"] == "manifest"


def test_symbol_resolver_refreshes_data_dir_manifest_changes(tmp_path):
    manifest_path = tmp_path / "manifest" / "us.csv"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        "symbol,name,exchange,asset_type\nXYZ,Example Corp,NASDAQ,equity\n",
        encoding="utf-8",
    )

    with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}, clear=True):
        assert resolve_symbol("XYZ")["source"] == "manifest"

        manifest_path.write_text(
            "symbol,name,exchange,asset_type\nABCD,Another Example,NASDAQ,equity\n",
            encoding="utf-8",
        )
        resolution = resolve_symbol("ABCD")

    assert resolution["market"] == "us"
    assert resolution["source"] == "manifest"
