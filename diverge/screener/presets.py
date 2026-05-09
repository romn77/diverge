from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_FILTER_PRESET_SELECTIONS: dict[str, str] = {
    "rsi": "any",
    "ma20_position": "any",
    "ma60_position": "any",
    "ma_alignment": "any",
    "ret_20": "any",
    "ret_60": "any",
    "volatility": "any",
    "liquidity": "any",
    "pattern": "any",
    "volume": "any",
    "pe_ttm": "any",
    "ps_ttm": "any",
    "pb": "any",
    "peg": "any",
    "roe": "any",
    "gross_margin": "any",
    "net_margin": "any",
    "revenue_growth_yoy": "any",
    "net_income_growth_yoy": "any",
    "current_ratio": "any",
    "debt_to_assets": "any",
}

DEFAULT_RANKING_PROFILE_ID = "technical_pattern_balanced"

FILTER_PRESET_GROUPS: list[dict[str, Any]] = [
    {
        "id": "rsi",
        "label": "RSI (14)",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Strength >= 60",
                "value": "strength_60",
                "condition": {"field": "rsi", "op": ">=", "value": 60},
            },
            {
                "label": "Overbought >= 70",
                "value": "overbought_70",
                "condition": {"field": "rsi", "op": ">=", "value": 70},
            },
            {
                "label": "Overbought >= 80",
                "value": "overbought_80",
                "condition": {"field": "rsi", "op": ">=", "value": 80},
            },
            {
                "label": "Overbought >= 90",
                "value": "overbought_90",
                "condition": {"field": "rsi", "op": ">=", "value": 90},
            },
            {
                "label": "Weakness <= 40",
                "value": "weakness_40",
                "condition": {"field": "rsi", "op": "<=", "value": 40},
            },
            {
                "label": "Oversold <= 30",
                "value": "oversold_30",
                "condition": {"field": "rsi", "op": "<=", "value": 30},
            },
            {
                "label": "Oversold <= 20",
                "value": "oversold_20",
                "condition": {"field": "rsi", "op": "<=", "value": 20},
            },
            {
                "label": "Oversold <= 10",
                "value": "oversold_10",
                "condition": {"field": "rsi", "op": "<=", "value": 10},
            },
            {
                "label": "Not Overbought < 70",
                "value": "not_overbought_70",
                "condition": {"field": "rsi", "op": "<", "value": 70},
            },
            {
                "label": "Not Oversold > 30",
                "value": "not_oversold_30",
                "condition": {"field": "rsi", "op": ">", "value": 30},
            },
        ],
    },
    {
        "id": "ma20_position",
        "label": "MA20",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Price > MA20",
                "value": "price_above_ma20",
                "condition": {"field": "close", "op": ">", "compare_field": "ma20"},
            },
            {
                "label": "Near MA20 within +/-3%",
                "value": "near_ma20_3pct",
                "condition": {
                    "field": "close",
                    "op": "within_pct",
                    "compare_field": "ma20",
                    "value": 0.03,
                },
            },
            {
                "label": "Below MA20",
                "value": "below_ma20",
                "condition": {"field": "close", "op": "<", "compare_field": "ma20"},
            },
        ],
    },
    {
        "id": "ma60_position",
        "label": "MA60",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Price > MA60",
                "value": "price_above_ma60",
                "condition": {"field": "close", "op": ">", "compare_field": "ma60"},
            },
            {
                "label": "Below MA60",
                "value": "below_ma60",
                "condition": {"field": "close", "op": "<", "compare_field": "ma60"},
            },
        ],
    },
    {
        "id": "ma_alignment",
        "label": "MA Alignment",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Bullish Alignment: Price > MA20 > MA60",
                "value": "bullish_alignment",
                "conditions": [
                    {"field": "close", "op": ">", "compare_field": "ma20"},
                    {"field": "ma20", "op": ">", "compare_field": "ma60"},
                ],
            },
        ],
    },
    {
        "id": "ret_20",
        "label": "20D Return",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "20D Return > 0%",
                "value": "ret20_positive",
                "condition": {"field": "ret_20", "op": ">", "value": 0},
            },
            {
                "label": "20D Return >= 5%",
                "value": "ret20_5",
                "condition": {"field": "ret_20", "op": ">=", "value": 0.05},
            },
            {
                "label": "20D Return < 0%",
                "value": "ret20_negative",
                "condition": {"field": "ret_20", "op": "<", "value": 0},
            },
        ],
    },
    {
        "id": "ret_60",
        "label": "60D Return",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "60D Return > 0%",
                "value": "ret60_positive",
                "condition": {"field": "ret_60", "op": ">", "value": 0},
            },
            {
                "label": "60D Return >= 10%",
                "value": "ret60_10",
                "condition": {"field": "ret_60", "op": ">=", "value": 0.10},
            },
        ],
    },
    {
        "id": "volatility",
        "label": "Volatility",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Low Volatility: ATR% <= 2%",
                "value": "atr_low_2",
                "condition": {"field": "atr_pct", "op": "<=", "value": 0.02},
            },
            {
                "label": "Normal Volatility: ATR% <= 4%",
                "value": "atr_normal_4",
                "condition": {"field": "atr_pct", "op": "<=", "value": 0.04},
            },
            {
                "label": "High Volatility: ATR% >= 5%",
                "value": "atr_high_5",
                "condition": {"field": "atr_pct", "op": ">=", "value": 0.05},
            },
            {
                "label": "Extreme Volatility: ATR% >= 8%",
                "value": "atr_extreme_8",
                "condition": {"field": "atr_pct", "op": ">=", "value": 0.08},
            },
        ],
    },
    {
        "id": "liquidity",
        "label": "Liquidity",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Market Default",
                "value": "market_default",
                "condition": {
                    "field": "avg_amount_20d",
                    "op": ">=",
                    "market_threshold": "default_liquidity",
                },
            },
            {
                "label": "2x Market Default",
                "value": "market_default_2x",
                "condition": {
                    "field": "avg_amount_20d",
                    "op": ">=",
                    "market_threshold": "double_liquidity",
                },
            },
        ],
    },
    {
        "id": "pattern",
        "label": "Pattern",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Any Breakout",
                "value": "breakout_any",
                "condition": {"field": "breakout_hit", "op": "is_true"},
            },
            {
                "label": "Platform Breakout",
                "value": "platform_breakout",
                "condition": {
                    "field": "breakout_type",
                    "op": "==",
                    "value": "platform_breakout",
                },
            },
            {
                "label": "Box Breakout",
                "value": "box_breakout",
                "condition": {
                    "field": "breakout_type",
                    "op": "==",
                    "value": "box_breakout",
                },
            },
            {
                "label": "Wedge Breakout",
                "value": "wedge_breakout",
                "condition": {
                    "field": "breakout_type",
                    "op": "==",
                    "value": "wedge_breakout",
                },
            },
        ],
    },
    {
        "id": "volume",
        "label": "Volume",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Breakout Volume Confirmed",
                "value": "breakout_volume_confirmed",
                "condition": {"field": "breakout_with_volume", "op": "is_true"},
            },
        ],
    },
    {
        "id": "pe_ttm",
        "label": "P/E",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "P/E > 0 and <= 10",
                "value": "pe_lte_10",
                "conditions": [
                    {"field": "pe_ttm", "op": ">", "value": 0},
                    {"field": "pe_ttm", "op": "<=", "value": 10},
                ],
            },
            {
                "label": "P/E > 0 and <= 20",
                "value": "pe_lte_20",
                "conditions": [
                    {"field": "pe_ttm", "op": ">", "value": 0},
                    {"field": "pe_ttm", "op": "<=", "value": 20},
                ],
            },
            {
                "label": "P/E > 0 and <= 40",
                "value": "pe_lte_40",
                "conditions": [
                    {"field": "pe_ttm", "op": ">", "value": 0},
                    {"field": "pe_ttm", "op": "<=", "value": 40},
                ],
            },
        ],
    },
    {
        "id": "ps_ttm",
        "label": "P/S",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "P/S <= 3",
                "value": "ps_lte_3",
                "condition": {"field": "ps_ttm", "op": "<=", "value": 3},
            },
            {
                "label": "P/S <= 5",
                "value": "ps_lte_5",
                "condition": {"field": "ps_ttm", "op": "<=", "value": 5},
            },
            {
                "label": "P/S <= 10",
                "value": "ps_lte_10",
                "condition": {"field": "ps_ttm", "op": "<=", "value": 10},
            },
        ],
    },
    {
        "id": "pb",
        "label": "P/B",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "P/B <= 1",
                "value": "pb_lte_1",
                "condition": {"field": "pb", "op": "<=", "value": 1},
            },
            {
                "label": "P/B <= 3",
                "value": "pb_lte_3",
                "condition": {"field": "pb", "op": "<=", "value": 3},
            },
            {
                "label": "P/B <= 5",
                "value": "pb_lte_5",
                "condition": {"field": "pb", "op": "<=", "value": 5},
            },
        ],
    },
    {
        "id": "peg",
        "label": "PEG",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "PEG <= 1",
                "value": "peg_lte_1",
                "condition": {"field": "peg", "op": "<=", "value": 1},
            },
            {
                "label": "PEG <= 1.5",
                "value": "peg_lte_1_5",
                "condition": {"field": "peg", "op": "<=", "value": 1.5},
            },
            {
                "label": "PEG <= 2",
                "value": "peg_lte_2",
                "condition": {"field": "peg", "op": "<=", "value": 2},
            },
        ],
    },
    {
        "id": "roe",
        "label": "ROE",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "ROE >= 10%",
                "value": "roe_gte_10",
                "condition": {"field": "roe", "op": ">=", "value": 0.10},
            },
            {
                "label": "ROE >= 20%",
                "value": "roe_gte_20",
                "condition": {"field": "roe", "op": ">=", "value": 0.20},
            },
        ],
    },
    {
        "id": "gross_margin",
        "label": "Gross Margin",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Gross Margin >= 30%",
                "value": "gross_margin_gte_30",
                "condition": {"field": "gross_margin", "op": ">=", "value": 0.30},
            },
        ],
    },
    {
        "id": "net_margin",
        "label": "Net Margin",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Net Margin >= 10%",
                "value": "net_margin_gte_10",
                "condition": {"field": "net_margin", "op": ">=", "value": 0.10},
            },
        ],
    },
    {
        "id": "revenue_growth_yoy",
        "label": "Revenue Growth",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Revenue Growth >= 10%",
                "value": "revenue_growth_gte_10",
                "condition": {"field": "revenue_growth_yoy", "op": ">=", "value": 0.10},
            },
            {
                "label": "Revenue Growth >= 20%",
                "value": "revenue_growth_gte_20",
                "condition": {"field": "revenue_growth_yoy", "op": ">=", "value": 0.20},
            },
        ],
    },
    {
        "id": "net_income_growth_yoy",
        "label": "Net Income Growth",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Net Income Growth >= 10%",
                "value": "income_growth_gte_10",
                "condition": {
                    "field": "net_income_growth_yoy",
                    "op": ">=",
                    "value": 0.10,
                },
            },
        ],
    },
    {
        "id": "current_ratio",
        "label": "Current Ratio",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Current Ratio >= 1",
                "value": "current_ratio_gte_1",
                "condition": {"field": "current_ratio", "op": ">=", "value": 1.0},
            },
            {
                "label": "Current Ratio >= 1.5",
                "value": "current_ratio_gte_1_5",
                "condition": {"field": "current_ratio", "op": ">=", "value": 1.5},
            },
        ],
    },
    {
        "id": "debt_to_assets",
        "label": "Debt / Assets",
        "options": [
            {"label": "Any", "value": "any"},
            {
                "label": "Debt / Assets <= 60%",
                "value": "debt_assets_lte_60",
                "condition": {"field": "debt_to_assets", "op": "<=", "value": 0.60},
            },
        ],
    },
]

RANKING_PROFILES: dict[str, dict[str, Any]] = {
    "technical_pattern_balanced": {
        "id": "technical_pattern_balanced",
        "label": "Technical Pattern Balanced",
        "description": "Balanced trend, momentum, pattern, liquidity, and risk ranking.",
        "weights": {
            "trend": 0.25,
            "momentum": 0.20,
            "pattern": 0.25,
            "liquidity": 0.15,
            "risk": 0.15,
            "fundamental": 0.0,
        },
    },
    "trend_momentum": {
        "id": "trend_momentum",
        "label": "Trend Momentum First",
        "description": "Prioritize established trends and positive momentum.",
        "weights": {
            "trend": 0.30,
            "momentum": 0.30,
            "pattern": 0.15,
            "liquidity": 0.15,
            "risk": 0.10,
            "fundamental": 0.0,
        },
    },
    "pattern_breakout": {
        "id": "pattern_breakout",
        "label": "Pattern Breakout First",
        "description": "Prioritize breakout and volume-confirmed pattern signals.",
        "weights": {
            "trend": 0.20,
            "momentum": 0.15,
            "pattern": 0.40,
            "liquidity": 0.15,
            "risk": 0.10,
            "fundamental": 0.0,
        },
    },
    "low_volatility": {
        "id": "low_volatility",
        "label": "Low Volatility Steady",
        "description": "Favor lower volatility candidates while keeping trend context.",
        "weights": {
            "trend": 0.20,
            "momentum": 0.15,
            "pattern": 0.15,
            "liquidity": 0.15,
            "risk": 0.35,
            "fundamental": 0.0,
        },
    },
    "quality_growth_value": {
        "id": "quality_growth_value",
        "label": "Quality Growth Value",
        "description": "Blend fundamentals with technical confirmation and risk control.",
        "weights": {
            "trend": 0.20,
            "momentum": 0.15,
            "pattern": 0.15,
            "liquidity": 0.10,
            "risk": 0.15,
            "fundamental": 0.25,
        },
    },
}

LEGACY_FILTER_OPTION_GROUPS: dict[str, dict[str, str]] = {
    "moving_average": {
        "price_above_ma20": "ma20_position",
        "near_ma20_3pct": "ma20_position",
        "below_ma20": "ma20_position",
        "price_above_ma60": "ma60_position",
        "below_ma60": "ma60_position",
        "bullish_alignment": "ma_alignment",
    },
    "performance": {
        "ret20_positive": "ret_20",
        "ret20_5": "ret_20",
        "ret20_negative": "ret_20",
        "ret60_positive": "ret_60",
        "ret60_10": "ret_60",
    },
    "valuation": {
        "pe_lte_10": "pe_ttm",
        "pe_lte_20": "pe_ttm",
        "pe_lte_40": "pe_ttm",
        "ps_lte_3": "ps_ttm",
        "ps_lte_5": "ps_ttm",
        "ps_lte_10": "ps_ttm",
        "pb_lte_1": "pb",
        "pb_lte_3": "pb",
        "pb_lte_5": "pb",
        "peg_lte_1": "peg",
        "peg_lte_1_5": "peg",
        "peg_lte_2": "peg",
    },
    "quality": {
        "roe_gte_10": "roe",
        "roe_gte_20": "roe",
        "gross_margin_gte_30": "gross_margin",
        "net_margin_gte_10": "net_margin",
    },
    "growth": {
        "revenue_growth_gte_10": "revenue_growth_yoy",
        "revenue_growth_gte_20": "revenue_growth_yoy",
        "income_growth_gte_10": "net_income_growth_yoy",
    },
    "balance_sheet": {
        "current_ratio_gte_1": "current_ratio",
        "current_ratio_gte_1_5": "current_ratio",
        "debt_assets_lte_60": "debt_to_assets",
    },
}


def _option_by_group() -> dict[str, dict[str, dict[str, Any]]]:
    return {
        str(group["id"]): {str(option["value"]): option for option in group["options"]}
        for group in FILTER_PRESET_GROUPS
    }


def list_filter_preset_groups() -> list[dict[str, Any]]:
    return deepcopy(FILTER_PRESET_GROUPS)


def list_ranking_profiles() -> list[dict[str, Any]]:
    return [deepcopy(profile) for profile in RANKING_PROFILES.values()]


def normalize_filter_preset_selections(
    selections: dict[str, str] | None,
) -> dict[str, str]:
    normalized = dict(DEFAULT_FILTER_PRESET_SELECTIONS)
    if not selections:
        return normalized

    options_by_group = _option_by_group()
    for raw_group, raw_value in selections.items():
        group = str(raw_group).strip()
        value = str(raw_value).strip()
        if group in LEGACY_FILTER_OPTION_GROUPS:
            if value == "any":
                continue
            mapped_group = LEGACY_FILTER_OPTION_GROUPS[group].get(value)
            if mapped_group is None:
                raise ValueError(
                    f"unknown screener filter preset option for {group}: {value}"
                )
            group = mapped_group
        if group not in options_by_group:
            raise ValueError(f"unknown screener filter preset group: {group}")
        if value not in options_by_group[group]:
            raise ValueError(
                f"unknown screener filter preset option for {group}: {value}"
            )
        normalized[group] = value
    return normalized


def resolve_filter_preset_conditions(
    selections: dict[str, str] | None,
) -> list[dict[str, Any]]:
    normalized = normalize_filter_preset_selections(selections)
    options_by_group = _option_by_group()
    conditions: list[dict[str, Any]] = []
    for group, value in normalized.items():
        if value == "any":
            continue
        option = deepcopy(options_by_group[group][value])
        option["group"] = group
        conditions.append(option)
    return conditions


def resolve_ranking_profile(profile_id: str | None) -> dict[str, Any] | None:
    if profile_id is None:
        return None
    normalized = str(profile_id).strip()
    if not normalized:
        return None
    if normalized not in RANKING_PROFILES:
        raise ValueError(f"unknown screener ranking profile: {normalized}")
    return deepcopy(RANKING_PROFILES[normalized])
