from diverge.dataflows import routes


def test_history_source_kwargs_for_market_uses_route(monkeypatch):
    def fake_route(*, module, market, category):
        assert module == "analysis"
        assert category == routes.CORE_STOCK_CATEGORY
        return ["akshare", "tushare"] if market == "cn" else []

    monkeypatch.setattr(routes.vendor_usage, "get_data_source_route", fake_route)

    assert routes.history_source_kwargs_for_market(module="analysis", market="cn") == {
        "cn_data_source": "akshare",
        "cn_data_source_fallbacks": ["tushare"],
    }
    assert routes.history_source_kwargs_for_market(module="analysis", market="us") == {
        "us_data_source": "massive",
        "us_data_source_fallbacks": [],
    }


def test_dual_market_history_source_kwargs_resolves_screener_defaults(monkeypatch):
    monkeypatch.setattr(
        routes.vendor_usage,
        "get_data_source_route",
        lambda **_: [],
    )

    assert routes.dual_market_history_source_kwargs(module="screener") == {
        "cn_data_source": "tushare",
        "cn_data_source_fallbacks": [],
        "us_data_source": "massive",
        "us_data_source_fallbacks": [],
    }
