from __future__ import annotations

from typing import Any

import pandas as pd

_ALLOWED_OPS = {"==", "!=", ">", ">=", "<", "<=", "in", "not_in", "is_true", "is_false"}


class ConditionError(ValueError):
    pass


def _series(df: pd.DataFrame, field: str) -> pd.Series:
    if field not in df.columns:
        return pd.Series([pd.NA] * len(df), index=df.index)
    return df[field]


def evaluate_condition_tree(
    df: pd.DataFrame, condition: dict[str, Any] | None
) -> pd.Series:
    if condition is None or condition == {}:
        return pd.Series([True] * len(df), index=df.index)
    if not isinstance(condition, dict):
        raise ConditionError("condition must be a mapping")
    if "all" in condition:
        parts = condition.get("all") or []
        if not isinstance(parts, list):
            raise ConditionError("all must be a list")
        result = pd.Series([True] * len(df), index=df.index)
        for part in parts:
            result &= evaluate_condition_tree(df, part).fillna(False)
        return result
    if "any" in condition:
        parts = condition.get("any") or []
        if not isinstance(parts, list):
            raise ConditionError("any must be a list")
        result = pd.Series([False] * len(df), index=df.index)
        for part in parts:
            result |= evaluate_condition_tree(df, part).fillna(False)
        return result
    if "not" in condition:
        return ~evaluate_condition_tree(df, condition.get("not")).fillna(False)

    field = str(condition.get("field") or "").strip()
    op = str(condition.get("op") or "").strip()
    value = condition.get("value")
    if not field:
        raise ConditionError("leaf condition requires field")
    if op not in _ALLOWED_OPS:
        raise ConditionError(f"unsupported condition op: {op}")
    lhs = _series(df, field)
    if op == "==":
        return lhs == value
    if op == "!=":
        return lhs != value
    if op == ">":
        return lhs.astype("float64") > float(value)
    if op == ">=":
        return lhs.astype("float64") >= float(value)
    if op == "<":
        return lhs.astype("float64") < float(value)
    if op == "<=":
        return lhs.astype("float64") <= float(value)
    if op == "in":
        return lhs.isin(value if isinstance(value, list) else [value])
    if op == "not_in":
        return ~lhs.isin(value if isinstance(value, list) else [value])
    if op == "is_true":
        return lhs.eq(True)
    if op == "is_false":
        return lhs.eq(False)
    raise ConditionError(f"unsupported condition op: {op}")
