from __future__ import annotations

from web.backend import app_config, screener_presets
from web.backend.runtime import screener_prewarm
from web.backend.services import screener_prewarm_payloads


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


def test_screener_presets_persist_user_configs_for_background_prewarm(
    tmp_path, monkeypatch
):
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
    assert (
        configs[0]["config"]["filter_preset_selections"]["ma20_position"]
        == "price_above_ma20"
    )


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
    assert (
        payloads[1]["filter_preset_selections"]["ma20_position"] == "price_above_ma20"
    )
    assert all(payload["history_cache_policy"] == "cache_only" for payload in payloads)


def test_prewarm_payload_service_builds_ohlcv_payload_with_sources_and_manifest(
    tmp_path,
    monkeypatch,
):
    manifest_path = tmp_path / "us.csv"
    manifest_path.write_text("symbol\nAAPL\n", encoding="utf-8")
    monkeypatch.setattr(
        screener_prewarm_payloads,
        "get_screener_config_options_payload",
        lambda: {"defaults": {"top_k": 250}},
    )
    monkeypatch.setattr(
        screener_prewarm_payloads,
        "resolve_screener_data_sources",
        lambda: {
            "cn_data_source": "tushare",
            "cn_data_source_fallbacks": [],
            "us_data_source": "massive",
            "us_data_source_fallbacks": [],
        },
    )
    monkeypatch.setattr(
        screener_prewarm_payloads.app_config,
        "resolve_manifest_path",
        lambda market, *, require_exists=False: manifest_path
        if market == "us"
        else None,
    )

    payload = screener_prewarm_payloads.build_ohlcv_sync_payload(
        "us",
        "2026-05-13",
    )

    assert payload["markets"] == ["us"]
    assert payload["as_of_date"] == "2026-05-13"
    assert payload["top_k"] == 100
    assert payload["us_data_source"] == "massive"
    assert payload["us_manifest_path"] == str(manifest_path)


def test_prewarm_payload_service_wraps_screener_config_errors(monkeypatch):
    monkeypatch.setattr(
        screener_prewarm_payloads.app_config,
        "default_manifest_path",
        lambda market: "/data/manifest/us.csv",
    )

    def fail_prepare(*args, **kwargs):
        raise screener_prewarm_payloads.screener_preparation.ScreenerPreparationError(
            "bad config"
        )

    monkeypatch.setattr(
        screener_prewarm_payloads.screener_preparation,
        "build_screener_config_payload",
        fail_prepare,
    )

    try:
        screener_prewarm_payloads.build_screener_config_payload({"markets": ["us"]})
    except RuntimeError as exc:
        assert str(exc) == "bad config"
    else:
        raise AssertionError("expected RuntimeError")


def test_fundamental_prewarm_sync_uses_full_universe_symbols(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        screener_prewarm.data_sync_tasks,
        "resolve_universe_symbols",
        lambda payload: {"us": ["AAPL", "MSFT", "NVDA"]},
    )
    monkeypatch.setattr(
        screener_prewarm,
        "build_fundamental_sync_payload",
        lambda market, as_of_date, *, symbols: {
            "market": market,
            "source": "simfin",
            "symbols": symbols,
            "as_of_date": as_of_date,
        },
    )

    def fake_sync(payload):
        captured.update(payload)
        return {"status": "completed", "symbols_success": len(payload["symbols"])}

    monkeypatch.setattr(
        screener_prewarm.data_sync_tasks,
        "run_fundamental_sync_payload",
        fake_sync,
    )

    result = screener_prewarm.run_fundamental_prewarm_sync(
        "us",
        "2026-04-28",
        ohlcv_payload={"markets": ["us"], "as_of_date": "2026-04-28", "top_k": 100},
    )

    assert result == {"status": "completed", "symbols_success": 3}
    assert captured["symbols"] == ["AAPL", "MSFT", "NVDA"]
