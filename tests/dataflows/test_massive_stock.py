from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from tradingagents.dataflows.vendor_errors import VendorAuthError
from tradingagents.dataflows.massive_stock import _fetch_massive_stock_df, get_stock


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


def test_fetch_massive_stock_df_paginates_and_normalizes_response():
    responses = [
        _FakeResponse(
            {
                "results": [
                    {
                        "t": "2026-03-24T00:00:00Z",
                        "o": 100.0,
                        "h": 102.0,
                        "l": 99.5,
                        "c": 101.0,
                        "v": 500,
                    }
                ],
                "next_page_token": "page-2",
            }
        ),
        _FakeResponse(
            {
                "results": [
                    {
                        "t": "2026-03-25T00:00:00Z",
                        "o": 101.0,
                        "h": 103.0,
                        "l": 100.5,
                        "c": 102.0,
                        "v": 600,
                    }
                ],
            }
        ),
    ]
    get_mock = Mock(side_effect=responses)

    with (
        patch("tradingagents.dataflows.massive_common.requests.get", get_mock),
        patch.dict(
            "os.environ",
            {"MASSIVE_API_KEY": "test-token"},
            clear=False,
        ),
    ):
        df = _fetch_massive_stock_df("AAPL", "2026-03-24", "2026-03-25")

    assert df["Date"].tolist() == [pd.Timestamp("2026-03-24T00:00:00Z"), pd.Timestamp("2026-03-25T00:00:00Z")]
    assert df["Close"].tolist() == [101.0, 102.0]
    assert get_mock.call_count == 2
    first_call = get_mock.call_args_list[0]
    assert first_call.kwargs["headers"]["X-API-KEY"] == "test-token"
    assert first_call.kwargs["params"]["tickers"] == "AAPL"
    assert first_call.kwargs["params"]["interval"] == "1Day"
    assert first_call.kwargs["params"]["price_adjust"] == "raw"


def test_fetch_massive_stock_df_parses_wrapper_bars_dict_shape():
    responses = [
        _FakeResponse(
            {
                "bars": {
                    "GOOG": [
                        {
                            "t": "2026-03-24T00:00:00Z",
                            "o": 169.0,
                            "h": 169.53,
                            "l": 165.48,
                            "c": 166.57,
                            "v": 224126,
                            "n": 269746,
                        }
                    ]
                },
                "next_page_token": None,
            }
        ),
    ]
    get_mock = Mock(side_effect=responses)

    with (
        patch("tradingagents.dataflows.massive_common.requests.get", get_mock),
        patch.dict("os.environ", {"MASSIVE_API_KEY": "test-token"}, clear=False),
    ):
        df = _fetch_massive_stock_df("GOOG", "2026-03-24", "2026-03-24")

    assert df["Close"].tolist() == [166.57]
    assert df["Transactions"].tolist() == [269746]


def test_fetch_massive_stock_df_uses_massive_rate_limiter_for_each_page():
    responses = [
        _FakeResponse(
            {
                "results": [
                    {
                        "t": "2026-03-24T00:00:00Z",
                        "o": 100.0,
                        "h": 102.0,
                        "l": 99.5,
                        "c": 101.0,
                        "v": 500,
                    }
                ],
                "next_page_token": "page-2",
            }
        ),
        _FakeResponse(
            {
                "results": [
                    {
                        "t": "2026-03-25T00:00:00Z",
                        "o": 101.0,
                        "h": 103.0,
                        "l": 100.5,
                        "c": 102.0,
                        "v": 600,
                    }
                ],
            }
        ),
    ]
    get_mock = Mock(side_effect=responses)

    with (
        patch("tradingagents.dataflows.massive_common.requests.get", get_mock),
        patch("tradingagents.dataflows.massive_common._apply_massive_rate_limit") as mock_rate_limit,
        patch.dict("os.environ", {"MASSIVE_API_KEY": "test-token"}, clear=False),
    ):
        _fetch_massive_stock_df("AAPL", "2026-03-24", "2026-03-25")

    assert mock_rate_limit.call_count == 2


def test_get_stock_formats_massive_dataframe_as_string():
    df = pd.DataFrame(
        [
            {
                "Date": "2026-03-24",
                "Open": 100.0,
                "High": 102.0,
                "Low": 99.5,
                "Close": 101.0,
                "Volume": 500,
            }
        ]
    )

    with patch("tradingagents.dataflows.massive_stock._fetch_massive_stock_df", return_value=df):
        result = get_stock("AAPL", "2026-03-24", "2026-03-24")

    assert "Stock data for AAPL" in result
    assert "2026-03-24" in result


def test_fetch_massive_stock_df_requires_token():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(VendorAuthError, match="MASSIVE"):
            _fetch_massive_stock_df("AAPL", "2026-03-24", "2026-03-24")
