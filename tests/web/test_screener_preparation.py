from __future__ import annotations

from types import SimpleNamespace

import pytest

from web.backend.services import screener_preparation


def _base_payload(market: str = "cn") -> dict:
    return {
        "markets": [market],
        "as_of_date": "2026-03-24",
        "top_k": 20,
        "history_cache_policy": "refresh_missing",
        "breakout_types": [],
        "filter_preset_selections": {"ma20_position": "price_above_ma20"},
        "ranking_profile_id": "technical_pattern_balanced",
        "include_fundamentals": False,
        "cn_fundamental_source": "tushare",
        "us_fundamental_source": "simfin",
    }


def _fixed_sources(_markets: list[str]) -> dict[str, object]:
    return {
        "cn_data_source": "tushare",
        "cn_data_source_fallbacks": [],
        "us_data_source": "massive",
        "us_data_source_fallbacks": [],
    }


def _set_runtime_dirs(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        screener_preparation.app_config,
        "SCREENER_RESULTS_DIR",
        tmp_path / "runs",
    )
    monkeypatch.setattr(
        screener_preparation.app_config,
        "SCREENER_CACHE_DIR",
        tmp_path / "cache",
    )
    monkeypatch.setattr(
        screener_preparation.app_config,
        "STOCK_HISTORY_DIR",
        tmp_path / "history",
    )
    monkeypatch.setattr(
        screener_preparation.app_config,
        "FUNDAMENTALS_DIR",
        tmp_path / "fundamentals",
    )


def test_prepare_screener_run_forces_cache_only_and_resolves_missing_as_of_date(
    tmp_path,
    monkeypatch,
):
    _set_runtime_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(
        screener_preparation.app_config,
        "resolve_manifest_path",
        lambda market, project_root=None, *, require_exists=False: None,
    )
    monkeypatch.setattr(
        screener_preparation.screener_results,
        "screener_key_for_config",
        lambda config: "screen-fixed",
    )
    monkeypatch.setattr(
        screener_preparation.screener_results,
        "get_cached_screener_result",
        lambda config: None,
    )
    raw_payload = _base_payload("cn")
    raw_payload["as_of_date"] = None

    prepared = screener_preparation.prepare_screener_run(
        raw_payload,
        data_source_resolver=_fixed_sources,
        as_of_date_resolver=lambda markets, payload: "2026-03-24",
    )

    assert raw_payload["history_cache_policy"] == "refresh_missing"
    assert prepared.request_payload["history_cache_policy"] == "cache_only"
    assert prepared.config_payload["history_cache_policy"] == "cache_only"
    assert prepared.request_payload["as_of_date"] == "2026-03-24"
    assert prepared.config_payload["as_of_date"] == "2026-03-24"
    assert prepared.request_payload["screener_key"] == "screen-fixed"
    assert prepared.screener_key == "screen-fixed"


def test_build_screener_config_payload_injects_us_manifest_without_mutating_request(
    tmp_path,
    monkeypatch,
):
    _set_runtime_dirs(monkeypatch, tmp_path)
    manifest_path = tmp_path / "us.csv"
    manifest_path.write_text("symbol\nAAPL\n", encoding="utf-8")
    monkeypatch.setattr(
        screener_preparation.app_config,
        "resolve_manifest_path",
        lambda market, project_root=None, *, require_exists=False: manifest_path
        if market == "us"
        else None,
    )
    request_payload = _base_payload("us")

    config_payload = screener_preparation.build_screener_config_payload(
        request_payload,
        data_sources=_fixed_sources(["us"]),
    )

    assert "us_manifest_path" not in request_payload
    assert config_payload["us_manifest_path"] == str(manifest_path)
    assert config_payload["output_dir"] == str(tmp_path / "runs")
    assert config_payload["cache_dir"] == str(tmp_path / "cache")
    assert config_payload["history_dir"] == str(tmp_path / "history")
    assert config_payload["fundamental_dir"] == str(tmp_path / "fundamentals")


def test_build_screener_config_payload_rejects_us_without_manifest(
    tmp_path,
    monkeypatch,
):
    _set_runtime_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(
        screener_preparation.app_config,
        "resolve_manifest_path",
        lambda market, project_root=None, *, require_exists=False: None,
    )

    with pytest.raises(
        screener_preparation.ScreenerPreparationError,
        match="custom manifest error",
    ):
        screener_preparation.build_screener_config_payload(
            _base_payload("us"),
            data_sources=_fixed_sources(["us"]),
            us_manifest_error="custom manifest error",
        )


def test_prepare_screener_run_reports_cached_snapshot(tmp_path, monkeypatch):
    _set_runtime_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(
        screener_preparation.app_config,
        "resolve_manifest_path",
        lambda market, project_root=None, *, require_exists=False: None,
    )
    monkeypatch.setattr(
        screener_preparation.screener_results,
        "screener_key_for_config",
        lambda config: "screen-cached",
    )
    monkeypatch.setattr(
        screener_preparation.screener_results,
        "get_cached_screener_result",
        lambda config: SimpleNamespace(source_run_id="cached-run-001"),
    )

    prepared = screener_preparation.prepare_screener_run(
        _base_payload("cn"),
        data_source_resolver=_fixed_sources,
    )

    assert prepared.cached
    assert prepared.cached_run_id == "cached-run-001"
    assert prepared.request_payload["screener_key"] == "screen-cached"
