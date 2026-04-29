# Market-Routed DCF Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current static single-period DCF path with a market-routed valuation pipeline that uses `yfinance` for non-CN symbols and `AkShare` for CN symbols, while preserving the existing markdown-first `fundamentals_report` contract.

**Architecture:** Keep valuation calculations pure inside `diverge/valuation`, but move provider-specific retrieval into a new internal valuation-input route under `diverge/dataflows`. The new route should build a richer `ValuationInput` with multi-period financial history, provider-derived assumptions, and explicit provenance. `ERP` remains an internal market-level configuration; `MarketContext.beta` stores the resolved numeric beta used by the model, while `assumptions["beta"]` stores the source and fallback metadata. Short-term growth and `risk_free` are sourced per market from the selected provider with explicit fallback rules.

**Tech Stack:** Python 3.13, LangGraph, pytest, yfinance, AkShare, existing `route_to_vendor` market detection, markdown/json-highlights report pipeline

---

### Task 1: Add a market-routed internal valuation input path

**Files:**
- Create: `diverge/dataflows/valuation_inputs.py`
- Modify: `diverge/dataflows/interface.py`
- Modify: `diverge/agents/utils/fundamental_data_tools.py`
- Test: `tests/dataflows/test_valuation_inputs.py`
- Modify: `tests/integration/test_skill_adoption_flow.py`

**Step 1: Write the failing test**

```python
from diverge.dataflows.valuation_inputs import route_to_valuation_input


def test_route_to_valuation_input_uses_yfinance_for_us(monkeypatch):
    calls = []

    def fake_yf(*args, **kwargs):
        calls.append("yfinance")
        return "ok"

    def fake_ak(*args, **kwargs):
        calls.append("akshare")
        return "bad"

    monkeypatch.setattr(
        "diverge.dataflows.valuation_inputs.build_yfinance_valuation_input",
        fake_yf,
    )
    monkeypatch.setattr(
        "diverge.dataflows.valuation_inputs.build_akshare_valuation_input",
        fake_ak,
    )

    assert route_to_valuation_input("AAPL", curr_date="2026-03-24") == "ok"
    assert calls == ["yfinance"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/dataflows/test_valuation_inputs.py::test_route_to_valuation_input_uses_yfinance_for_us -q`

Expected: FAIL because `diverge.dataflows.valuation_inputs` and `route_to_valuation_input()` do not exist yet.

**Step 3: Write minimal implementation**

```python
# diverge/dataflows/valuation_inputs.py
from diverge.dataflows.interface import resolve_market_and_symbol

from .akshare_valuation import build_akshare_valuation_input
from .yfinance_valuation import build_yfinance_valuation_input


def route_to_valuation_input(
    ticker: str,
    curr_date: str | None = None,
    freq: str = "annual",
):
    market, _, _ = resolve_market_and_symbol("get_fundamentals", (ticker, curr_date), {})
    if market == "cn":
        return build_akshare_valuation_input(ticker=ticker, curr_date=curr_date, freq=freq)
    return build_yfinance_valuation_input(ticker=ticker, curr_date=curr_date, freq=freq)
```

Update `get_valuation_ready_fundamentals()` to call `route_to_valuation_input()` instead of `route_to_normalized_fundamentals()`.

In the same task, update `tests/integration/test_skill_adoption_flow.py` to patch `route_to_valuation_input()` or `get_valuation_ready_fundamentals()` directly. Do not leave the integration test waiting until Task 8 to stop patching `route_to_vendor()`.

Add a note in `diverge/dataflows/fundamentals_normalizer.py` that `normalize_fundamentals_payload()` remains a legacy compatibility normalizer and does not produce a fully populated market-routed `ValuationInput` for the new DCF path. Its newer schema fields may stay intentionally `None`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/dataflows/test_valuation_inputs.py -q`

Expected: PASS for US and CN routing cases.

**Step 5: Commit**

```bash
git add diverge/dataflows/valuation_inputs.py diverge/dataflows/interface.py diverge/agents/utils/fundamental_data_tools.py tests/dataflows/test_valuation_inputs.py
git commit -m "feat: add market-routed valuation input path"
```

### Task 2: Extend valuation schemas for multi-period history and assumption provenance

**Files:**
- Modify: `diverge/valuation/schemas.py`
- Test: `tests/valuation/test_schemas.py`

**Step 1: Write the failing test**

```python
from datetime import date

from diverge.valuation.schemas import AssumptionValue, FinancialSnapshot, MarketContext, ValuationInput


def test_latest_financial_prefers_newest_report_date():
    valuation_input = ValuationInput(
        ticker="AAPL",
        market=MarketContext(market="us", currency="USD"),
        financials=[
            FinancialSnapshot(period="FY2024", report_date=date(2024, 9, 30)),
            FinancialSnapshot(period="FY2025", report_date=date(2025, 9, 30)),
        ],
        assumptions={
            "beta": AssumptionValue(value=1.2, source="yfinance.info", as_of=date(2026, 3, 24)),
        },
    )

    assert valuation_input.latest_financial.period == "FY2025"
    assert valuation_input.assumptions["beta"].source == "yfinance.info"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/valuation/test_schemas.py -q`

Expected: FAIL because `AssumptionValue` and `ValuationInput.assumptions` are not defined.

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass, field
from datetime import date


@dataclass(slots=True)
class AssumptionValue:
    value: float | int | str | None
    source: str
    as_of: date | None = None
    confidence: str = "medium"
    fallback_reason: str | None = None


@dataclass(slots=True)
class MarketContext:
    market: str
    currency: str
    share_price: float | None = None
    shares_outstanding: float | None = None
    diluted_shares_outstanding: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    beta: float | None = None
    report_date: date | None = None


@dataclass(slots=True)
class ValuationInput:
    ticker: str
    market: MarketContext
    financials: list[FinancialSnapshot] = field(default_factory=list)
    assumptions: dict[str, AssumptionValue] = field(default_factory=dict)
    instrument_type: str = "operating_company"
    valuation_applicability: str = "applicable"
    valuation_applicability_reason: str | None = None
```

`MarketContext.beta` is the resolved numeric value used in WACC. `assumptions["beta"]` remains the provenance record and must be kept in sync with the resolved field. `diluted_shares_outstanding` should be used for per-share value when available, and only fall back to `shares_outstanding` when diluted data is absent. If a provider cannot supply diluted shares in Phase 1, leave the field `None` and rely on the fallback path explicitly.

**Step 4: Run test to verify it passes**

Run: `pytest tests/valuation/test_schemas.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add diverge/valuation/schemas.py tests/valuation/test_schemas.py
git commit -m "feat: extend valuation schemas for assumption provenance"
```

### Task 3: Build non-CN valuation inputs from yfinance

**Files:**
- Create: `diverge/dataflows/yfinance_valuation.py`
- Modify: `diverge/dataflows/y_finance.py`
- Test: `tests/dataflows/test_yfinance_valuation.py`

**Step 1: Write the failing test**

```python
from diverge.dataflows.yfinance_valuation import build_yfinance_valuation_input


def test_build_yfinance_valuation_input_collects_growth_beta_and_treasury(monkeypatch):
    class FakeTicker:
        info = {"beta": 1.15, "sharesOutstanding": 100, "currentPrice": 50}

        def get_income_stmt(self, as_dict=False, pretty=False, freq="yearly"):
            return {"2025-12-31": {"Total Revenue": 1000, "Net Income": 120}}

        def get_cash_flow(self, as_dict=False, pretty=False, freq="yearly"):
            return {"2025-12-31": {"Free Cash Flow": 100}}

        def get_balance_sheet(self, as_dict=False, pretty=False, freq="yearly"):
            return {"2025-12-31": {"Cash And Cash Equivalents": 50, "Total Debt": 200}}

        def get_earnings_estimate(self, as_dict=False):
            return {"0y": {"growth": 0.18}, "+1y": {"growth": 0.12}}

        def get_revenue_estimate(self, as_dict=False):
            return {"0y": {"growth": 0.22}, "+1y": {"growth": 0.15}}

        def get_growth_estimates(self, as_dict=False):
            return {"+5y": {"stock": 0.14}}

        def history(self, *args, **kwargs):
            import pandas as pd
            return pd.DataFrame({"Close": [4.2]})

    monkeypatch.setattr("diverge.dataflows.yfinance_valuation.yf.Ticker", lambda symbol: FakeTicker())
    monkeypatch.setattr(
        "diverge.dataflows.yfinance_valuation._get_us_risk_free_rate",
        lambda: AssumptionValue(value=0.042, source="yfinance:^TNX", confidence="medium"),
    )

    valuation_input = build_yfinance_valuation_input("AAPL", curr_date="2026-03-24", freq="annual")

    assert valuation_input.market.market == "us"
    assert valuation_input.market.beta == 1.15
    assert valuation_input.assumptions["risk_free_rate"].source == "yfinance:^TNX"
    assert valuation_input.assumptions["short_term_growth"].source.startswith("yfinance")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/dataflows/test_yfinance_valuation.py -q`

Expected: FAIL because the module does not exist.

**Step 3: Write minimal implementation**

```python
import yfinance as yf

from diverge.valuation.schemas import AssumptionValue, FinancialSnapshot, MarketContext, ValuationInput


def _get_us_risk_free_rate() -> AssumptionValue:
    treasury = yf.Ticker("^TNX").history(period="5d")
    latest = float(treasury["Close"].dropna().iloc[-1]) / 100.0
    return AssumptionValue(value=latest, source="yfinance:^TNX", confidence="medium")


def build_yfinance_valuation_input(ticker: str, curr_date: str | None = None, freq: str = "annual") -> ValuationInput:
    ticker_obj = yf.Ticker(ticker.upper())
    info = ticker_obj.info
    assumptions = {
        "risk_free_rate": _get_us_risk_free_rate(),
        "beta": AssumptionValue(value=info.get("beta"), source="yfinance.info"),
    }

    def _build_yfinance_snapshots(ticker_obj, freq: str) -> list[FinancialSnapshot]:
        income = ticker_obj.get_income_stmt(as_dict=True, pretty=True, freq="yearly")
        cashflow = ticker_obj.get_cash_flow(as_dict=True, pretty=True, freq="yearly")
        balance = ticker_obj.get_balance_sheet(as_dict=True, pretty=True, freq="yearly")
        # Iterate each report date, merge statement rows by date, and return sorted FinancialSnapshot objects.
        return snapshots

    # Populate short_term_growth from earnings_estimate, revenue_estimate, growth_estimates in priority order.
    return ValuationInput(
        ticker=ticker.upper(),
        market=MarketContext(
            market="us",
            currency=info.get("currency") or "USD",
            share_price=info.get("currentPrice"),
            shares_outstanding=info.get("sharesOutstanding"),
            diluted_shares_outstanding=info.get("impliedSharesOutstanding"),
            market_cap=info.get("marketCap"),
            enterprise_value=info.get("enterpriseValue"),
            beta=info.get("beta"),
        ),
        financials=_build_yfinance_snapshots(ticker_obj, freq=freq),
        assumptions=assumptions,
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/dataflows/test_yfinance_valuation.py -q`

Expected: PASS for happy-path and fallback-path cases.

**Step 5: Commit**

```bash
git add diverge/dataflows/yfinance_valuation.py diverge/dataflows/y_finance.py tests/dataflows/test_yfinance_valuation.py
git commit -m "feat: add yfinance valuation input builder"
```

### Task 4: Build CN valuation inputs from AkShare

**Files:**
- Create: `diverge/dataflows/akshare_valuation.py`
- Modify: `diverge/dataflows/akshare_fundamentals.py`
- Test: `tests/dataflows/test_akshare_valuation.py`

**Step 1: Write the failing test**

```python
from diverge.dataflows.akshare_valuation import build_akshare_valuation_input


def test_build_akshare_valuation_input_uses_bond_and_research_sources(monkeypatch):
    import pandas as pd

    def fake_financial_report(*args, **kwargs):
        symbol = kwargs["symbol"]
        if symbol == "利润表":
            return pd.DataFrame([{"报告日": "2025-12-31", "营业总收入": 1000, "净利润": 120}])
        if symbol == "资产负债表":
            return pd.DataFrame([{"报告日": "2025-12-31", "货币资金": 50, "负债合计": 200, "股东权益合计": 800}])
        return pd.DataFrame([{"报告日": "2025-12-31", "经营活动产生的现金流量净额": 150, "购建固定资产、无形资产和其他长期资产支付的现金": -50}])

    def fake_research_report(*args, **kwargs):
        return pd.DataFrame([{"报告日期": "2026-03-01", "2026盈利预测-收益": 0.18}])

    def fake_bond_rate():
        return pd.DataFrame([{"日期": "2026-03-24", "中国国债收益率10年": 2.3}])

    monkeypatch.setattr("diverge.dataflows.akshare_valuation.ak.stock_financial_report_sina", fake_financial_report)
    monkeypatch.setattr("diverge.dataflows.akshare_valuation.ak.stock_research_report_em", fake_research_report)
    monkeypatch.setattr("diverge.dataflows.akshare_valuation.ak.bond_zh_us_rate", fake_bond_rate)

    valuation_input = build_akshare_valuation_input("600519", curr_date="2026-03-24", freq="annual")

    assert valuation_input.market.market == "cn"
    assert valuation_input.assumptions["risk_free_rate"].source == "akshare:bond_zh_us_rate"
    assert valuation_input.assumptions["short_term_growth"].source == "akshare:stock_research_report_em"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/dataflows/test_akshare_valuation.py -q`

Expected: FAIL because the module does not exist.

**Step 3: Write minimal implementation**

```python
from diverge.valuation.schemas import AssumptionValue, MarketContext, ValuationInput
from diverge.dataflows.vendor_errors import VendorRetryableError


def _import_akshare():
    try:
        import akshare as ak
    except ModuleNotFoundError as exc:
        raise VendorRetryableError("akshare is not installed.") from exc
    return ak


def _get_cn_risk_free_rate() -> AssumptionValue:
    ak = _import_akshare()
    rates = ak.bond_zh_us_rate()
    latest = rates.dropna(subset=["中国国债收益率10年"]).iloc[-1]
    return AssumptionValue(
        value=float(latest["中国国债收益率10年"]) / 100.0,
        source="akshare:bond_zh_us_rate",
        confidence="medium",
    )


def build_akshare_valuation_input(ticker: str, curr_date: str | None = None, freq: str = "annual") -> ValuationInput:
    ak = _import_akshare()
    income_df, balance_df, cashflow_df = _fetch_multi_period_reports(ticker)
    research_df = ak.stock_research_report_em(symbol=ticker)
    assumptions = {
        "risk_free_rate": _get_cn_risk_free_rate(),
        "short_term_growth": _extract_cn_growth_assumption(research_df),
    }

    def _build_cn_snapshots(income_df, balance_df, cashflow_df) -> list[FinancialSnapshot]:
        # Merge the three statement dataframes on report date and return sorted FinancialSnapshot objects.
        return snapshots

    beta = None
    return ValuationInput(
        ticker=ticker,
        market=MarketContext(market="cn", currency="CNY", beta=beta),
        financials=_build_cn_snapshots(income_df, balance_df, cashflow_df),
        assumptions=assumptions,
    )
```

Do not block this task on CN beta regression. Phase 1 may explicitly return `beta=None` plus a low-confidence fallback note. CN beta regression lands in Task 5a below.

**Step 4: Run test to verify it passes**

Run: `pytest tests/dataflows/test_akshare_valuation.py -q`

Expected: PASS for source-selection and fallback tests.

**Step 5: Commit**

```bash
git add diverge/dataflows/akshare_valuation.py diverge/dataflows/akshare_fundamentals.py tests/dataflows/test_akshare_valuation.py
git commit -m "feat: add akshare valuation input builder for cn market"
```

### Task 5: Add assumption resolution and normalized FCFF

**Files:**
- Create: `diverge/valuation/assumptions.py`
- Create: `diverge/valuation/fcff.py`
- Test: `tests/valuation/test_assumptions.py`
- Test: `tests/valuation/test_fcff.py`

**Step 1: Write the failing tests**

```python
from diverge.valuation.assumptions import resolve_short_term_growth
from diverge.valuation.fcff import normalize_fcff
from diverge.valuation.schemas import AssumptionValue, FinancialSnapshot


def test_resolve_short_term_growth_prefers_provider_estimate():
    assumptions = {
        "short_term_growth": AssumptionValue(value=0.18, source="provider"),
        "historical_revenue_cagr": AssumptionValue(value=0.10, source="history"),
    }
    result = resolve_short_term_growth(assumptions)
    assert result.value == 0.18
    assert result.source == "provider"


def test_resolve_assumption_returns_existing_value_when_present():
    assumptions = {
        "risk_free_rate": AssumptionValue(value=0.04, source="provider"),
    }
    result = resolve_assumption(assumptions, "risk_free_rate", default=0.03)
    assert result.value == 0.04
    assert result.source == "provider"


def test_resolve_assumption_returns_default_with_low_confidence_when_missing():
    result = resolve_assumption({}, "risk_free_rate", default=0.03)
    assert result.value == 0.03
    assert result.confidence == "low"
    assert "Missing 'risk_free_rate'" in (result.fallback_reason or "")


def test_normalize_fcff_uses_multi_year_median_for_outlier_case():
    financials = [
        FinancialSnapshot(period="FY2023", free_cash_flow=100),
        FinancialSnapshot(period="FY2024", free_cash_flow=-300),
        FinancialSnapshot(period="FY2025", free_cash_flow=110),
    ]
    assert normalize_fcff(financials).value == 100
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/valuation/test_assumptions.py tests/valuation/test_fcff.py -q`

Expected: FAIL because the modules do not exist.

**Step 3: Write minimal implementation**

```python
def resolve_short_term_growth(assumptions: dict[str, AssumptionValue]) -> AssumptionValue:
    for key in ("short_term_growth", "historical_revenue_cagr", "historical_fcf_cagr"):
        assumption = assumptions.get(key)
        if assumption and assumption.value is not None:
            return assumption
    return AssumptionValue(
        value=0.05,
        source="internal-default",
        confidence="low",
        fallback_reason="No provider or historical growth signals available.",
    )


def resolve_assumption(
    assumptions: dict[str, AssumptionValue],
    key: str,
    *,
    default: float,
    source: str = "internal-default",
) -> AssumptionValue:
    assumption = assumptions.get(key)
    if assumption and assumption.value is not None:
        return assumption
    return AssumptionValue(
        value=default,
        source=source,
        confidence="low",
        fallback_reason=f"Missing '{key}' in valuation_input.assumptions.",
    )


def normalize_fcff(financials: list[FinancialSnapshot]) -> AssumptionValue:
    from statistics import median

    valid = [snapshot.free_cash_flow for snapshot in financials if snapshot.free_cash_flow is not None]
    if not valid:
        raise ValueError("normalized FCFF requires at least one free_cash_flow value")
    return AssumptionValue(value=median(valid), source="historical-median-fcff", confidence="medium")
```

Later refine `normalize_fcff()` to rebuild FCFF from CFO + CapEx when direct FCF is unavailable.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/valuation/test_assumptions.py tests/valuation/test_fcff.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add diverge/valuation/assumptions.py diverge/valuation/fcff.py tests/valuation/test_assumptions.py tests/valuation/test_fcff.py
git commit -m "feat: add assumption resolver and normalized fcff helper"
```

### Task 5a: Add CN beta calculation as a bounded follow-up helper

**Files:**
- Modify: `diverge/dataflows/akshare_valuation.py`
- Test: `tests/dataflows/test_akshare_valuation.py`

**Step 1: Write the failing test**

```python
def test_compute_cn_beta_returns_none_when_price_history_is_too_short():
    assert _compute_cn_beta("600519", benchmark="sh000300") is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/dataflows/test_akshare_valuation.py::test_compute_cn_beta_returns_none_when_price_history_is_too_short -q`

Expected: FAIL because `_compute_cn_beta()` does not exist.

**Step 3: Write minimal implementation**

```python
def _compute_cn_beta(ticker: str, benchmark: str = "sh000300") -> float | None:
    stock_returns = _load_stock_returns(ticker)
    benchmark_returns = _load_index_returns(benchmark)
    if len(stock_returns) < 60 or len(benchmark_returns) < 60:
        return None
    # Regress stock returns against benchmark returns and return the slope.
    return beta
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/dataflows/test_akshare_valuation.py -q`

Expected: PASS for both short-history fallback and happy-path regression cases.

**Step 5: Commit**

```bash
git add diverge/dataflows/akshare_valuation.py tests/dataflows/test_akshare_valuation.py
git commit -m "feat: add bounded cn beta regression helper"
```

### Task 6: Replace the DCF core with a multi-stage market-routed model with compatibility shim

**Files:**
- Modify: `diverge/valuation/dcf.py`
- Test: `tests/valuation/test_dcf.py`

**Step 1: Write the failing test**

```python
from datetime import date

import pytest

from diverge.valuation.dcf import calculate_dcf
from diverge.valuation.schemas import AssumptionValue, FinancialSnapshot, MarketContext, ValuationInput


def test_calculate_dcf_uses_multi_stage_growth_and_dynamic_cost_of_equity():
    valuation_input = ValuationInput(
        ticker="ACME",
        market=MarketContext(
            market="us",
            currency="USD",
            shares_outstanding=100,
            market_cap=5_000,
            beta=1.2,
        ),
        financials=[
            FinancialSnapshot(period="FY2023", report_date=date(2023, 12, 31), free_cash_flow=90, cash_and_equivalents=50, total_debt=200),
            FinancialSnapshot(period="FY2024", report_date=date(2024, 12, 31), free_cash_flow=100, cash_and_equivalents=50, total_debt=200),
            FinancialSnapshot(period="FY2025", report_date=date(2025, 12, 31), free_cash_flow=110, cash_and_equivalents=50, total_debt=200),
        ],
        assumptions={
            "short_term_growth": AssumptionValue(value=0.12, source="provider"),
            "terminal_growth_rate": AssumptionValue(value=0.03, source="internal-default"),
            "risk_free_rate": AssumptionValue(value=0.04, source="provider"),
            "equity_risk_premium": AssumptionValue(value=0.05, source="internal-config"),
        },
    )

    result = calculate_dcf(valuation_input, high_growth_years=3, fade_years=2)

    assert result.assumptions["wacc"] > result.assumptions["terminal_growth_rate"]
    assert len(result.forecast_cash_flows) == 5
    assert result.fair_value_per_share is not None
```

Also keep the existing legacy tests in `tests/valuation/test_dcf.py` until a compatibility shim is in place. Do not delete the old single-stage assertions in the first pass.

**Step 2: Run test to verify it fails**

Run: `pytest tests/valuation/test_dcf.py -q`

Expected: FAIL because the current function only supports a single growth rate and fixed WACC, and the new multi-stage test will fail.

**Step 3: Write minimal implementation**

```python
def calculate_dcf(
    valuation_input: ValuationInput,
    *,
    growth_rate: float | None = None,
    terminal_growth_rate: float | None = None,
    wacc: float | None = None,
    projection_years: int | None = None,
    high_growth_years: int = 3,
    fade_years: int = 2,
) -> DCFResult:
    if growth_rate is not None or terminal_growth_rate is not None or wacc is not None or projection_years is not None:
        return _calculate_legacy_dcf(
            valuation_input,
            growth_rate=growth_rate or 0.05,
            terminal_growth_rate=terminal_growth_rate or 0.02,
            wacc=wacc or 0.10,
            projection_years=projection_years or 5,
        )

    base_fcff = normalize_fcff(valuation_input.financials).value
    short_term_growth = resolve_short_term_growth(valuation_input.assumptions).value
    resolved_terminal_growth_rate = float(
        resolve_assumption(valuation_input.assumptions, "terminal_growth_rate", default=0.03).value
    )
    resolved_risk_free_rate = float(
        resolve_assumption(valuation_input.assumptions, "risk_free_rate", default=0.04).value
    )
    resolved_equity_risk_premium = float(
        resolve_assumption(valuation_input.assumptions, "equity_risk_premium", default=0.05).value
    )
    resolved_cost_of_debt = float(
        resolve_assumption(
            valuation_input.assumptions,
            "cost_of_debt",
            default=resolved_risk_free_rate + 0.015,
        ).value
    )
    resolved_tax_rate = float(
        resolve_assumption(valuation_input.assumptions, "tax_rate", default=0.25).value
    )
    beta = valuation_input.market.beta or 1.0
    cost_of_equity = resolved_risk_free_rate + beta * resolved_equity_risk_premium
    latest = valuation_input.latest_financial
    market_cap = valuation_input.market.market_cap or 0.0
    total_debt = latest.total_debt or 0.0
    capital_base = market_cap + total_debt
    if capital_base > 0:
        wacc = (
            market_cap / capital_base * cost_of_equity
            + total_debt / capital_base * resolved_cost_of_debt * (1 - resolved_tax_rate)
        )
    else:
        wacc = cost_of_equity

    growth_path = [short_term_growth] * high_growth_years
    for fade_year in range(1, fade_years + 1):
        fade_ratio = fade_year / (fade_years + 1)
        growth_path.append(
            short_term_growth + (resolved_terminal_growth_rate - short_term_growth) * fade_ratio
        )
    shares_outstanding = (
        valuation_input.market.diluted_shares_outstanding
        or valuation_input.market.shares_outstanding
    )
    # Forecast using growth_path, then compute terminal value off the final faded year.


def _calculate_legacy_dcf(
    valuation_input: ValuationInput,
    *,
    growth_rate: float,
    terminal_growth_rate: float,
    wacc: float,
    projection_years: int,
) -> DCFResult:
    # Move the current pre-refactor calculate_dcf() body here unchanged.
    ...
```

Keep the existing validation that `wacc > terminal_growth_rate`, and move the legacy single-stage logic into `_calculate_legacy_dcf()` so existing callers and tests continue to work during the migration window. In Phase 1, `format_valuation_sections()` intentionally stays on the legacy kwarg path for calculation while the new market-routed assumptions are surfaced in reporting; switching formatter-driven calculation to the new path is a separate Phase 2 migration.

Leave `diverge/valuation/sensitivity.py` unchanged in Phase 1. It can continue calling `calculate_dcf()` with explicit legacy kwargs through the compatibility shim. If that is the intended behavior, do not list `sensitivity.py` as a modified file in this task.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/valuation/test_dcf.py tests/valuation/test_fcff.py tests/valuation/test_assumptions.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add diverge/valuation/dcf.py tests/valuation/test_dcf.py
git commit -m "feat: add multi-stage market-routed dcf core"
```

### Task 7: Update report formatting and fundamentals analyst integration

**Files:**
- Modify: `diverge/valuation/formatter.py`
- Modify: `diverge/agents/analysts/fundamentals_analyst.py`
- Modify: `web/frontend/components/ReportViewer.tsx`
- Test: `tests/valuation/test_formatter.py`
- Test: `tests/agents/test_fundamentals_prompt_highlights.py`
- Test: `web/frontend/components/ReportViewer.test.mjs`

**Step 1: Write the failing test**

```python
from diverge.valuation.formatter import format_valuation_sections


def test_format_valuation_sections_renders_assumption_provenance():
    rendered = format_valuation_sections(_build_sample_input_with_assumptions())
    assert "## Valuation Assumptions" in rendered
    assert "yfinance:^TNX" in rendered or "akshare:bond_zh_us_rate" in rendered
    assert "Fallback Used" in rendered
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/valuation/test_formatter.py tests/agents/test_fundamentals_prompt_highlights.py -q`

Expected: FAIL because formatter does not render assumption provenance.

**Step 3: Write minimal implementation**

```python
def format_valuation_sections(
    valuation_input: ValuationInput,
    *,
    assumptions: dict[str, float | int] | None = None,
) -> str:
    config = {**DEFAULT_ASSUMPTIONS, **(assumptions or {})}
    ...
    sections.append(_format_assumptions(valuation_input))
    return "\n\n".join(section.strip() for section in sections if section).strip()


def _format_assumptions(valuation_input: ValuationInput) -> str:
    assumptions = valuation_input.assumptions
    lines = [
        "## Valuation Assumptions",
        "",
        "| Assumption | Value | Source | Confidence | Fallback Used |",
        "| --- | --- | --- | --- | --- |",
    ]
    for key in (
        "short_term_growth",
        "terminal_growth_rate",
        "risk_free_rate",
        "equity_risk_premium",
        "cost_of_debt",
        "tax_rate",
        "beta",
    ):
        assumption = assumptions.get(key)
        if not assumption:
            continue
        lines.append(
            f"| {key} | {assumption.value} | {assumption.source} | {assumption.confidence} | {assumption.fallback_reason or 'No'} |"
        )
    return "\n".join(lines)
```

Update the `format_valuation_sections()` call site in the same change. `_format_assumptions()` must stop consuming the numeric `config` dict directly; use `valuation_input.assumptions` for rendering provenance, and keep `config` only where legacy numeric defaults are still needed for transitional calculation behavior.

Keep `DCF Applicability`, `DCF Summary`, and `Sensitivity Summary` section names unchanged so downstream viewers and tests remain stable.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/valuation/test_formatter.py tests/agents/test_fundamentals_prompt_highlights.py web/frontend/components/ReportViewer.test.mjs -q`

Expected: PASS

**Step 5: Commit**

```bash
git add diverge/valuation/formatter.py diverge/agents/analysts/fundamentals_analyst.py web/frontend/components/ReportViewer.tsx tests/valuation/test_formatter.py tests/agents/test_fundamentals_prompt_highlights.py web/frontend/components/ReportViewer.test.mjs
git commit -m "feat: surface valuation assumption provenance in reports"
```

### Task 8: Add edge-case coverage and perform market-by-market validation

**Files:**
- Modify: `tests/dataflows/test_akshare_valuation.py`
- Modify: `tests/dataflows/test_yfinance_valuation.py`
- Modify: `tests/valuation/test_dcf.py`
- Modify: `tests/integration/test_skill_adoption_flow.py`
- Optional: `docs/plans/2026-03-24-market-routed-dcf-phase1.md`

**Step 1: Write the failing tests**

```python
def test_yfinance_fallback_marks_missing_beta_as_low_confidence():
    valuation_input = build_yfinance_valuation_input("AAPL", curr_date="2026-03-24", freq="annual")
    assert valuation_input.assumptions["beta"].confidence in {"low", "medium"}


def test_akshare_beta_returns_none_for_short_history():
    valuation_input = build_akshare_valuation_input("600519", curr_date="2026-03-24", freq="annual")
    assert valuation_input.market.beta is None or valuation_input.market.beta > 0
```

Add fixtures for:
- ETF / fund / index gating
- CN bond-rate missing
- `yfinance` Treasury proxy missing
- negative single-year FCF outlier
- REIT / bank / insurance marked `DCF Not Applicable`
- integration tests that patch `route_to_valuation_input()` or provider builders instead of `route_to_vendor()`

**Step 2: Run tests to verify they fail**

Run: `pytest tests/dataflows/test_yfinance_valuation.py tests/dataflows/test_akshare_valuation.py tests/valuation/test_dcf.py tests/integration/test_skill_adoption_flow.py -q`

Expected: FAIL until the fallback metadata and inapplicability logic are fully wired.

**Step 3: Write minimal implementation**

Implement:
- explicit low-confidence fallback markers
- provider-specific error messages
- `instrument_type -> valuation_applicability` rules for `reit`, `bank`, `insurance`, `etf`, `fund`, `index`
- update `tests/integration/test_skill_adoption_flow.py` to patch `diverge.dataflows.valuation_inputs.route_to_valuation_input` or `diverge.agents.utils.fundamental_data_tools.get_valuation_ready_fundamentals`, not `diverge.dataflows.interface.route_to_vendor`
- validation smoke helper for manual compare runs

**Step 4: Run verification**

Run:

```bash
pytest tests/valuation tests/dataflows tests/agents tests/integration/test_skill_adoption_flow.py -q
```

Expected: PASS

Manual smoke matrix:

```bash
python - <<'PY'
from diverge.graph.trading_graph import DivergeGraph
from diverge.default_config import DEFAULT_CONFIG

graph = DivergeGraph(debug=False, config=DEFAULT_CONFIG.copy())
for ticker in ("NVDA", "SPY", "600519", "000001.SZ"):
    _, decision = graph.propagate(ticker, "2026-03-24")
    print(ticker, (decision or "")[:200])
PY
```

Expected:
- `NVDA`: `DCF Applicable`, `yfinance` assumption sources visible
- `SPY`: `DCF Not Applicable`
- `600519` / `000001.SZ`: `DCF Applicable`, `akshare` assumption sources visible

**Step 5: Commit**

```bash
git add tests/dataflows/test_yfinance_valuation.py tests/dataflows/test_akshare_valuation.py tests/valuation/test_dcf.py tests/integration/test_skill_adoption_flow.py
git commit -m "test: add market-routed valuation edge case coverage"
```

## Notes for the Implementer

- Do not break the existing `fundamentals_report: str` contract.
- Keep all provider-specific parsing out of `diverge/valuation/dcf.py`.
- Treat `ERP` as internal configuration, not provider truth.
- For non-CN markets, use `yfinance` only in this phase.
- For CN markets, use `AkShare` only in this phase, even though the general fundamentals vendor order currently prefers `tushare`.
- `MarketContext.beta` is the resolved numeric value consumed by DCF; `assumptions["beta"]` is the provenance record.
- Mark `REIT`, `bank`, and `insurance` as `DCF Not Applicable` until sector-specific models are introduced.
