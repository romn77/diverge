from __future__ import annotations

import pandas as pd

from diverge.common.market_calendar import trading_day_lag

from .presets import resolve_filter_preset_conditions
from .schema import ScreenRunConfig


REQUIRED_FEATURE_COLUMNS = [
    "avg_amount_20d",
    "ma20",
    "ma60",
    "ret_20",
    "ret_60",
    "rsi",
    "macdh",
    "atr_pct",
    "vwma",
]
MAX_STALE_BUSINESS_DAYS = 3
HARD_FILTER_DROP_REASONS = frozenset(
    {
        "stale_data",
        "insufficient_bars",
        "missing_features",
        "low_price_cn",
        "low_price_us",
        "insufficient_trading_days_20d",
        "illiquid_cn",
        "illiquid_us",
        "preset_condition",
    }
)


def _missing_required_features(row: pd.Series) -> bool:
    return any(pd.isna(row.get(column)) for column in REQUIRED_FEATURE_COLUMNS)


def _is_stale_data(row: pd.Series) -> bool:
    lag = trading_day_lag(
        str(row.get("market") or ""),
        row.get("as_of_date"),
        row.get("data_end_date"),
    )
    return lag is not None and lag > MAX_STALE_BUSINESS_DAYS


def _price_floor_drop_reason(row: pd.Series, config: ScreenRunConfig) -> str | None:
    close = pd.to_numeric(row.get("close"), errors="coerce")
    if pd.isna(close):
        return None

    market = str(row.get("market") or "").strip().lower()
    if market == "cn" and float(close) < config.cn_min_price:
        return "low_price_cn"
    if market == "us" and float(close) < config.us_min_price:
        return "low_price_us"
    return None


def _has_insufficient_trading_continuity(
    row: pd.Series, config: ScreenRunConfig
) -> bool:
    trading_days_20d = pd.to_numeric(row.get("trading_days_20d"), errors="coerce")
    return (
        pd.isna(trading_days_20d)
        or float(trading_days_20d) < config.min_trading_days_20d
    )


def _market_liquidity_threshold(
    row: pd.Series, config: ScreenRunConfig, name: str
) -> float | None:
    market = str(row.get("market") or "").strip().lower()
    if market == "cn":
        threshold = config.cn_min_avg_amount_20d
    elif market == "us":
        threshold = config.us_min_avg_dollar_volume_20d
    else:
        return None
    if name == "double_liquidity":
        return float(threshold) * 2
    return float(threshold)


def _condition_value(
    row: pd.Series, condition: dict, config: ScreenRunConfig
) -> object:
    if "compare_field" in condition:
        return row.get(condition["compare_field"])
    if "market_threshold" in condition:
        return _market_liquidity_threshold(
            row, config, str(condition["market_threshold"])
        )
    return condition.get("value")


def _numeric_pair(
    row: pd.Series, condition: dict, config: ScreenRunConfig
) -> tuple[float | None, float | None]:
    left = pd.to_numeric(row.get(condition["field"]), errors="coerce")
    right = pd.to_numeric(_condition_value(row, condition, config), errors="coerce")
    if pd.isna(left) or pd.isna(right):
        return None, None
    return float(left), float(right)


def _condition_matches(
    row: pd.Series, condition: dict, config: ScreenRunConfig
) -> bool:
    op = str(condition.get("op") or "")
    if op == "is_true":
        return bool(row.get(condition["field"])) is True
    if op == "==":
        return str(row.get(condition["field"]) or "") == str(
            condition.get("value") or ""
        )

    left, right = _numeric_pair(row, condition, config)
    if left is None or right is None:
        return False
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == "within_pct":
        if right == 0:
            return False
        return abs(left / right - 1) <= abs(float(condition.get("value") or 0))
    return False


def _resolved_condition_detail(
    row: pd.Series, condition: dict, config: ScreenRunConfig
) -> str:
    field = str(condition.get("field") or "")
    op = str(condition.get("op") or "")
    value = _condition_value(row, condition, config)
    if op == "is_true":
        return f"{field} is true"
    if "compare_field" in condition:
        return f"{field} {op} {condition['compare_field']}"
    return f"{field} {op} {value}"


def _preset_filter_drop(
    row: pd.Series,
    config: ScreenRunConfig,
) -> tuple[str | None, str, str]:
    matched_labels: list[str] = []
    matched_details: list[str] = []
    for preset in resolve_filter_preset_conditions(config.filter_preset_selections):
        raw_conditions = preset.get("conditions") or [preset.get("condition")]
        conditions = [condition for condition in raw_conditions if condition]
        if all(_condition_matches(row, condition, config) for condition in conditions):
            matched_labels.append(str(preset["label"]))
            matched_details.extend(
                _resolved_condition_detail(row, condition, config)
                for condition in conditions
            )
            continue
        return (
            f"preset_{preset['group']}_{preset['value']}",
            ";".join(matched_labels),
            ";".join(matched_details),
        )
    return None, ";".join(matched_labels), ";".join(matched_details)


def apply_hard_filters(
    features_df: pd.DataFrame,
    config: ScreenRunConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    kept_rows: list[dict] = []
    dropped_rows: list[dict] = []

    for _, row in features_df.iterrows():
        reason = row.get("drop_reason")
        if reason:
            dropped_rows.append({**row.to_dict(), "drop_reason": reason})
            continue

        if _is_stale_data(row):
            dropped_rows.append({**row.to_dict(), "drop_reason": "stale_data"})
            continue

        if int(row.get("bar_count", 0) or 0) < 60:
            dropped_rows.append({**row.to_dict(), "drop_reason": "insufficient_bars"})
            continue

        if _missing_required_features(row):
            dropped_rows.append({**row.to_dict(), "drop_reason": "missing_features"})
            continue

        price_floor_reason = _price_floor_drop_reason(row, config)
        if price_floor_reason is not None:
            dropped_rows.append({**row.to_dict(), "drop_reason": price_floor_reason})
            continue

        if _has_insufficient_trading_continuity(row, config):
            dropped_rows.append(
                {**row.to_dict(), "drop_reason": "insufficient_trading_days_20d"}
            )
            continue

        if (
            row["market"] == "cn"
            and float(row["avg_amount_20d"]) < config.cn_min_avg_amount_20d
        ):
            dropped_rows.append({**row.to_dict(), "drop_reason": "illiquid_cn"})
            continue

        if (
            row["market"] == "us"
            and float(row["avg_amount_20d"]) < config.us_min_avg_dollar_volume_20d
        ):
            dropped_rows.append({**row.to_dict(), "drop_reason": "illiquid_us"})
            continue

        preset_drop_reason, matched_conditions, matched_condition_details = (
            _preset_filter_drop(row, config)
        )
        if preset_drop_reason is not None:
            dropped_rows.append(
                {
                    **row.to_dict(),
                    "drop_reason": preset_drop_reason,
                    "matched_conditions": matched_conditions,
                    "matched_condition_details": matched_condition_details,
                    "failed_condition": preset_drop_reason,
                }
            )
            continue

        kept_rows.append(
            {
                **row.to_dict(),
                "matched_conditions": matched_conditions,
                "matched_condition_details": matched_condition_details,
            }
        )

    kept_columns = list(features_df.columns)
    for column in ("matched_conditions", "matched_condition_details"):
        if column not in kept_columns:
            kept_columns.append(column)
    kept = pd.DataFrame(kept_rows, columns=kept_columns)
    dropped_columns = list(features_df.columns)
    for column in (
        "drop_reason",
        "matched_conditions",
        "matched_condition_details",
        "failed_condition",
    ):
        if column not in dropped_columns:
            dropped_columns.append(column)
    dropped = pd.DataFrame(dropped_rows, columns=dropped_columns)
    return kept, dropped
