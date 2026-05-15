from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from diverge.opportunity.storage import write_json, write_table


def write_backtest_artifacts(run_dir: Path, snapshot: dict[str, Any]) -> dict[str, str]:
    write_json(
        run_dir / "backtest_snapshot.json",
        {key: value for key, value in snapshot.items() if key != "signal_outcomes"},
    )
    write_json(run_dir / "backtest_metrics.json", snapshot.get("holding_periods") or {})
    outcomes = snapshot.get("signal_outcomes") or []
    if outcomes:
        write_table(run_dir / "signal_outcomes.parquet", pd.DataFrame(outcomes))
    return {
        "backtest_snapshot": "backtest_snapshot.json",
        "backtest_metrics": "backtest_metrics.json",
        "signal_outcomes": "signal_outcomes.parquet" if outcomes else "",
    }
