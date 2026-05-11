from __future__ import annotations

from diverge.dataflows.vendors.tencent.quote import (
    parse_quote_response,
    us_symbol_to_tencent_code,
)


def test_us_symbol_to_tencent_code_defaults_to_nasdaq_suffix():
    assert us_symbol_to_tencent_code("aapl") == "usAAPL.OQ"
    assert us_symbol_to_tencent_code("BRK.B") == "usBRK.B.OQ"


def test_parse_quote_response_handles_basic_us_quote_payload():
    text = 'v_usAAPL.OQ="51~Apple Inc.~AAPL.OQ~200.00~198.00~2.00~1.00~~~~1000000~~~~~~~~~~~~~~~~~~~~~~~~~~~~~25.0~~~~~3.0T";'

    rows = parse_quote_response(text)

    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["name"] == "Apple Inc."
    assert rows[0]["price"] == 200.0
    assert rows[0]["change_pct"] == 0.01
