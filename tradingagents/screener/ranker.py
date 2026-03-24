from __future__ import annotations

import pandas as pd


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


def score_candidates(filtered_df: pd.DataFrame) -> pd.DataFrame:
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

    ranked["total_score"] = (
        ranked["trend_score"] * 0.35
        + ranked["momentum_score"] * 0.30
        + ranked["risk_score"] * 0.20
        + ranked["liquidity_score"] * 0.15
    )
    ranked["strategy_tags"] = ranked.apply(_strategy_tags, axis=1)
    ranked["risk_flags"] = ranked.apply(_risk_flags, axis=1)

    ranked = ranked.sort_values(["total_score", "symbol"], ascending=[False, True]).reset_index(drop=True)
    ranked["global_rank"] = range(1, len(ranked) + 1)
    ranked["market_rank"] = ranked.groupby("market").cumcount() + 1
    return ranked
