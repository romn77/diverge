from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any

import pandas as pd
import pytest


DEFAULT_SAMPLE_TICKERS = ("AAPL", "MSFT", "NVDA", "GOOGL", "JPM", "XOM")
DEFAULT_MIN_FIELD_COVERAGE = 0.70
DEFAULT_MIN_TICKER_COVERAGE = 0.60


@dataclass(frozen=True)
class V2FieldRequirement:
    field: str
    group: str
    description: str
    simfin_candidates: tuple[str, ...]
    required: bool = True


@dataclass
class SimfinCoverageResult:
    tickers: tuple[str, ...]
    covered_fields: dict[str, str] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    field_coverage: float = 0.0
    ticker_coverage: dict[str, float] = field(default_factory=dict)
    latest_rows: dict[str, dict[str, Any]] = field(default_factory=dict)


V2_FIELD_REQUIREMENTS = (
    V2FieldRequirement(
        field="market_cap",
        group="profile",
        description="Size filter and liquidity context.",
        simfin_candidates=("Market-Cap", "Market Cap", "market_cap", "mktcap"),
    ),
    V2FieldRequirement(
        field="pe_ttm",
        group="valuation",
        description="TTM price-to-earnings valuation.",
        simfin_candidates=("P/E", "PE", "Price to Earnings", "Price/Earnings"),
    ),
    V2FieldRequirement(
        field="pb",
        group="valuation",
        description="Price-to-book valuation.",
        simfin_candidates=("P/Book", "P/B", "PB", "Price to Book"),
    ),
    V2FieldRequirement(
        field="ps_ttm",
        group="valuation",
        description="Price-to-sales valuation.",
        simfin_candidates=("P/Sales", "P/S", "PS", "Price to Sales"),
    ),
    V2FieldRequirement(
        field="roe",
        group="quality",
        description="Return on equity.",
        simfin_candidates=("ROE", "Return on Equity"),
    ),
    V2FieldRequirement(
        field="roa",
        group="quality",
        description="Return on assets.",
        simfin_candidates=("ROA", "Return on Assets"),
        required=False,
    ),
    V2FieldRequirement(
        field="gross_margin",
        group="quality",
        description="Gross profit margin.",
        simfin_candidates=("Gross Margin", "Gross Profit Margin"),
    ),
    V2FieldRequirement(
        field="net_margin",
        group="quality",
        description="Net profit margin.",
        simfin_candidates=("Net Profit Margin", "Profit Margin", "Net Margin"),
    ),
    V2FieldRequirement(
        field="revenue_growth_yoy",
        group="growth",
        description="Revenue growth for growth filters.",
        simfin_candidates=("Revenue Growth", "Sales Growth", "Sales Growth YoY"),
    ),
    V2FieldRequirement(
        field="net_income_growth_yoy",
        group="growth",
        description="Net income or earnings growth.",
        simfin_candidates=(
            "Net Income Growth",
            "Earnings Growth",
            "Net Income Growth YoY",
        ),
    ),
    V2FieldRequirement(
        field="debt_to_assets",
        group="financial_health",
        description="Balance-sheet leverage.",
        simfin_candidates=("Debt Ratio", "Debt-to-Assets", "Liabilities to Assets"),
    ),
    V2FieldRequirement(
        field="current_ratio",
        group="financial_health",
        description="Short-term solvency.",
        simfin_candidates=("Current Ratio",),
    ),
    V2FieldRequirement(
        field="free_cashflow",
        group="cashflow",
        description="Free cash flow level or proxy.",
        simfin_candidates=("Free Cash Flow", "FCF"),
    ),
    V2FieldRequirement(
        field="operating_cashflow_quality",
        group="cashflow",
        description="Operating cash flow quality proxy.",
        simfin_candidates=(
            "Operating Cash Flow / Net Income",
            "Operating Cash Flow to Net Income",
            "Cash Return on Assets",
            "Free Cash Flow Margin",
        ),
        required=False,
    ),
)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _sample_tickers() -> tuple[str, ...]:
    raw = os.getenv("SIMFIN_SAMPLE_TICKERS", "MSFT")
    if not raw.strip():
        return DEFAULT_SAMPLE_TICKERS
    return tuple(ticker.strip().upper() for ticker in raw.split(",") if ticker.strip())


def _normalize_tickers(tickers: tuple[str, ...] | list[str] | str) -> tuple[str, ...]:
    if isinstance(tickers, str):
        return tuple(
            ticker.strip().upper()
            for ticker in tickers.split(",")
            if ticker.strip()
        )
    return tuple(str(ticker).strip().upper() for ticker in tickers if str(ticker).strip())


def _import_simfin():
    try:
        return import_module("simfin")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The 'simfin' package is not installed in this virtualenv. "
            "Install it with: ./.venv/bin/python -m pip install simfin"
        ) from exc


def _normalize_column_name(value: object) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _candidate_matches(columns: pd.Index, candidates: tuple[str, ...]) -> str | None:
    normalized = {_normalize_column_name(column): str(column) for column in columns}
    for candidate in candidates:
        match = normalized.get(_normalize_column_name(candidate))
        if match:
            return match
    return None


def _series_for_column(frame: pd.DataFrame, column: str) -> pd.Series:
    value = frame[column]
    if isinstance(value, pd.DataFrame):
        return value.iloc[:, 0]
    return value


def _drop_sparse_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame.dropna(axis=1, how="all")


def _load_simfin_signal_frame(
    sf, hub, loader_name: str, *, variant: str = "daily"
) -> pd.DataFrame:
    loader = getattr(hub, loader_name)
    try:
        return _drop_sparse_columns(loader(variant=variant))
    except TypeError:
        return _drop_sparse_columns(loader())


def _combine_signal_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    usable = [
        frame for frame in frames if isinstance(frame, pd.DataFrame) and not frame.empty
    ]
    if not usable:
        return pd.DataFrame()

    normalized: list[pd.DataFrame] = []
    for frame in usable:
        next_frame = frame.copy()
        if isinstance(next_frame.index, pd.MultiIndex):
            next_frame = next_frame.reset_index()
        normalized.append(next_frame)
    combined = pd.concat(normalized, axis=1)
    return combined.loc[:, ~combined.columns.duplicated()]


def _latest_rows_by_ticker(
    frame: pd.DataFrame, tickers: tuple[str, ...]
) -> dict[str, dict[str, Any]]:
    if frame.empty:
        return {}

    ticker_column = _candidate_matches(
        frame.columns, ("Ticker", "Symbol", "ticker", "symbol")
    )
    if ticker_column is None:
        return {}

    date_column = _candidate_matches(
        frame.columns, ("Date", "Report Date", "Publish Date", "Fiscal Year")
    )
    rows: dict[str, dict[str, Any]] = {}
    normalized_tickers = {ticker.upper() for ticker in tickers}
    ticker_values = _series_for_column(frame, ticker_column).astype(str).str.upper()
    filtered = frame.loc[ticker_values.isin(normalized_tickers)].copy()
    if filtered.empty:
        return rows

    if date_column is not None:
        filtered[date_column] = pd.to_datetime(
            _series_for_column(filtered, date_column),
            errors="coerce",
        )
        filtered = filtered.sort_values(date_column)

    filtered_tickers = _series_for_column(filtered, ticker_column).astype(str).str.upper()
    for ticker, group in filtered.groupby(
        filtered_tickers
    ):
        rows[ticker] = group.iloc[-1].dropna().to_dict()
    return rows


def evaluate_simfin_v2_scope(
    *,
    api_key: str,
    tickers: tuple[str, ...] | list[str] | str = DEFAULT_SAMPLE_TICKERS,
    market: str = "us",
    data_dir: Path | None = None,
) -> SimfinCoverageResult:
    sf = _import_simfin()
    normalized_tickers = _normalize_tickers(tickers)
    if not normalized_tickers:
        raise ValueError("At least one ticker is required.")

    if data_dir is None:
        data_dir = Path(os.getenv("SIMFIN_DATA_DIR", ".simfin_data"))

    sf.set_api_key(api_key)
    sf.set_data_dir(str(data_dir))

    hub = sf.StockHub(market=market, tickers=list(normalized_tickers))
    frames = [
        _load_simfin_signal_frame(sf, hub, "val_signals"),
        _load_simfin_signal_frame(sf, hub, "fin_signals"),
        _load_simfin_signal_frame(sf, hub, "growth_signals"),
    ]
    combined = _combine_signal_frames(frames)

    result = SimfinCoverageResult(tickers=normalized_tickers)
    for requirement in V2_FIELD_REQUIREMENTS:
        matched_column = _candidate_matches(
            combined.columns, requirement.simfin_candidates
        )
        if matched_column is None:
            if requirement.required:
                result.missing_fields.append(requirement.field)
            continue
        result.covered_fields[requirement.field] = matched_column

    required_count = sum(
        1 for requirement in V2_FIELD_REQUIREMENTS if requirement.required
    )
    result.field_coverage = (
        len(result.covered_fields) / required_count if required_count else 0.0
    )
    result.latest_rows = _latest_rows_by_ticker(combined, normalized_tickers)

    for ticker in normalized_tickers:
        latest_row = result.latest_rows.get(ticker, {})
        available = 0
        for column in result.covered_fields.values():
            value = latest_row.get(column)
            if value is not None and pd.notna(value):
                available += 1
        result.ticker_coverage[ticker] = (
            available / len(result.covered_fields) if result.covered_fields else 0.0
        )

    return result


def _values_by_ticker(result: SimfinCoverageResult) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for ticker in result.tickers:
        row = result.latest_rows.get(ticker, {})
        values[ticker] = {
            field: row.get(column)
            for field, column in result.covered_fields.items()
        }
    return values


def _coverage_report(result: SimfinCoverageResult) -> dict[str, Any]:
    return {
        "tickers": result.tickers,
        "field_coverage": result.field_coverage,
        "covered_fields": result.covered_fields,
        "missing_fields": result.missing_fields,
        "ticker_coverage": result.ticker_coverage,
        "values": _values_by_ticker(result),
    }


def test_simfin_can_cover_screener_v2_scope(tmp_path):
    api_key = os.getenv("SIMFIN_API_KEY")
    if not api_key:
        pytest.skip("Set SIMFIN_API_KEY to run the SimFin v2 scope coverage check.")
    pytest.importorskip("simfin")

    result = evaluate_simfin_v2_scope(
        api_key=api_key,
        tickers=_sample_tickers(),
        data_dir=tmp_path / "simfin",
    )

    report = _coverage_report(result)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    min_field_coverage = float(
        os.getenv("SIMFIN_MIN_FIELD_COVERAGE", DEFAULT_MIN_FIELD_COVERAGE)
    )
    min_ticker_coverage = float(
        os.getenv("SIMFIN_MIN_TICKER_COVERAGE", DEFAULT_MIN_TICKER_COVERAGE)
    )
    weak_tickers = [
        ticker
        for ticker, coverage in result.ticker_coverage.items()
        if coverage < min_ticker_coverage
    ]

    assert result.field_coverage >= min_field_coverage, report
    assert not weak_tickers, {**report, "weak_tickers": weak_tickers}


from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    key = os.getenv("SIMFIN_API_KEY")
    if not key:
        raise SystemExit("Set SIMFIN_API_KEY before running this validation script.")
    try:
        coverage = evaluate_simfin_v2_scope(api_key=key, tickers=_sample_tickers())
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(
        json.dumps(
            _coverage_report(coverage),
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
