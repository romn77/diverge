from __future__ import annotations

import pandas as pd

from diverge.screener.dsl import evaluate_condition_tree
from diverge.screener.scoring import score_weighted_components
from diverge.screener.signal_builder import build_signal_events
from diverge.screener.strategy_config import ScoreComponent


def test_condition_tree_and_weighted_scoring_build_signal_events():
    frame = pd.DataFrame(
        [
            {
                "symbol": "300001.SZ",
                "market": "cn",
                "trade_date": "2026-05-14",
                "theme_hot_score": 90,
                "amount_ratio_5d": 2.0,
                "ret_20d": 0.12,
                "candidate_type": "leader",
            },
            {
                "symbol": "300002.SZ",
                "market": "cn",
                "trade_date": "2026-05-14",
                "theme_hot_score": 40,
                "amount_ratio_5d": 0.8,
                "ret_20d": -0.03,
                "candidate_type": "watch",
            },
        ]
    )
    condition = {
        "all": [
            {"field": "theme_hot_score", "op": ">=", "value": 70},
            {"field": "amount_ratio_5d", "op": ">", "value": 1},
        ]
    }

    matched = frame.loc[evaluate_condition_tree(frame, condition)]
    scored = score_weighted_components(
        matched,
        [
            ScoreComponent(name="hot", field="theme_hot_score", weight=0.5),
            ScoreComponent(name="momentum", field="ret_20d", weight=0.5),
        ],
    )
    events = build_signal_events(
        scored, strategy_id="strategy_v1", trade_date="2026-05-14"
    )

    assert scored.iloc[0]["score"] == 50
    assert "score_contributions" in scored.columns
    assert events == [
        {
            "event_id": "20260514-strategy_v1-0001",
            "strategy_id": "strategy_v1",
            "trade_date": "2026-05-14",
            "symbol": "300001.SZ",
            "market": "cn",
            "signal_type": "entry_candidate",
            "score": 50.0,
            "rank": 1,
            "candidate_type": "leader",
            "theme_id": None,
            "evidence": [],
            "data_quality_flags": [],
        }
    ]
