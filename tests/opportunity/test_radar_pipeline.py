from __future__ import annotations

import json

import pandas as pd

from diverge.opportunity.radar import run_opportunity_radar


def test_radar_writes_artifacts_and_marks_missing_backtest(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    factor_path = tmp_path / "factors.csv"
    pd.DataFrame(
        [
            {
                "symbol": "300001.SZ",
                "name": "Alpha",
                "market": "cn",
                "trade_date": "2026-05-14",
                "theme_id": "ai_compute",
                "theme_name": "AI Compute",
                "theme_hot_score": 90,
                "theme_capital_score": 80,
                "amount_ratio_5d": 2.0,
                "ret_20d": 0.12,
                "ret_5d": 0.04,
                "breakout_20d": True,
                "volatility_20d": 0.05,
                "moneyflow_net_amount_5d": 10_000_000,
                "float_mv": 1_000_000_000,
                "catalyst_score": 75,
            }
        ]
    ).to_csv(factor_path, index=False)

    result = run_opportunity_radar(
        {"trade_date": "2026-05-14", "factor_snapshot_path": str(factor_path)},
        project_root=tmp_path,
        owner_user_id="user-1",
        tenant_id="tenant-1",
    )

    run_dir = tmp_path / "data" / "opportunity" / "runs" / result["run_id"]
    candidate_pool = json.loads((run_dir / "candidate_pool.json").read_text())
    snapshot = json.loads((run_dir / "backtest_snapshot.json").read_text())
    meta = json.loads((run_dir / "run_meta.json").read_text())

    assert result["candidate_count"] == 1
    assert candidate_pool["candidates"][0]["symbol"] == "300001.SZ"
    assert snapshot["status"] == "unavailable"
    assert "insufficient_sample" in snapshot["data_quality_notes"]
    assert meta["tenant_id"] == "tenant-1"


def test_radar_tolerates_missing_float_mv_in_factor_snapshot(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    factor_path = tmp_path / "factors.csv"
    pd.DataFrame(
        [
            {
                "symbol": "300002.SZ",
                "name": "Beta",
                "market": "cn",
                "trade_date": "2026-05-14",
                "theme_id": "ai_compute",
                "theme_name": "AI Compute",
                "theme_hot_score": 88,
                "theme_capital_score": 76,
                "amount_ratio_5d": 1.8,
                "ret_20d": 0.1,
                "ret_5d": 0.03,
                "breakout_20d": True,
                "volatility_20d": 0.04,
                "moneyflow_net_amount_5d": 7_000_000,
                "catalyst_score": 70,
            }
        ]
    ).to_csv(factor_path, index=False)

    result = run_opportunity_radar(
        {"trade_date": "2026-05-14", "factor_snapshot_path": str(factor_path)},
        project_root=tmp_path,
    )

    run_dir = tmp_path / "data" / "opportunity" / "runs" / result["run_id"]
    candidate_pool = json.loads((run_dir / "candidate_pool.json").read_text())
    meta = json.loads((run_dir / "run_meta.json").read_text())

    assert result["status"] == "completed"
    assert candidate_pool["candidates"][0]["symbol"] == "300002.SZ"
    assert meta["candidate_count"] == 1
