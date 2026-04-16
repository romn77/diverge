from __future__ import annotations

import pandas as pd


class _FakeAkshare:
    @staticmethod
    def stock_financial_report_sina(stock: str, symbol: str):
        if symbol == "利润表":
            return pd.DataFrame(
                [
                    {"报告日": "2025-12-31", "营业总收入": 1_000.0, "净利润": 120.0},
                    {"报告日": "2024-12-31", "营业总收入": 950.0, "净利润": 110.0},
                ]
            )
        if symbol == "资产负债表":
            return pd.DataFrame(
                [
                    {
                        "报告日": "2025-12-31",
                        "货币资金": 50.0,
                        "负债合计": 200.0,
                        "股东权益合计": 800.0,
                    },
                    {
                        "报告日": "2024-12-31",
                        "货币资金": 45.0,
                        "负债合计": 210.0,
                        "股东权益合计": 760.0,
                    },
                ]
            )
        return pd.DataFrame(
            [
                {
                    "报告日": "2025-12-31",
                    "经营活动产生的现金流量净额": 150.0,
                    "购建固定资产、无形资产和其他长期资产支付的现金": -50.0,
                },
                {
                    "报告日": "2024-12-31",
                    "经营活动产生的现金流量净额": 140.0,
                    "购建固定资产、无形资产和其他长期资产支付的现金": -45.0,
                },
            ]
        )

    @staticmethod
    def stock_research_report_em(symbol: str):
        return pd.DataFrame(
            [
                {"日期": "2026-03-01", "2026-盈利预测-收益": 0.18},
                {"日期": "2026-02-01", "2026-盈利预测-收益": 0.16},
            ]
        )

    @staticmethod
    def bond_zh_us_rate(start_date: str = "19901219"):
        return pd.DataFrame(
            [
                {
                    "日期": "2026-03-20",
                    "中国国债收益率10年": None,
                    "美国国债收益率10年": 4.2,
                },
                {
                    "日期": "2026-03-24",
                    "中国国债收益率10年": 2.3,
                    "美国国债收益率10年": None,
                },
            ]
        )


def test_build_akshare_valuation_input_uses_bond_and_research_sources(monkeypatch):
    from tradingagents.dataflows.akshare_valuation import build_akshare_valuation_input

    monkeypatch.setattr(
        "tradingagents.dataflows.akshare_valuation._import_akshare",
        lambda: _FakeAkshare(),
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.akshare_valuation.call_akshare_api",
        lambda func, *args, **kwargs: func(*args, **kwargs),
    )

    valuation_input = build_akshare_valuation_input(
        "600519",
        curr_date="2026-03-24",
        freq="annual",
    )

    assert valuation_input.market.market == "cn"
    assert valuation_input.assumptions["risk_free_rate"].source == "akshare:bond_zh_us_rate"
    assert valuation_input.assumptions["risk_free_rate"].value == 0.023
    assert valuation_input.assumptions["short_term_growth"].source == "akshare:stock_research_report_em"
    assert valuation_input.latest_financial.free_cash_flow == 100.0
    assert len(valuation_input.financials) == 2


def test_compute_cn_beta_returns_none_when_price_history_is_too_short(monkeypatch):
    from tradingagents.dataflows.akshare_valuation import _compute_cn_beta

    monkeypatch.setattr(
        "tradingagents.dataflows.akshare_valuation.call_akshare_api",
        lambda func, *args, **kwargs: func(*args, **kwargs),
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.akshare_valuation._load_stock_returns",
        lambda ticker: [0.01] * 10,
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.akshare_valuation._load_index_returns",
        lambda ticker: [0.01] * 10,
    )

    assert _compute_cn_beta("600519", benchmark="sh000300") is None
