import pytest

from tradingagents.screener.schema import ScreenRunConfig


def test_screen_run_config_accepts_valid_dual_market_input():
    config = ScreenRunConfig(
        markets=["cn", "us"],
        as_of_date="2026-03-24",
        top_k=100,
        cn_data_source="akshare",
        cn_data_source_fallbacks=["tushare"],
        us_data_source="tushare",
        cn_manifest_path=" /tmp/cn_manifest.csv ",
        us_manifest_path=" /tmp/us_manifest.csv ",
    )

    assert config.markets == ["cn", "us"]
    assert config.top_k == 100
    assert not hasattr(config, "limit_per_market")
    assert config.cn_data_source == "akshare"
    assert config.cn_data_source_fallbacks == ["tushare"]
    assert config.us_data_source == "tushare"
    assert config.cn_manifest_path == "/tmp/cn_manifest.csv"
    assert config.us_manifest_path == "/tmp/us_manifest.csv"


def test_screen_run_config_rejects_future_dates():
    with pytest.raises(ValueError, match="future"):
        ScreenRunConfig(
            markets=["cn"],
            as_of_date="2099-01-01",
            top_k=50,
        )


def test_screen_run_config_rejects_unknown_market_values():
    with pytest.raises(ValueError, match="markets"):
        ScreenRunConfig(
            markets=["cn", "hk"],
            as_of_date="2026-03-24",
            top_k=50,
        )


def test_screen_run_config_requires_us_manifest_when_us_market_requested():
    with pytest.raises(ValueError, match="us_manifest_path"):
        ScreenRunConfig(
            markets=["us"],
            as_of_date="2026-03-24",
            top_k=50,
        )


def test_screen_run_config_rejects_unknown_cn_data_source():
    with pytest.raises(ValueError, match="cn_data_source"):
        ScreenRunConfig(
            markets=["cn"],
            as_of_date="2026-03-24",
            top_k=50,
            cn_data_source="bogus",
        )


def test_screen_run_config_rejects_invalid_cn_fallback_data_source():
    with pytest.raises(ValueError, match="cn_data_source_fallbacks"):
        ScreenRunConfig(
            markets=["cn"],
            as_of_date="2026-03-24",
            top_k=50,
            cn_data_source="akshare",
            cn_data_source_fallbacks=["bogus"],
        )


def test_screen_run_config_rejects_unknown_us_data_source():
    with pytest.raises(ValueError, match="us_data_source"):
        ScreenRunConfig(
            markets=["us"],
            as_of_date="2026-03-24",
            top_k=50,
            us_data_source="bogus",
            us_manifest_path="/tmp/us_manifest.csv",
        )


def test_screen_run_config_accepts_massive_us_data_source():
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-03-24",
        top_k=20,
        us_data_source="massive",
        us_manifest_path="/tmp/us_manifest.csv",
    )

    assert config.us_data_source == "massive"
