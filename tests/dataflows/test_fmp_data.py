from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from diverge.dataflows.vendor_errors import VendorDataEmptyError


class _Response:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_fmp_income_statement_uses_stable_endpoint_and_filters_future_reports(monkeypatch):
    from diverge.dataflows.fmp_fundamentals import get_income_statement

    monkeypatch.setenv("FMP_API_KEY", "demo")
    payload = [
        {"date": "2027-01-01", "revenue": 999},
        {"date": "2025-12-31", "revenue": 123},
    ]

    with patch(
        "diverge.dataflows.fmp_common.requests.get",
        return_value=_Response(payload),
    ) as mock_get:
        result = get_income_statement("AAPL", "annual", "2026-04-26")

    assert json.loads(result) == {"annualReports": [{"date": "2025-12-31", "revenue": 123}]}
    url = mock_get.call_args.args[0]
    params = mock_get.call_args.kwargs["params"]
    assert url.endswith("/stable/income-statement")
    assert params["symbol"] == "AAPL"
    assert params["period"] == "annual"
    assert params["apikey"] == "demo"


def test_fmp_news_and_insider_transactions_use_stable_search_endpoints(monkeypatch):
    from diverge.dataflows.fmp_news import get_insider_transactions, get_news

    monkeypatch.setenv("FMP_API_KEY", "demo")

    with patch(
        "diverge.dataflows.fmp_common.requests.get",
        side_effect=[
            _Response([{"symbol": "AAPL", "title": "Apple news"}]),
            _Response([{"symbol": "AAPL", "transactionType": "S-Sale"}]),
        ],
    ) as mock_get:
        news = get_news("AAPL", "2026-04-01", "2026-04-26")
        insider = get_insider_transactions("AAPL")

    assert json.loads(news)[0]["title"] == "Apple news"
    assert json.loads(insider)[0]["transactionType"] == "S-Sale"
    first_call = mock_get.call_args_list[0]
    second_call = mock_get.call_args_list[1]
    assert first_call.args[0].endswith("/stable/news/stock")
    assert first_call.kwargs["params"]["symbols"] == "AAPL"
    assert second_call.args[0].endswith("/stable/insider-trading/search")
    assert second_call.kwargs["params"]["symbol"] == "AAPL"


def test_fmp_empty_payload_raises_empty_data_for_vendor_fallback(monkeypatch):
    from diverge.dataflows.fmp_fundamentals import get_fundamentals

    monkeypatch.setenv("FMP_API_KEY", "demo")

    with patch(
        "diverge.dataflows.fmp_common.requests.get",
        return_value=_Response([]),
    ):
        with pytest.raises(VendorDataEmptyError):
            get_fundamentals("AAPL", "2026-04-26")
