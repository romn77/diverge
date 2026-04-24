from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web.backend import app_config, auth, screener_results
from web.backend.services import screeners as screener_service


def _write_legacy_run(
    runs_dir: Path,
    run_id: str,
    *,
    as_of_date: str,
    markets: list[str],
    rows: list[dict],
    filtered_count_by_reason: dict[str, int] | None = None,
    elapsed_seconds: float = 0.0,
    universe_count_by_market: dict[str, int] | None = None,
) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    headers = list(rows[0].keys()) if rows else ["symbol", "market", "global_rank", "total_score"]
    csv_lines = [",".join(headers)]
    for row in rows:
        csv_lines.append(",".join(str(row.get(header, "")) for header in headers))

    (run_dir / "candidates.csv").write_text("\n".join(csv_lines) + "\n", encoding="utf-8")
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "run_timestamp": run_id,
                "as_of_date": as_of_date,
                "config": {"markets": markets},
                "universe_count_by_market": universe_count_by_market or {market: len(rows) for market in markets},
                "candidate_count": len(rows),
                "elapsed_seconds": elapsed_seconds,
                "filtered_count_by_reason": filtered_count_by_reason or {},
                "artifact_paths": {
                    "run_meta": str(run_dir / "run_meta.json"),
                    "candidates": str(run_dir / "candidates.csv"),
                },
            }
        ),
        encoding="utf-8",
    )


class ScreenerResultReadModelTests(unittest.TestCase):
    def setUp(self):
        self.auth_env_patch = patch.dict(
            os.environ,
            {"AUTH_ENABLED": "false", "AUTH_MODE": "disabled"},
            clear=False,
        )
        self.auth_env_patch.start()
        auth.reset_runtime_state()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.runs_dir = self.root / "data" / "screener" / "runs"
        self.state_dir = self.root / "data" / "screener" / "state"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.original_results_dir = app_config.SCREENER_RESULTS_DIR
        self.original_state_dir = getattr(app_config, "SCREENER_STATE_DIR", None)

        app_config.SCREENER_RESULTS_DIR = self.runs_dir
        app_config.SCREENER_STATE_DIR = self.state_dir
        screener_results.reset_screener_result_observability()

    def tearDown(self):
        app_config.SCREENER_RESULTS_DIR = self.original_results_dir
        app_config.SCREENER_STATE_DIR = self.original_state_dir
        screener_results.reset_screener_result_observability()
        auth.reset_runtime_state()
        self.auth_env_patch.stop()
        self.temp_dir.cleanup()

    def test_workspace_read_service_uses_canonical_state_after_legacy_migration(self):
        _write_legacy_run(
            self.runs_dir,
            "20260322_214530",
            as_of_date="2026-03-22",
            markets=["us"],
            rows=[
                {"symbol": "AAPL", "market": "us", "global_rank": 1, "total_score": 0.91},
                {"symbol": "MSFT", "market": "us", "global_rank": 2, "total_score": 0.83},
            ],
        )
        _write_legacy_run(
            self.runs_dir,
            "20260323_214530",
            as_of_date="2026-03-23",
            markets=["us"],
            rows=[
                {"symbol": "MSFT", "market": "us", "global_rank": 1, "total_score": 0.95},
                {"symbol": "AAPL", "market": "us", "global_rank": 2, "total_score": 0.82},
            ],
        )
        _write_legacy_run(
            self.runs_dir,
            "20260324_214530",
            as_of_date="2026-03-24",
            markets=["us"],
            rows=[
                {"symbol": "MSFT", "market": "us", "global_rank": 2, "total_score": 0.88},
                {"symbol": "NVDA", "market": "us", "global_rank": 1, "total_score": 0.99},
            ],
            filtered_count_by_reason={"liquidity_floor": 2},
        )

        state = screener_results.migrate_legacy_screener_results()

        self.assertEqual(state.current_result.source_run_id, "20260324_214530")
        self.assertEqual(state.current_result.source_legacy_run_id, "20260324_214530")
        self.assertEqual(state.current_result.slot, screener_results.CURRENT_SNAPSHOT_SLOT)
        self.assertEqual(state.previous_result.source_run_id, "20260323_214530")
        self.assertEqual(state.previous_result.source_legacy_run_id, "20260323_214530")
        self.assertEqual(state.previous_result.slot, screener_results.PREVIOUS_SNAPSHOT_SLOT)
        self.assertEqual(state.current_result.summary["entered_symbols"], ["NVDA"])
        self.assertEqual(state.current_result.summary["exited_symbols"], ["AAPL"])
        self.assertEqual(state.current_result.summary["rank_changed_symbols"], ["MSFT"])
        self.assertEqual(state.current_result.summary["unchanged"], 0)
        self.assertEqual(state.previous_result.summary, screener_results.SUMMARY_TEMPLATE)
        self.assertEqual(state.recent_runs[0].result_hash, state.current_result.result_hash)
        self.assertEqual(state.recent_runs[0].source_legacy_run_id, "20260324_214530")
        self.assertEqual(
            screener_results.get_screener_result_observability()["migration_seed_count"],
            2,
        )

        runs = screener_service.list_screener_runs()
        self.assertEqual(
            [row["id"] for row in runs],
            ["20260324_214530", "20260323_214530", "20260322_214530"],
        )
        self.assertEqual([row["snapshot_slot"] for row in runs], ["current", "previous", None])

        detail = screener_service.get_screener_run("20260324_214530")
        self.assertEqual(detail["summary"]["entered_symbols"], ["NVDA"])
        self.assertEqual(detail["filtered_count_by_reason"]["liquidity_floor"], 2)

        rows = screener_service.get_screener_run_candidates("20260324_214530")
        self.assertEqual([row["symbol"] for row in rows], ["MSFT", "NVDA"])

        with self.assertRaises(HTTPException) as context:
            screener_service.get_screener_run("20260322_214530")
        self.assertEqual(context.exception.status_code, 404)

    def test_single_seed_migration_keeps_current_summary_empty(self):
        _write_legacy_run(
            self.runs_dir,
            "20260324_214530",
            as_of_date="2026-03-24",
            markets=["us"],
            rows=[
                {"symbol": "NVDA", "market": "us", "global_rank": 1, "total_score": 0.99},
                {"symbol": "MSFT", "market": "us", "global_rank": 2, "total_score": 0.88},
            ],
            elapsed_seconds=1.75,
            universe_count_by_market={"us": 8},
        )

        state = screener_results.migrate_legacy_screener_results()

        self.assertEqual(state.current_result.source_legacy_run_id, "20260324_214530")
        self.assertEqual(state.current_result.slot, screener_results.CURRENT_SNAPSHOT_SLOT)
        self.assertIsNone(state.previous_result)
        self.assertEqual(state.current_result.summary, screener_results.SUMMARY_TEMPLATE)
        self.assertEqual(state.recent_runs[0].duration_ms, 1750)
        self.assertEqual(state.recent_runs[0].universe_count, 8)
        self.assertEqual(
            screener_results.get_screener_result_observability()["migration_seed_count"],
            1,
        )

    def test_admin_recent_runs_deduplicates_workspace_and_owner_state(self):
        duplicate_run_id = "20260418_171313"
        workspace_state = screener_results.ScreenerResultState(
            owner_user_id=None,
            recent_runs=[
                screener_results.ScreenerRunMetadata(
                    id=duplicate_run_id,
                    generated_at=duplicate_run_id,
                    as_of_date="2026-04-17",
                    markets=["cn", "us"],
                    candidate_count=20,
                    owner_user_id=None,
                    snapshot_slot=screener_results.CURRENT_SNAPSHOT_SLOT,
                    snapshot_available=True,
                    result_hash="same-result",
                )
            ],
        )
        owner_state = screener_results.ScreenerResultState(
            owner_user_id="admin-user",
            recent_runs=[
                screener_results.ScreenerRunMetadata(
                    id=duplicate_run_id,
                    generated_at=duplicate_run_id,
                    as_of_date="2026-04-17",
                    markets=["cn", "us"],
                    candidate_count=20,
                    owner_user_id="admin-user",
                    snapshot_slot=screener_results.CURRENT_SNAPSHOT_SLOT,
                    snapshot_available=True,
                    result_hash="same-result",
                )
            ],
        )
        screener_results.save_screener_result_state(workspace_state)
        screener_results.save_screener_result_state(owner_state)

        with patch.dict(os.environ, {"AUTH_ENABLED": "true", "AUTH_MODE": "required"}, clear=False):
            admin_user = SimpleNamespace(id="admin-user", role=auth.UserRole.ADMIN.value)
            runs = screener_service.list_screener_runs(admin_user)

        self.assertEqual([run["id"] for run in runs], [duplicate_run_id])

    def test_record_screener_run_metadata_handles_no_change_then_rotation(self):
        _write_legacy_run(
            self.runs_dir,
            "20260323_214530",
            as_of_date="2026-03-23",
            markets=["us"],
            rows=[
                {"symbol": "MSFT", "market": "us", "global_rank": 1, "total_score": 0.95},
                {"symbol": "AAPL", "market": "us", "global_rank": 2, "total_score": 0.82},
            ],
        )
        _write_legacy_run(
            self.runs_dir,
            "20260324_214530",
            as_of_date="2026-03-24",
            markets=["us"],
            rows=[
                {"symbol": "MSFT", "market": "us", "global_rank": 2, "total_score": 0.88},
                {"symbol": "NVDA", "market": "us", "global_rank": 1, "total_score": 0.99},
            ],
        )
        screener_results.migrate_legacy_screener_results()
        screener_results.reset_screener_result_observability()

        task = SimpleNamespace(request_payload={"as_of_date": "2026-03-25", "markets": ["us"]}, owner_user_id=None)

        _write_legacy_run(
            self.runs_dir,
            "20260325_214530",
            as_of_date="2026-03-25",
            markets=["us"],
            rows=[
                {"symbol": "MSFT", "market": "us", "global_rank": 2, "total_score": 0.88},
                {"symbol": "NVDA", "market": "us", "global_rank": 1, "total_score": 0.99},
            ],
        )
        screener_service.record_screener_run_metadata(
            task,
            SimpleNamespace(run_dir=self.runs_dir / "20260325_214530", candidate_count=2),
        )

        state = screener_results.load_screener_result_state()
        self.assertEqual(state.current_result.source_run_id, "20260325_214530")
        self.assertEqual(state.previous_result.source_run_id, "20260323_214530")
        self.assertEqual(state.current_result.source_legacy_run_id, "20260325_214530")
        self.assertEqual(state.previous_result.source_legacy_run_id, "20260323_214530")
        self.assertEqual(state.recent_runs[0].status, "no_change")
        self.assertEqual(
            screener_results.get_screener_result_observability()["snapshot_rotation_total"],
            0,
        )

        _write_legacy_run(
            self.runs_dir,
            "20260326_214530",
            as_of_date="2026-03-26",
            markets=["us"],
            rows=[
                {"symbol": "NVDA", "market": "us", "global_rank": 1, "total_score": 1.02},
                {"symbol": "META", "market": "us", "global_rank": 2, "total_score": 0.86},
            ],
        )
        screener_service.record_screener_run_metadata(
            task,
            SimpleNamespace(run_dir=self.runs_dir / "20260326_214530", candidate_count=2),
        )

        state = screener_results.load_screener_result_state()
        self.assertEqual(state.current_result.source_run_id, "20260326_214530")
        self.assertEqual(state.previous_result.source_run_id, "20260325_214530")
        self.assertEqual(state.current_result.source_legacy_run_id, "20260326_214530")
        self.assertEqual(state.previous_result.source_legacy_run_id, "20260325_214530")
        self.assertEqual(state.recent_runs[0].status, "success")
        self.assertEqual(state.previous_result.summary, screener_results.SUMMARY_TEMPLATE)
        self.assertEqual(state.recent_runs[0].result_hash, state.current_result.result_hash)
        self.assertEqual(state.current_result.summary["entered_symbols"], ["META"])
        self.assertEqual(state.current_result.summary["exited_symbols"], ["MSFT"])
        self.assertEqual(
            screener_results.get_screener_result_observability()["snapshot_rotation_total"],
            1,
        )

    def test_result_hash_tracks_canonicalization_errors(self):
        class UnserializableValue:
            pass

        result_hash = screener_results._result_hash(
            [
                {
                    "symbol": "AAPL",
                    "market": "us",
                    "global_rank": 1,
                    "total_score": 0.91,
                    "payload": UnserializableValue(),
                }
            ]
        )

        self.assertTrue(result_hash)
        self.assertEqual(
            screener_results.get_screener_result_observability()["hash_canonicalization_error_total"],
            1,
        )

    def test_result_hash_canonicalizes_rows_before_hashing(self):
        rows_a = [
            {
                "symbol": "MSFT",
                "rank": 2,
                "score": 1.2000,
                "matched_reason_codes": ["volume", "trend", "volume"],
                "display_metrics": {
                    "beta": 2,
                    "alpha": {
                        "zeta": None,
                        "gamma": 1.20,
                    },
                },
                "optional": None,
            },
            {
                "symbol": "AAPL",
                "rank": 1,
                "score": 0.95,
                "matched_reason_codes": ["leadership"],
                "display_metrics": {"momentum": 5.0, "quality": 7},
            },
        ]
        rows_b = [
            {
                "symbol": "AAPL",
                "rank": 1.0,
                "score": 0.9500,
                "matched_reason_codes": ["leadership"],
                "display_metrics": {"quality": 7.0, "momentum": 5},
            },
            {
                "symbol": "MSFT",
                "rank": 2.0,
                "score": 1.2,
                "matched_reason_codes": ["trend", "volume"],
                "display_metrics": {
                    "alpha": {
                        "gamma": 1.2,
                    },
                    "beta": 2.0,
                },
            },
        ]

        self.assertEqual(
            screener_results.canonicalize_result_rows(rows_a),
            screener_results.canonicalize_result_rows(rows_b),
        )
        self.assertEqual(
            screener_results.result_hash(rows_a),
            screener_results.result_hash(rows_b),
        )

    def test_persist_screener_run_first_success_and_failed_metadata(self):
        first_candidate = screener_results.ScreenerResultCandidate(
            source_run_id="20260324_214530",
            generated_at="20260324_214530",
            as_of_date="2026-03-24",
            markets=["us"],
            universe_count=24,
            match_count=2,
            filtered_count_by_reason={"liquidity_floor": 3},
            artifact_paths={"candidates": "runs/20260324_214530/candidates.csv"},
            rows=[
                {"symbol": "AAPL", "market": "us", "global_rank": 1, "total_score": 0.91},
                {"symbol": "MSFT", "market": "us", "global_rank": 2, "total_score": 0.83},
            ],
            manifest_version="manifest-v1",
            logic_version="logic-v1",
            duration_ms=1234,
        )

        state = screener_results.persist_screener_run(
            SimpleNamespace(request_payload={"as_of_date": "2026-03-24", "markets": ["us"]}, owner_user_id=None),
            first_candidate,
        )

        self.assertEqual(state.current_result.source_run_id, "20260324_214530")
        self.assertIsNone(state.previous_result)
        self.assertEqual(state.recent_runs[0].status, "success")
        self.assertEqual(state.recent_runs[0].match_count, 2)
        self.assertEqual(state.recent_runs[0].duration_ms, 1234)
        self.assertTrue(state.recent_runs[0].snapshot_available)

        failed_state = screener_results.persist_screener_run(
            SimpleNamespace(request_payload={"as_of_date": "2026-03-25", "markets": ["us"]}, owner_user_id=None),
            error_summary="boom",
            source_run_id="task-failed-001",
        )

        self.assertEqual(failed_state.current_result.source_run_id, "20260324_214530")
        self.assertIsNone(failed_state.previous_result)
        self.assertEqual(failed_state.recent_runs[0].status, "failed")
        self.assertEqual(failed_state.recent_runs[0].error_summary, "boom")
        self.assertFalse(failed_state.recent_runs[0].snapshot_available)

    def test_persist_screener_run_rotates_previous_and_keeps_no_change_previous(self):
        initial_candidate = screener_results.ScreenerResultCandidate(
            source_run_id="20260324_214530",
            generated_at="20260324_214530",
            as_of_date="2026-03-24",
            markets=["us"],
            universe_count=24,
            match_count=2,
            filtered_count_by_reason={},
            artifact_paths={"candidates": "runs/20260324_214530/candidates.csv"},
            rows=[
                {"symbol": "MSFT", "market": "us", "global_rank": 2, "total_score": 0.88},
                {"symbol": "NVDA", "market": "us", "global_rank": 1, "total_score": 0.99},
            ],
            manifest_version="manifest-v1",
            logic_version="logic-v1",
            duration_ms=1000,
        )
        screener_results.persist_screener_run(
            SimpleNamespace(request_payload={"as_of_date": "2026-03-24", "markets": ["us"]}, owner_user_id=None),
            initial_candidate,
        )

        changed_state = screener_results.persist_screener_run(
            SimpleNamespace(request_payload={"as_of_date": "2026-03-25", "markets": ["us"]}, owner_user_id=None),
            screener_results.ScreenerResultCandidate(
                source_run_id="20260325_214530",
                generated_at="20260325_214530",
                as_of_date="2026-03-25",
                markets=["us"],
                universe_count=24,
                match_count=2,
                filtered_count_by_reason={},
                artifact_paths={"candidates": "runs/20260325_214530/candidates.csv"},
                rows=[
                    {"symbol": "NVDA", "market": "us", "global_rank": 1, "total_score": 1.02},
                    {"symbol": "META", "market": "us", "global_rank": 2, "total_score": 0.86},
                ],
                manifest_version="manifest-v2",
                logic_version="logic-v2",
                duration_ms=1100,
            ),
        )

        self.assertEqual(changed_state.current_result.source_run_id, "20260325_214530")
        self.assertEqual(changed_state.previous_result.source_run_id, "20260324_214530")
        self.assertEqual(changed_state.previous_result.summary, screener_results.SUMMARY_TEMPLATE)
        self.assertEqual(changed_state.current_result.summary["entered_symbols"], ["META"])
        self.assertEqual(changed_state.current_result.summary["exited_symbols"], ["MSFT"])
        self.assertEqual(changed_state.recent_runs[0].status, "success")

        no_change_state = screener_results.persist_screener_run(
            SimpleNamespace(request_payload={"as_of_date": "2026-03-26", "markets": ["us"]}, owner_user_id=None),
            screener_results.ScreenerResultCandidate(
                source_run_id="20260326_214530",
                generated_at="20260326_214530",
                as_of_date="2026-03-26",
                markets=["us"],
                universe_count=32,
                match_count=2,
                filtered_count_by_reason={},
                artifact_paths={"candidates": "runs/20260326_214530/candidates.csv"},
                rows=[
                    {"symbol": "META", "market": "us", "global_rank": 2, "total_score": 0.86},
                    {"symbol": "NVDA", "market": "us", "global_rank": 1, "total_score": 1.02},
                ],
                manifest_version="manifest-v3",
                logic_version="logic-v3",
                duration_ms=1200,
            ),
        )

        self.assertEqual(no_change_state.current_result.source_run_id, "20260326_214530")
        self.assertEqual(no_change_state.current_result.manifest_version, "manifest-v3")
        self.assertEqual(no_change_state.current_result.logic_version, "logic-v3")
        self.assertEqual(no_change_state.current_result.candidate_count, 2)
        self.assertEqual(no_change_state.previous_result.source_run_id, "20260324_214530")
        self.assertEqual(no_change_state.previous_result.summary, screener_results.SUMMARY_TEMPLATE)
        self.assertEqual(no_change_state.recent_runs[0].status, "no_change")
        self.assertEqual(
            screener_results.get_screener_result_observability()["snapshot_rotation_total"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
