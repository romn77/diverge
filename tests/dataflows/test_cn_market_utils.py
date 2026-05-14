from diverge.dataflows.cn_market_utils import (
    detect_market,
    parse_and_normalize_cn_ticker,
)


def test_cn_market_utils_keeps_symbol_compatibility_imports():
    assert detect_market("600519") == "cn"
    assert parse_and_normalize_cn_ticker("600519")["tushare"] == "600519.SH"
