from __future__ import annotations

import pandas as pd

from .presets import resolve_ranking_profile
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


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(pd.NA, index=df.index, dtype="Float64")
    return pd.to_numeric(df[column], errors="coerce")


def _positive_quality(series: pd.Series, cap: float | None = None) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if cap is not None:
        numeric = numeric.clip(upper=cap)
    return numeric


def _inverse_valuation(series: pd.Series, cap: float | None = None) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    numeric = numeric.where(numeric > 0)
    if cap is not None:
        numeric = numeric.clip(upper=cap)
    return -numeric


def _fundamental_raw(df: pd.DataFrame) -> pd.Series:
    components = pd.DataFrame(index=df.index)
    components["valuation_pe"] = _inverse_valuation(_numeric_column(df, "pe_ttm"), cap=120)
    components["valuation_ps"] = _inverse_valuation(_numeric_column(df, "ps_ttm"), cap=80)
    components["valuation_pb"] = _inverse_valuation(_numeric_column(df, "pb"), cap=80)
    components["valuation_peg"] = _inverse_valuation(_numeric_column(df, "peg"), cap=10)
    components["quality_roe"] = _positive_quality(_numeric_column(df, "roe"), cap=1.0)
    components["quality_gross_margin"] = _positive_quality(_numeric_column(df, "gross_margin"), cap=1.0)
    components["quality_net_margin"] = _positive_quality(_numeric_column(df, "net_margin"), cap=1.0)
    components["growth_revenue"] = _positive_quality(_numeric_column(df, "revenue_growth_yoy"), cap=3.0)
    components["growth_income"] = _positive_quality(_numeric_column(df, "net_income_growth_yoy"), cap=3.0)
    components["balance_current"] = _positive_quality(_numeric_column(df, "current_ratio"), cap=5.0)
    components["balance_debt"] = -_positive_quality(_numeric_column(df, "debt_to_assets"), cap=2.0)
    return components.mean(axis=1, skipna=True).fillna(0.0)


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


def _pattern_raw(row: pd.Series) -> float:
    score = 0.0
    if bool(row.get("breakout_hit")):
        score += 1.0
    if bool(row.get("breakout_with_volume")):
        score += 0.4
    if row["close"] > row["ma20"] and row["ma20"] > row["ma60"]:
        score += 0.3
    if row["close"] > row["vwma"]:
        score += 0.2
    return score


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


def _score_contributions(row: pd.Series, weights: dict[str, float] | None) -> str:
    if not weights:
        payload = {
            "trend": float(row.get("trend_score", 0.0) * 0.35),
            "momentum": float(row.get("momentum_score", 0.0) * 0.30),
            "risk": float(row.get("risk_score", 0.0) * 0.20),
            "liquidity": float(row.get("liquidity_score", 0.0) * 0.15),
            "pattern": float(row.get("breakout_bonus", 0.0)),
            "fundamental": float(row.get("fundamental_score", 0.0) * 0.0),
        }
    else:
        payload = {
            "trend": float(row.get("trend_score", 0.0) * weights.get("trend", 0.0)),
            "momentum": float(row.get("momentum_score", 0.0) * weights.get("momentum", 0.0)),
            "pattern": float(row.get("pattern_score", 0.0) * weights.get("pattern", 0.0)),
            "liquidity": float(row.get("liquidity_score", 0.0) * weights.get("liquidity", 0.0)),
            "risk": float(row.get("risk_score", 0.0) * weights.get("risk", 0.0)),
            "fundamental": float(row.get("fundamental_score", 0.0) * weights.get("fundamental", 0.0)),
        }
    return ",".join(
        f"{key}:{value:.4f}"
        for key, value in payload.items()
        if value is not None and value != 0.0
    )


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
    ranked["pattern_raw"] = ranked.apply(_pattern_raw, axis=1)
    ranked["fundamental_raw"] = _fundamental_raw(ranked)

    ranked = _marketwise_zscore(ranked, "trend_raw", "trend_score")
    ranked = _marketwise_zscore(ranked, "momentum_raw", "momentum_score")
    ranked = _marketwise_zscore(ranked, "risk_raw", "risk_score")
    ranked = _marketwise_zscore(ranked, "liquidity_raw", "liquidity_score")
    ranked = _marketwise_zscore(ranked, "pattern_raw", "pattern_score")
    ranked = _marketwise_zscore(ranked, "fundamental_raw", "fundamental_score")

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
    ranking_profile = resolve_ranking_profile(config.ranking_profile_id if config is not None else None)
    weights = ranking_profile["weights"] if ranking_profile is not None else None
    ranked["technical_score"] = (ranked["trend_score"] + ranked["momentum_score"]) / 2
    if weights is None:
        ranked["total_score"] = ranked["base_total_score"] + ranked["breakout_bonus"]
        ranked["ranking_profile_id"] = None
    else:
        ranked["total_score"] = (
            ranked["trend_score"] * weights["trend"]
            + ranked["momentum_score"] * weights["momentum"]
            + ranked["pattern_score"] * weights["pattern"]
            + ranked["liquidity_score"] * weights["liquidity"]
            + ranked["risk_score"] * weights["risk"]
            + ranked["fundamental_score"] * weights.get("fundamental", 0.0)
        )
        ranked["ranking_profile_id"] = ranking_profile["id"]
    ranked["score_contributions"] = ranked.apply(
        lambda row: _score_contributions(row, weights),
        axis=1,
    )
    ranked["strategy_tags"] = ranked.apply(_strategy_tags, axis=1)
    ranked["risk_flags"] = ranked.apply(_risk_flags, axis=1)

    ranked = ranked.sort_values(["total_score", "symbol"], ascending=[False, True]).reset_index(drop=True)
    ranked["global_rank"] = range(1, len(ranked) + 1)
    ranked["market_rank"] = ranked.groupby("market").cumcount() + 1
    return ranked
