from __future__ import annotations

from unittest.mock import Mock, patch

import pandas as pd


def test_fetch_akshare_stock_df_uses_rate_limiter():
    akshare_client = Mock()
    raw_df = pd.DataFrame(
        [
            {
                "日期": "2026-03-24",
                "开盘": 10.0,
                "收盘": 10.2,
                "最高": 10.5,
                "最低": 9.8,
                "成交量": 1000,
                "成交额": 25_000.0,
            }
        ]
    )

    with (
        patch("diverge.dataflows.akshare_stock._import_akshare", return_value=akshare_client),
        patch("diverge.dataflows.akshare_stock.call_akshare_api", return_value=raw_df) as mock_rate_limit,
    ):
        from diverge.dataflows.akshare_stock import _fetch_akshare_stock_df

        result = _fetch_akshare_stock_df("600519", "2025-01-01", "2026-03-24")

    assert result["Date"].tolist() == [pd.Timestamp("2026-03-24")]
    mock_rate_limit.assert_called_once_with(
        akshare_client.stock_zh_a_hist,
        symbol="600519",
        period="daily",
        start_date="20250101",
        end_date="20260324",
        adjust="qfq",
    )


def test_fetch_akshare_fundamentals_report_uses_rate_limiter():
    akshare_client = Mock()
    raw_df = pd.DataFrame([{"报告日": "2025-12-31", "营业总收入": 1000.0}])

    with (
        patch("diverge.dataflows.akshare_fundamentals._import_akshare", return_value=akshare_client),
        patch("diverge.dataflows.akshare_fundamentals.call_akshare_api", return_value=raw_df) as mock_rate_limit,
    ):
        from diverge.dataflows.akshare_fundamentals import _fetch_report

        result = _fetch_report("600519", "利润表")

    assert result.iloc[0]["营业总收入"] == 1000.0
    mock_rate_limit.assert_called_once()


def test_akshare_news_uses_rate_limiter():
    akshare_client = Mock()
    raw_df = pd.DataFrame([{"日期": "2026-03-24", "标题": "Example"}])

    with (
        patch("diverge.dataflows.akshare_news._import_akshare", return_value=akshare_client),
        patch("diverge.dataflows.akshare_news.call_akshare_api", return_value=raw_df) as mock_rate_limit,
    ):
        from diverge.dataflows.akshare_news import get_news

        result = get_news("600519", "2026-03-01", "2026-03-31")

    assert "Example" in result
    mock_rate_limit.assert_called_once_with(
        akshare_client.stock_research_report_em,
        symbol="600519",
    )


def test_akshare_valuation_risk_free_rate_uses_rate_limiter():
    akshare_client = Mock()
    raw_df = pd.DataFrame(
        [
            {"日期": "2026-03-24", "中国国债收益率10年": 2.3},
        ]
    )

    with (
        patch("diverge.dataflows.akshare_valuation._import_akshare", return_value=akshare_client),
        patch("diverge.dataflows.akshare_valuation.call_akshare_api", return_value=raw_df) as mock_rate_limit,
    ):
        from diverge.dataflows.akshare_valuation import _get_cn_risk_free_rate

        result = _get_cn_risk_free_rate()

    assert result.value == 0.023
    mock_rate_limit.assert_called_once_with(akshare_client.bond_zh_us_rate)
