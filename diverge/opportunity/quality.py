from __future__ import annotations

from typing import Literal, TypedDict

Severity = Literal["info", "warning", "error"]


class DataQualityFlag(TypedDict, total=False):
    code: str
    severity: Severity
    source: str
    field: str
    message: str


def quality_flag(
    code: str,
    *,
    severity: Severity = "warning",
    source: str = "opportunity",
    field: str = "",
    message: str = "",
) -> DataQualityFlag:
    return {
        "code": code,
        "severity": severity,
        "source": source,
        "field": field,
        "message": message or code.replace("_", " "),
    }
