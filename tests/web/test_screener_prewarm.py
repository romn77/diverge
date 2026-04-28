from __future__ import annotations

from datetime import datetime, timezone

from web.backend import app_config, screener_presets
from web.backend.runtime import screener_prewarm


def _payload(market: str = "cn") -> dict:
    return {
        "markets": [market],
        "as_of_date": None,
        "top_k": 50,
        "cn_data_source": "tushare",
        "us_data_source": "massive",
        "history_cache_policy": "cache_only",
        "breakout_types": [],
        "filter_preset_selections": {"ma20_position": "price_above_ma20"},
        "ranking_profile_id": "technical_pattern_balanced",
        "include_fundamentals": False,
        "cn_fundamental_source": "tushare",
        "us_fundamental_source": "simfin",
    }


def test_screener_presets_persist_user_configs_for_background_prewarm(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "SCREENER_STATE_DIR", tmp_path / "state")

    saved = screener_presets.save_screener_presets(
        "user-1",
        [{"id": "trend", "name": "Trend", "config": _payload("cn")}],
        tenant_id="tenant-1",
    )

    assert saved[0]["owner_user_id"] == "user-1"
    assert screener_presets.load_screener_presets("user-1")[0]["name"] == "Trend"
    configs = screener_presets.list_all_screener_preset_configs()
    assert configs[0]["owner_user_id"] == "user-1"
    assert configs[0]["config"]["filter_preset_selections"]["ma20_position"] == "price_above_ma20"


def test_collect_screener_prewarm_payloads_includes_default_and_matching_user_presets(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(app_config, "SCREENER_STATE_DIR", tmp_path / "state")
    screener_presets.save_screener_presets(
        "user-1",
        [
            {"id": "cn-trend", "name": "CN Trend", "config": _payload("cn")},
            {"id": "us-trend", "name": "US Trend", "config": _payload("us")},
        ],
    )

    payloads = screener_prewarm.collect_screener_prewarm_payloads(
        "cn",
        "2026-04-28",
    )

    assert [payload["markets"] for payload in payloads] == [["cn"], ["cn"]]
    assert payloads[0]["filter_preset_selections"]["ma20_position"] == "any"
    assert payloads[1]["filter_preset_selections"]["ma20_position"] == "price_above_ma20"
    assert all(payload["history_cache_policy"] == "cache_only" for payload in payloads)


def test_due_market_trading_day_waits_until_market_close():
    before_close = datetime(2026, 4, 28, 6, 59, tzinfo=timezone.utc)
    after_close = datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc)

    assert screener_prewarm.due_market_trading_day("cn", before_close) is None
    assert screener_prewarm.due_market_trading_day("cn", after_close) == "2026-04-28"
