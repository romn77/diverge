from __future__ import annotations

import pandas as pd

from .schema import ScreenRunConfig


BREAKOUT_BASE_BONUS = {
    "platform_breakout": 0.11,
    "box_breakout": 0.11,
    "wedge_breakout": 0.08,
}
BREAKOUT_VOLUME_BONUS = 0.04
BREAKOUT_BONUS_CAP = 0.15


def _safe_zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").astype(float)
    std = numeric.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=series.index)
    return (numeric - numeric.mean()) / std


def _marketwise_zscore(df: pd.DataFrame, raw_column: str, score_column: str) -> pd.DataFrame:
    result = df.copy()
    result[score_column] = result.groupby("market")[raw_column].transform(_safe_zscore)
    return result


def _strategy_tags(row: pd.Series) -> str:
    tags: list[str] = []
    if row["close"] > row["ma20"] and row["ma20"] > row["ma60"]:
        tags.append("trend_up")
    if row["ret_20"] > 0 and row["ret_60"] > 0 and row["macdh"] > 0:
        tags.append("momentum_positive")
    if row["close"] > row["vwma"]:
        tags.append("above_vwma")
    breakout_type = row.get("breakout_type")
    if breakout_type:
        tags.append(str(breakout_type))
    if bool(row.get("breakout_with_volume")):
        tags.append("breakout_with_volume")
    return ",".join(tags)


def _risk_flags(row: pd.Series) -> str:
    flags: list[str] = []
    if row["atr_pct"] > 0.05:
        flags.append("high_atr")
    if row["rsi"] > 70:
        flags.append("rsi_hot")
    if row["rsi"] < 35:
        flags.append("rsi_cold")
    return ",".join(flags)


def _selected_breakout_types(config: ScreenRunConfig | None) -> set[str]:
    if config is None:
        return set()
    return {breakout_type for breakout_type in config.breakout_types}


def _breakout_bonus_parts(row: pd.Series, enabled_breakouts: set[str]) -> tuple[float, float, float]:
    breakout_type = row.get("breakout_type")
    if not enabled_breakouts:
        return 0.0, 0.0, 0.0
    if not bool(row.get("breakout_hit")) or breakout_type not in enabled_breakouts:
        return 0.0, 0.0, 0.0

    base_bonus = float(BREAKOUT_BASE_BONUS.get(str(breakout_type), 0.0))
    volume_bonus = BREAKOUT_VOLUME_BONUS if bool(row.get("breakout_with_volume")) else 0.0
    breakout_bonus = min(base_bonus + volume_bonus, BREAKOUT_BONUS_CAP)
    return base_bonus, volume_bonus, breakout_bonus


def score_candidates(
    filtered_df: pd.DataFrame,
    config: ScreenRunConfig | None = None,
) -> pd.DataFrame:
    ranked = filtered_df.copy()
    ranked["trend_raw"] = ((ranked["close"] / ranked["ma20"]) - 1 + (ranked["close"] / ranked["ma60"]) - 1) / 2
    ranked["momentum_raw"] = (
        ranked["ret_20"] + ranked["ret_60"] + ranked["macdh"] + (-abs(ranked["rsi"] - 55) / 100)
    ) / 4
    ranked["risk_raw"] = -ranked["atr_pct"]
    ranked["liquidity_raw"] = (ranked["avg_amount_20d"] + ((ranked["close"] / ranked["vwma"]) - 1)) / 2

    ranked = _marketwise_zscore(ranked, "trend_raw", "trend_score")
    ranked = _marketwise_zscore(ranked, "momentum_raw", "momentum_score")
    ranked = _marketwise_zscore(ranked, "risk_raw", "risk_score")
    ranked = _marketwise_zscore(ranked, "liquidity_raw", "liquidity_score")

    ranked["base_total_score"] = (
        ranked["trend_score"] * 0.35
        + ranked["momentum_score"] * 0.30
        + ranked["risk_score"] * 0.20
        + ranked["liquidity_score"] * 0.15
    )
    selected_breakouts = _selected_breakout_types(config)
    breakout_bonus_parts = ranked.apply(
        lambda row: _breakout_bonus_parts(row, selected_breakouts),
        axis=1,
        result_type="expand",
    )
    breakout_bonus_parts.columns = [
        "breakout_base_bonus",
        "breakout_volume_bonus",
        "breakout_bonus",
    ]
    ranked[breakout_bonus_parts.columns] = breakout_bonus_parts
    ranked["total_score"] = ranked["base_total_score"] + ranked["breakout_bonus"]
    ranked["strategy_tags"] = ranked.apply(_strategy_tags, axis=1)
    ranked["risk_flags"] = ranked.apply(_risk_flags, axis=1)

    ranked = ranked.sort_values(["total_score", "symbol"], ascending=[False, True]).reset_index(drop=True)
    ranked["global_rank"] = range(1, len(ranked) + 1)
    ranked["market_rank"] = ranked.groupby("market").cumcount() + 1
    return ranked
