from diverge.ticker_symbols import normalize_ticker_symbol


def test_ticker_symbols_keeps_normalize_ticker_compatibility_import():
    assert normalize_ticker_symbol(" cnc.to ") == "CNC.TO"
