from __future__ import annotations

from statistics import median

from .schemas import AssumptionValue, FinancialSnapshot


def normalize_fcff(financials: list[FinancialSnapshot]) -> AssumptionValue:
    valid = [
        snapshot.free_cash_flow
        for snapshot in financials
        if snapshot.free_cash_flow is not None
    ]
    if not valid:
        raise ValueError("normalized FCFF requires at least one free_cash_flow value")
    return AssumptionValue(
        value=median(valid),
        source="historical-median-fcff",
        confidence="medium",
    )
