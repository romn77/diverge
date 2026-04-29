import copy

import diverge.default_config as default_config
import diverge.dataflows.config as config_module


def setup_function():
    config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)


def test_route_to_valuation_input_uses_yfinance_for_us(monkeypatch):
    from diverge.dataflows import valuation_inputs

    calls = []

    def fake_yf(*args, **kwargs):
        calls.append("yfinance")
        return "ok"

    def fake_ak(*args, **kwargs):
        calls.append("akshare")
        return "bad"

    monkeypatch.setattr(valuation_inputs, "build_yfinance_valuation_input", fake_yf)
    monkeypatch.setattr(valuation_inputs, "build_akshare_valuation_input", fake_ak)

    result = valuation_inputs.route_to_valuation_input(
        "AAPL",
        curr_date="2026-03-24",
    )

    assert result == "ok"
    assert calls == ["yfinance"]


def test_route_to_valuation_input_uses_akshare_for_cn(monkeypatch):
    from diverge.dataflows import valuation_inputs

    calls = []

    def fake_yf(*args, **kwargs):
        calls.append("yfinance")
        return "bad"

    def fake_ak(*args, **kwargs):
        calls.append("akshare")
        return "ok"

    monkeypatch.setattr(valuation_inputs, "build_yfinance_valuation_input", fake_yf)
    monkeypatch.setattr(valuation_inputs, "build_akshare_valuation_input", fake_ak)

    result = valuation_inputs.route_to_valuation_input(
        "600519",
        curr_date="2026-03-24",
    )

    assert result == "ok"
    assert calls == ["akshare"]
