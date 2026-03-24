from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cli.main import app
from tradingagents.screener.schema import ScreenRunResult


runner = CliRunner()


def test_screen_command_requires_us_manifest_for_us_market():
    result = runner.invoke(
        app,
        [
            "screen",
            "--date",
            "2026-03-24",
            "--markets",
            "cn,us",
            "--top-k",
            "20",
        ],
    )

    assert result.exit_code != 0
    assert "us-manifest" in result.output


def test_screen_command_prints_progress_and_result_summary():
    def fake_run_screen(config, progress_callback=None):
        if progress_callback is not None:
            progress_callback("history", 1, 2, "600519.SH")
            progress_callback("history", 2, 2, "AAPL")

        return ScreenRunResult(
            run_dir=Path("/tmp/results/screener/20260324_214530"),
            universe_count_by_market={"cn": 1, "us": 1},
            fetch_failed_count=1,
            filtered_count_by_reason={"fetch_failed": 1, "illiquid_us": 2},
            candidate_count=2,
            candidate_preview=[
                {
                    "symbol": "600519.SH",
                    "market": "cn",
                    "global_rank": 1,
                    "total_score": 1.23,
                },
                {
                    "symbol": "AAPL",
                    "market": "us",
                    "global_rank": 2,
                    "total_score": 0.91,
                },
            ],
        )

    with patch("cli.main.run_screen", side_effect=fake_run_screen):
        result = runner.invoke(
            app,
            [
                "screen",
                "--date",
                "2026-03-24",
                "--markets",
                "cn,us",
                "--top-k",
                "20",
                "--limit-per-market",
                "50",
                "--us-manifest",
                "/tmp/us_manifest.csv",
            ],
        )

    assert result.exit_code == 0
    assert "history 1/2" in result.output
    assert "Universe counts" in result.output
    assert "fetch_failed: 1" in result.output
    assert "600519.SH" in result.output
    assert "/tmp/results/screener/20260324_214530" in result.output
