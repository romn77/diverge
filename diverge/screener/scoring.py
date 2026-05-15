from __future__ import annotations

import json

import pandas as pd

from diverge.screener.strategy_config import ScoreComponent


def _winsorized_z(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.notna().sum() < 2:
        return pd.Series([0.0] * len(values), index=values.index)
    lower = numeric.quantile(0.05)
    upper = numeric.quantile(0.95)
    clipped = numeric.clip(lower=lower, upper=upper)
    std = clipped.std(ddof=0)
    if not std or pd.isna(std):
        return pd.Series([0.0] * len(values), index=values.index)
    return (clipped - clipped.mean()) / std


def score_weighted_components(
    df: pd.DataFrame, components: list[ScoreComponent] | tuple[ScoreComponent, ...]
) -> pd.DataFrame:
    result = df.copy()
    raw_score = pd.Series([0.0] * len(result), index=result.index)
    contribution_by_name: dict[str, pd.Series] = {}
    total_weight = (
        sum(max(float(component.weight), 0.0) for component in components) or 1.0
    )
    group_columns = [
        column for column in ("trade_date", "market") if column in result.columns
    ]
    for component in components:
        values = (
            pd.to_numeric(result[component.field], errors="coerce")
            if component.field in result.columns
            else pd.Series([pd.NA] * len(result), index=result.index)
        )
        if component.transform == "zscore":
            if group_columns:
                transformed = values.groupby(
                    [result[column] for column in group_columns]
                ).transform(_winsorized_z)
            else:
                transformed = _winsorized_z(values)
        elif component.transform == "rank_pct":
            transformed = values.rank(pct=True).fillna(0.5) * 2 - 1
        else:
            transformed = values.fillna(0)
        if component.direction == "lower":
            transformed = -transformed
        weighted = transformed.fillna(0) * (float(component.weight) / total_weight)
        contribution_by_name[component.name] = weighted
        raw_score += weighted
    # Compress a typical z-score range into a user-facing 0-100 score.
    result["score"] = (50 + raw_score * 12.5).clip(0, 100).round(4)
    rows = []
    for index in result.index:
        rows.append(
            json.dumps(
                {
                    name: round(float(series.loc[index] * 100), 4)
                    for name, series in contribution_by_name.items()
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    result["score_contributions"] = rows
    return result
