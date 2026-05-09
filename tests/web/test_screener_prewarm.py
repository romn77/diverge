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


def test_due_market_trading_day_waits_until_market_close():
    before_close = datetime(2026, 4, 28, 6, 59, tzinfo=timezone.utc)
    after_close = datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc)

    assert screener_prewarm.due_market_trading_day("cn", before_close) is None
    assert screener_prewarm.due_market_trading_day("cn", after_close) == "2026-04-28"


def test_due_prewarm_syncs_history_before_enqueuing_screener(tmp_path, monkeypatch):
    calls = []

    monkeypatch.setattr(app_config, "SCREENER_STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(
        screener_prewarm,
        "build_ohlcv_sync_payload",
        lambda market, as_of_date: {"markets": [market], "as_of_date": as_of_date},
    )

    def fake_sync(payload):
        calls.append(("sync", payload["markets"][0], payload["as_of_date"]))
        return {"status": "completed", "symbols_success": 10}

    def fake_enqueue(market, as_of_date):
        calls.append(("screener", market, as_of_date))
        return 2

    def fake_fundamental(market, as_of_date, *, ohlcv_payload):
        calls.append(("fundamentals", market, as_of_date))
        return {"status": "completed", "symbols_success": 8}

    monkeypatch.setattr(
        screener_prewarm.data_sync_tasks,
        "run_ohlcv_sync_payload",
        fake_sync,
    )
    monkeypatch.setattr(
        screener_prewarm,
        "run_fundamental_prewarm_sync",
        fake_fundamental,
    )
    monkeypatch.setattr(
        screener_prewarm,
        "enqueue_screener_prewarm_tasks",
        fake_enqueue,
    )

    result = screener_prewarm.run_market_prewarm_workflow("cn", "2026-04-28")

    assert result["screener_tasks_enqueued"] == {"cn": 2}
    assert calls == [
        ("sync", "cn", "2026-04-28"),
        ("fundamentals", "cn", "2026-04-28"),
        ("screener", "cn", "2026-04-28"),
    ]


def test_due_prewarm_syncs_fundamentals_when_presets_require_them(
    tmp_path, monkeypatch
):
    calls = []

    monkeypatch.setattr(app_config, "SCREENER_STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(
        screener_prewarm,
        "build_ohlcv_sync_payload",
        lambda market, as_of_date: {"markets": [market], "as_of_date": as_of_date},
    )
    monkeypatch.setattr(
        screener_prewarm,
        "collect_screener_prewarm_payloads",
        lambda market, as_of_date: [
            {
                "markets": [market],
                "as_of_date": as_of_date,
                "include_fundamentals": True,
                "filter_preset_selections": {},
            }
        ],
    )

    def fake_sync(payload):
        calls.append(("sync", payload["markets"][0], payload["as_of_date"]))
        return {"status": "completed", "symbols_success": 10}

    def fake_fundamental(market, as_of_date, *, ohlcv_payload):
        calls.append(("fundamentals", market, as_of_date))
        return {"status": "completed", "symbols_success": 8}

    def fake_enqueue(market, as_of_date):
        calls.append(("screener", market, as_of_date))
        return 2

    monkeypatch.setattr(
        screener_prewarm.data_sync_tasks,
        "run_ohlcv_sync_payload",
        fake_sync,
    )
    monkeypatch.setattr(
        screener_prewarm,
        "run_fundamental_prewarm_sync",
        fake_fundamental,
    )
    monkeypatch.setattr(
        screener_prewarm,
        "enqueue_screener_prewarm_tasks",
        fake_enqueue,
    )

    result = screener_prewarm.run_market_prewarm_workflow("cn", "2026-04-28")

    assert result["screener_tasks_enqueued"] == {"cn": 2}
    assert calls == [
        ("sync", "cn", "2026-04-28"),
        ("fundamentals", "cn", "2026-04-28"),
        ("screener", "cn", "2026-04-28"),
    ]


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


def test_due_prewarm_enqueues_data_sync_workflow(tmp_path, monkeypatch):
    created = []

    monkeypatch.setattr(app_config, "SCREENER_STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(screener_prewarm, "_enabled_markets", lambda: ["cn"])
    monkeypatch.setattr(
        screener_prewarm,
        "due_market_trading_day",
        lambda market, now_utc=None: "2026-04-28",
    )
    monkeypatch.setattr(
        screener_prewarm,
        "build_ohlcv_sync_payload",
        lambda market, as_of_date: {"markets": [market], "as_of_date": as_of_date},
    )

    def fake_create(**kwargs):
        created.append(kwargs)
        return {"task_id": "sync-1", "status": "queued"}

    monkeypatch.setattr(
        screener_prewarm.data_sync_tasks,
        "create_data_sync_task",
        fake_create,
    )

    result = screener_prewarm.run_due_screener_prewarm_once()

    assert result == {"cn": 1}
    assert created == [
        {
            "sync_type": "ohlcv",
            "request_payload": {
                "markets": ["cn"],
                "as_of_date": "2026-04-28",
                "run_screener_prewarm": True,
            },
            "owner_user_id": None,
            "tenant_id": None,
        }
    ]
