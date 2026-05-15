from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DEFAULT_FACTOR_COLUMNS = [
    "symbol",
    "name",
    "market",
    "trade_date",
    "source",
    "as_of_date",
    "loaded_at",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turnover_rate",
    "volume_ratio",
    "float_mv",
    "total_mv",
    "ret_1d",
    "ret_3d",
    "ret_5d",
    "ret_10d",
    "ret_20d",
    "ret_60d",
    "volatility_20d",
    "amount_ratio_5d",
    "amount_ratio_20d",
    "ma_20",
    "ma_60",
    "rsi_14",
    "macd",
    "atr_14",
    "mfi_14",
    "vwma_20",
    "obv",
    "breakout_20d",
    "above_ma20",
    "above_ma60",
    "moneyflow_net_amount",
    "moneyflow_net_amount_5d",
    "moneyflow_net_amount_20d",
    "large_order_net_amount",
    "large_order_buy_ratio",
    "large_order_sell_ratio",
    "theme_id",
    "theme_name",
    "sector",
    "industry",
    "theme_hot_score",
    "theme_capital_score",
    "theme_breadth_score",
    "catalyst_score",
    "data_quality_flags",
]

_COLUMN_ALIASES = {
    "ret_20": "ret_20d",
    "ret_60": "ret_60d",
    "ma20": "ma_20",
    "ma60": "ma_60",
    "rsi": "rsi_14",
    "atr_pct": "atr_14",
    "avg_amount_20d": "amount_ratio_20d",
    "breakout_hit": "breakout_20d",
}


def normalize_factor_snapshot(
    frame: pd.DataFrame, *, trade_date: str | None = None, source: str = "local_cache"
) -> pd.DataFrame:
    result = frame.copy()
    for old, new in _COLUMN_ALIASES.items():
        if old in result.columns and new not in result.columns:
            result[new] = result[old]
    if "market" not in result.columns:
        result["market"] = "cn"
    if "trade_date" not in result.columns:
        result["trade_date"] = (
            trade_date or datetime.now(timezone.utc).date().isoformat()
        )
    if "source" not in result.columns:
        result["source"] = source
    if "as_of_date" not in result.columns:
        result["as_of_date"] = result["trade_date"]
    if "loaded_at" not in result.columns:
        result["loaded_at"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
    if "data_quality_flags" not in result.columns:
        result["data_quality_flags"] = "[]"
    if "moneyflow_float_mv_ratio_5d" not in result.columns:
        numerator = pd.to_numeric(
            result.get("moneyflow_net_amount_5d", 0), errors="coerce"
        )
        denominator = pd.to_numeric(result.get("float_mv", 0), errors="coerce").replace(
            0, pd.NA
        )
        result["moneyflow_float_mv_ratio_5d"] = (numerator / denominator).fillna(0)
    for column in DEFAULT_FACTOR_COLUMNS:
        if column not in result.columns:
            result[column] = pd.NA
    return result


def load_factor_snapshot(path: str | Path) -> pd.DataFrame:
    resolved = Path(path)
    if resolved.suffix == ".parquet":
        return pd.read_parquet(resolved)
    return pd.read_csv(resolved)
