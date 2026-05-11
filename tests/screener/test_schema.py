import pytest

from diverge.screener.presets import list_filter_preset_groups
from diverge.screener.schema import ScreenRunConfig


def test_screen_run_config_accepts_valid_dual_market_input():
    config = ScreenRunConfig(
        markets=["cn", "us"],
        as_of_date="2026-03-24",
        top_k=100,
        cn_data_source="akshare",
        cn_data_source_fallbacks=["tushare"],
        us_data_source="tushare",
        us_data_source_fallbacks=["massive"],
        cn_manifest_path=" /tmp/cn_manifest.csv ",
        us_manifest_path=" /tmp/us_manifest.csv ",
    )

    assert config.markets == ["cn", "us"]
    assert config.top_k == 100
    assert not hasattr(config, "limit_per_market")
    assert config.cn_data_source == "akshare"
    assert config.cn_data_source_fallbacks == ["tushare"]
    assert config.us_data_source == "tushare"
    assert config.us_data_source_fallbacks == ["massive"]
    assert config.cn_manifest_path == "/tmp/cn_manifest.csv"
    assert config.us_manifest_path == "/tmp/us_manifest.csv"
    assert config.history_cache_policy == "refresh_missing"


def test_screen_run_config_rejects_top_k_above_warmup_limit():
    with pytest.raises(ValueError, match="top_k"):
        ScreenRunConfig(
            markets=["cn"],
            as_of_date="2026-03-24",
            top_k=101,
        )


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


def test_screen_run_config_rejects_invalid_us_fallback_data_source():
    with pytest.raises(ValueError, match="us_data_source_fallbacks"):
        ScreenRunConfig(
            markets=["us"],
            as_of_date="2026-03-24",
            top_k=50,
            us_data_source="massive",
            us_data_source_fallbacks=["bogus"],
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


def test_screen_run_config_accepts_filter_presets_and_ranking_profile():
    config = ScreenRunConfig(
        markets=["cn"],
        as_of_date="2026-03-24",
        top_k=20,
        filter_preset_selections={"rsi": "strength_60"},
        ranking_profile_id="technical_pattern_balanced",
    )

    assert config.filter_preset_selections["rsi"] == "strength_60"
    assert config.filter_preset_selections["pattern"] == "any"
    assert config.ranking_profile_id == "technical_pattern_balanced"


def test_filter_presets_split_composite_groups_into_dedicated_dropdowns():
    groups = {group["id"]: group for group in list_filter_preset_groups()}

    assert not {
        "moving_average",
        "performance",
        "valuation",
        "quality",
        "growth",
        "balance_sheet",
    } & set(groups)
    assert groups["ma20_position"]["label"] == "MA20"
    assert groups["ma60_position"]["label"] == "MA60"
    assert groups["ma_alignment"]["label"] == "MA Alignment"
    assert groups["ret_20"]["label"] == "20D Return"
    assert groups["ret_60"]["label"] == "60D Return"
    assert groups["pe_ttm"]["label"] == "P/E"
    assert groups["ps_ttm"]["label"] == "P/S"
    assert groups["pb"]["label"] == "P/B"
    assert groups["peg"]["label"] == "PEG"
    assert groups["roe"]["label"] == "ROE"
    assert groups["gross_margin"]["label"] == "Gross Margin"
    assert groups["net_margin"]["label"] == "Net Margin"
    assert groups["revenue_growth_yoy"]["label"] == "Revenue Growth"
    assert groups["net_income_growth_yoy"]["label"] == "Net Income Growth"
    assert groups["current_ratio"]["label"] == "Current Ratio"
    assert groups["debt_to_assets"]["label"] == "Debt / Assets"
    assert {option["value"] for option in groups["ma20_position"]["options"]} >= {
        "any",
        "price_above_ma20",
        "near_ma20_3pct",
        "below_ma20",
    }
    assert {option["value"] for option in groups["ma60_position"]["options"]} >= {
        "any",
        "price_above_ma60",
        "below_ma60",
    }
    assert {option["value"] for option in groups["ret_20"]["options"]} >= {
        "any",
        "ret20_positive",
        "ret20_5",
        "ret20_negative",
    }
    assert {option["value"] for option in groups["pe_ttm"]["options"]} >= {
        "any",
        "pe_lte_20",
        "pe_lte_40",
    }
    assert {option["value"] for option in groups["ps_ttm"]["options"]} >= {
        "any",
        "ps_lte_5",
        "ps_lte_10",
    }
    assert {option["value"] for option in groups["pb"]["options"]} >= {
        "any",
        "pb_lte_3",
        "pb_lte_5",
    }
    assert {option["value"] for option in groups["peg"]["options"]} >= {
        "any",
        "peg_lte_1_5",
        "peg_lte_2",
    }


def test_screen_run_config_accepts_split_filter_presets():
    config = ScreenRunConfig(
        markets=["cn"],
        as_of_date="2026-03-24",
        top_k=20,
        filter_preset_selections={
            "ma20_position": "near_ma20_3pct",
            "ma60_position": "price_above_ma60",
            "ma_alignment": "bullish_alignment",
            "ret_20": "ret20_5",
            "ret_60": "ret60_10",
            "pe_ttm": "pe_lte_20",
            "ps_ttm": "ps_lte_5",
            "pb": "pb_lte_3",
            "peg": "peg_lte_1_5",
            "roe": "roe_gte_20",
            "gross_margin": "gross_margin_gte_30",
            "net_margin": "net_margin_gte_10",
            "revenue_growth_yoy": "revenue_growth_gte_20",
            "net_income_growth_yoy": "income_growth_gte_10",
            "current_ratio": "current_ratio_gte_1_5",
            "debt_to_assets": "debt_assets_lte_60",
        },
    )

    assert config.filter_preset_selections["ma20_position"] == "near_ma20_3pct"
    assert config.filter_preset_selections["ma60_position"] == "price_above_ma60"
    assert config.filter_preset_selections["ma_alignment"] == "bullish_alignment"
    assert config.filter_preset_selections["ret_20"] == "ret20_5"
    assert config.filter_preset_selections["ret_60"] == "ret60_10"
    assert config.filter_preset_selections["pe_ttm"] == "pe_lte_20"
    assert config.filter_preset_selections["ps_ttm"] == "ps_lte_5"
    assert config.filter_preset_selections["pb"] == "pb_lte_3"
    assert config.filter_preset_selections["peg"] == "peg_lte_1_5"
    assert config.filter_preset_selections["roe"] == "roe_gte_20"
    assert config.filter_preset_selections["gross_margin"] == "gross_margin_gte_30"
    assert config.filter_preset_selections["net_margin"] == "net_margin_gte_10"
    assert (
        config.filter_preset_selections["revenue_growth_yoy"] == "revenue_growth_gte_20"
    )
    assert (
        config.filter_preset_selections["net_income_growth_yoy"]
        == "income_growth_gte_10"
    )
    assert config.filter_preset_selections["current_ratio"] == "current_ratio_gte_1_5"
    assert config.filter_preset_selections["debt_to_assets"] == "debt_assets_lte_60"
    assert not {
        "moving_average",
        "performance",
        "valuation",
        "quality",
        "growth",
        "balance_sheet",
    } & set(config.filter_preset_selections)


def test_screen_run_config_migrates_legacy_valuation_preset_selection():
    config = ScreenRunConfig(
        markets=["cn"],
        as_of_date="2026-03-24",
        top_k=20,
        filter_preset_selections={
            "moving_average": "bullish_alignment",
            "performance": "ret60_10",
            "valuation": "ps_lte_10",
            "quality": "gross_margin_gte_30",
            "growth": "income_growth_gte_10",
            "balance_sheet": "debt_assets_lte_60",
        },
    )

    assert config.filter_preset_selections["ma_alignment"] == "bullish_alignment"
    assert config.filter_preset_selections["ret_60"] == "ret60_10"
    assert config.filter_preset_selections["ps_ttm"] == "ps_lte_10"
    assert config.filter_preset_selections["gross_margin"] == "gross_margin_gte_30"
    assert (
        config.filter_preset_selections["net_income_growth_yoy"]
        == "income_growth_gte_10"
    )
    assert config.filter_preset_selections["debt_to_assets"] == "debt_assets_lte_60"
    assert not {
        "moving_average",
        "performance",
        "valuation",
        "quality",
        "growth",
        "balance_sheet",
    } & set(config.filter_preset_selections)


def test_screen_run_config_rejects_unknown_filter_preset():
    with pytest.raises(ValueError, match="unknown screener filter preset"):
        ScreenRunConfig(
            markets=["cn"],
            as_of_date="2026-03-24",
            top_k=20,
            filter_preset_selections={"rsi": "mystery"},
        )


def test_screen_run_config_rejects_unknown_ranking_profile():
    with pytest.raises(ValueError, match="ranking profile"):
        ScreenRunConfig(
            markets=["cn"],
            as_of_date="2026-03-24",
            top_k=20,
            ranking_profile_id="mystery",
        )


def test_screen_run_config_accepts_cache_only_and_fundamental_sources(tmp_path):
    config = ScreenRunConfig(
        markets=["us"],
        as_of_date="2026-03-24",
        top_k=20,
        us_manifest_path="/tmp/us.csv",
        history_cache_policy="cache_only",
        include_fundamentals=True,
        fundamental_dir=str(tmp_path),
        us_fundamental_source="simfin",
    )

    assert config.history_cache_policy == "cache_only"
    assert config.include_fundamentals is True
    assert config.fundamental_dir == str(tmp_path)


def test_screen_run_config_rejects_unknown_history_cache_policy():
    with pytest.raises(ValueError, match="history_cache_policy"):
        ScreenRunConfig(
            markets=["cn"],
            as_of_date="2026-03-24",
            top_k=20,
            history_cache_policy="online_only",
        )
