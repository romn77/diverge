from __future__ import annotations

from typing import Any

import pandas as pd

from diverge.opportunity.config import load_theme_registry


def theme_lookup() -> dict[str, dict[str, Any]]:
    registry = load_theme_registry()
    lookup: dict[str, dict[str, Any]] = {}
    for theme in registry.get("themes", []):
        if not isinstance(theme, dict):
            continue
        theme_id = str(theme.get("theme_id") or "").strip()
        if not theme_id:
            continue
        keys = {theme_id, str(theme.get("theme_name") or "").strip()}
        keys.update(str(alias).strip() for alias in theme.get("aliases", []) or [])
        keys.update(
            str(source_id).strip() for source_id in theme.get("source_ids", []) or []
        )
        for key in keys:
            if key:
                lookup[key.lower()] = theme
    return lookup


def normalize_theme(
    theme_id: str | None, theme_name: str | None = None
) -> tuple[str, str]:
    lookup = theme_lookup()
    for raw in (theme_id, theme_name):
        key = str(raw or "").strip().lower()
        if key in lookup:
            theme = lookup[key]
            return str(theme.get("theme_id")), str(theme.get("theme_name"))
    fallback_id = str(theme_id or theme_name or "unmapped").strip() or "unmapped"
    return fallback_id, str(theme_name or fallback_id)


def build_theme_radar(
    candidates: pd.DataFrame, *, trade_date: str, market: str
) -> dict[str, Any]:
    themes: list[dict[str, Any]] = []
    if not candidates.empty and "theme_id" in candidates.columns:
        for raw_theme_id, group in candidates.groupby("theme_id", dropna=False):
            theme_id, theme_name = normalize_theme(
                str(raw_theme_id or ""),
                str(
                    group.get("theme_name", pd.Series([raw_theme_id])).iloc[0]
                    if len(group)
                    else raw_theme_id
                ),
            )
            top = group.sort_values("score", ascending=False).head(5)
            hot_score = float(
                group.get("theme_hot_score", pd.Series([0])).fillna(0).mean()
            )
            capital_score = float(
                group.get("theme_capital_score", pd.Series([0])).fillna(0).mean()
            )
            themes.append(
                {
                    "theme_id": theme_id,
                    "theme_name": theme_name,
                    "hot_score": round(hot_score, 2),
                    "capital_score": round(capital_score, 2),
                    "momentum_score": round(
                        float(
                            group.get("ret_20d", pd.Series([0])).fillna(0).mean() * 100
                        ),
                        2,
                    ),
                    "breadth_score": min(100, int(len(group) * 10)),
                    "catalyst_score": round(
                        float(
                            group.get("catalyst_score", pd.Series([0])).fillna(0).mean()
                        ),
                        2,
                    ),
                    "stage": "expansion" if hot_score >= 70 else "warming_up",
                    "leaders": top.get("symbol", pd.Series(dtype=str))
                    .astype(str)
                    .head(3)
                    .tolist(),
                    "watch_symbols": top.get("symbol", pd.Series(dtype=str))
                    .astype(str)
                    .iloc[3:5]
                    .tolist(),
                    "backtest_summary": None,
                    "risk_flags": ["short_term_overheated"] if hot_score >= 85 else [],
                }
            )
    themes.sort(key=lambda row: float(row.get("hot_score") or 0), reverse=True)
    return {"trade_date": trade_date, "market": market, "themes": themes}


def build_market_pulse(
    theme_radar: dict[str, Any], *, trade_date: str, market: str
) -> dict[str, Any]:
    themes = list(theme_radar.get("themes") or [])
    top_names = [str(theme.get("theme_name")) for theme in themes[:3]]
    regime = (
        "risk_on"
        if any(float(theme.get("hot_score") or 0) >= 70 for theme in themes)
        else "neutral"
    )
    summary = (
        f"Top themes: {', '.join(top_names)}."
        if top_names
        else "No high-confidence opportunity theme was detected from the prepared cache."
    )
    return {
        "trade_date": trade_date,
        "market": market,
        "market_regime": regime,
        "summary": summary,
        "top_themes": [str(theme.get("theme_id")) for theme in themes[:5]],
        "risk_notes": ["Some hot themes may be short-term overheated."]
        if any(theme.get("risk_flags") for theme in themes)
        else [],
        "data_quality_notes": [],
    }
