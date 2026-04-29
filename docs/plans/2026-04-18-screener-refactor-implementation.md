# Screener Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce screener orchestration redundancy by making debug reuse shared stage helpers, removing unused history failure cache runtime state, shrinking checkpoint payload to fields that actually drive recovery, and centralizing CLI screener config construction.

**Architecture:** Extract the common screener stages into shared helpers that separate "load and prefilter universe" from "evaluate histories/features/filters/ranking". `run_screen()` will execute those helpers for the full universe, while `debug_screen_symbol()` will reuse the same helpers on a narrowed target subset so it no longer maintains its own stage order. After that, remove failure-cache file I/O that no longer affects runtime decisions, simplify checkpoint state to a small negative-recovery snapshot, and fold duplicated CLI config parsing into one helper.

**Tech Stack:** Python 3.12, Typer CLI, pandas, pytest

---

### Task 1: Extract shared screener stage helpers and move debug onto them

**Files:**
- Create: `diverge/screener/stages.py`
- Modify: `diverge/screener/pipeline.py`
- Modify: `diverge/screener/debug.py`
- Test: `tests/screener/test_pipeline.py`
- Test: `tests/screener/test_debug.py`

**Step 1: Write the failing tests**

Add one pipeline-oriented test and one debug-oriented test that lock the new shared helper contract.

Example test shapes:

```python
def test_run_screen_uses_shared_stage_helpers(tmp_path):
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-03-24", top_k=20, us_manifest_path="/tmp/us.csv")
    stage_bundle = ScreenStageBundle(
        universe_df=pd.DataFrame([{"symbol": "AAPL", "market": "us"}]),
        prefiltered_df=pd.DataFrame([{"symbol": "AAPL", "market": "us"}]),
        prefiltered_out_df=pd.DataFrame(columns=["symbol", "market", "drop_reason"]),
        histories={"AAPL": _price_frame("2026-03-24")},
        fetch_failures=pd.DataFrame(columns=["symbol", "market", "drop_reason"]),
        features_df=pd.DataFrame([{"symbol": "AAPL", "market": "us", "total_score": 0.71}]),
        kept_df=pd.DataFrame([{"symbol": "AAPL", "market": "us", "total_score": 0.71}]),
        dropped_df=pd.DataFrame(columns=["symbol", "market", "drop_reason"]),
        ranked_df=pd.DataFrame([{"symbol": "AAPL", "market": "us", "global_rank": 1, "total_score": 0.71}]),
    )

    with patch("diverge.screener.pipeline.run_screen_stages", return_value=stage_bundle):
        result = run_screen(config)

    assert result.candidate_count == 1
```

```python
def test_debug_screen_symbol_uses_shared_stage_helpers_for_target_symbol():
    config = ScreenRunConfig(markets=["us"], as_of_date="2026-03-24", top_k=20, us_manifest_path="/tmp/us.csv")
    prefilter_bundle = UniverseStageBundle(
        universe_df=pd.DataFrame([{"symbol": "AAPL", "market": "us"}]),
        prefiltered_df=pd.DataFrame([{"symbol": "AAPL", "market": "us"}]),
        prefiltered_out_df=pd.DataFrame(columns=["symbol", "market", "drop_reason"]),
    )
    eval_bundle = EvaluationStageBundle(
        histories={"AAPL": _price_frame("2026-03-24")},
        fetch_failures=pd.DataFrame(columns=["symbol", "market", "drop_reason"]),
        features_df=pd.DataFrame([{"symbol": "AAPL", "market": "us"}]),
        kept_df=pd.DataFrame([{"symbol": "AAPL", "market": "us"}]),
        dropped_df=pd.DataFrame(columns=["symbol", "market", "drop_reason"]),
        ranked_df=pd.DataFrame([{"symbol": "AAPL", "market": "us", "global_rank": 1}]),
    )

    with (
        patch("diverge.screener.debug.prepare_universe_stage", return_value=prefilter_bundle),
        patch("diverge.screener.debug.evaluate_screen_stage", return_value=eval_bundle),
    ):
        result = debug_screen_symbol(config, symbol="AAPL", market="us")

    assert result.score_row["global_rank"] == 1
```

**Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest -q tests/screener/test_pipeline.py tests/screener/test_debug.py
```

Expected:
- FAIL because `ScreenStageBundle` / `UniverseStageBundle` / `EvaluationStageBundle` and the new helper functions do not exist yet.

**Step 3: Write the minimal implementation**

Create `diverge/screener/stages.py` with shared dataclasses and helpers:

```python
@dataclass(slots=True)
class UniverseStageBundle:
    universe_df: pd.DataFrame
    prefiltered_df: pd.DataFrame
    prefiltered_out_df: pd.DataFrame


@dataclass(slots=True)
class EvaluationStageBundle:
    histories: dict[str, pd.DataFrame]
    fetch_failures: pd.DataFrame
    features_df: pd.DataFrame
    kept_df: pd.DataFrame
    dropped_df: pd.DataFrame
    ranked_df: pd.DataFrame


def prepare_universe_stage(config: ScreenRunConfig, cache_root: Path) -> UniverseStageBundle:
    ...


def evaluate_screen_stage(
    config: ScreenRunConfig,
    *,
    source_universe_df: pd.DataFrame,
    fetch_universe_df: pd.DataFrame,
    cache_root: Path,
    progress_callback: Callable[..., None] | None = None,
) -> EvaluationStageBundle:
    ...
```

Refactor:
- `diverge/screener/pipeline.py` to call the shared helpers and only keep candidate selection + export orchestration.
- `diverge/screener/debug.py` to call the same helpers, then select the target symbol from the returned stage bundles instead of maintaining an independent stage sequence.
- Remove the pure forwarder helpers at the top of `debug.py` if the new shared helpers make them unnecessary.

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest -q tests/screener/test_pipeline.py tests/screener/test_debug.py
```

Expected:
- PASS for both files.

**Step 5: Commit**

```bash
git add diverge/screener/stages.py diverge/screener/pipeline.py diverge/screener/debug.py tests/screener/test_pipeline.py tests/screener/test_debug.py
git commit -m "refactor: share screener stage orchestration"
```

### Task 2: Remove history failure cache from runtime and filesystem writes

**Files:**
- Modify: `diverge/screener/history_cache.py`
- Modify: `diverge/screener/market_data.py`
- Test: `tests/screener/test_market_data.py`

**Step 1: Write the failing tests**

Add or update tests so reruns retry fetches without reading or depending on `history_failures` files, and so no failure-cache files are written during fetch errors.

Example test shape:

```python
def test_fetch_history_for_universe_does_not_write_history_failure_cache_files(tmp_path):
    universe = pd.DataFrame([{"symbol": "AAPL", "market": "us", "name": "Apple", "exchange": "NASDAQ", "sector": "", "list_date": ""}])

    with patch(
        "diverge.screener.market_data.fetch_price_history",
        side_effect=VendorRetryableError("boom"),
    ):
        histories, failures = fetch_history_for_universe(
            universe,
            "2026-03-24",
            cache_dir=tmp_path / "cache",
            checkpoint_dir=tmp_path / "checkpoints",
        )

    assert histories == {}
    assert failures.to_dict("records") == [{"symbol": "AAPL", "market": "us", "drop_reason": "fetch_failed"}]
    assert not list((tmp_path / "cache").rglob("history_failures/*.json"))
```

**Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest -q tests/screener/test_market_data.py -k "history_failure or retries_refetch_on_rerun"
```

Expected:
- FAIL because the code still writes history failure cache files and the helper functions still exist.

**Step 3: Write the minimal implementation**

Delete the runtime failure-cache subsystem:
- Remove `HISTORY_FAILURE_CACHE_DIRNAME`.
- Remove `history_failure_cache_path`, `load_history_failure_cache`, `save_history_failure_cache`, and `delete_history_failure_cache`.
- Remove all call sites in `diverge/screener/market_data.py`.
- Keep failure outcomes only in the in-memory `failures` rows and exported `filtered_out.csv`.

Minimal target shape:

```python
except VendorDataEmptyError:
    failures.append({"symbol": symbol, "market": market, "drop_reason": "history_empty"})
    history_status = "history_empty"
```

```python
except VendorRetryableError:
    failures.append({"symbol": symbol, "market": market, "drop_reason": "fetch_failed"})
    history_status = "fetch_failed"
```

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest -q tests/screener/test_market_data.py
```

Expected:
- PASS with no references to `history_failures`.

**Step 5: Commit**

```bash
git add diverge/screener/history_cache.py diverge/screener/market_data.py tests/screener/test_market_data.py
git commit -m "refactor: remove unused history failure cache"
```

### Task 3: Shrink checkpoint payload to recovery-driving fields only

**Files:**
- Modify: `diverge/screener/history_cache.py`
- Modify: `diverge/screener/market_data.py`
- Test: `tests/screener/test_market_data.py`

**Step 1: Write the failing tests**

Replace checkpoint-payload assertions that still require `processed_symbols`, `fetch_failed_symbols`, `universe_total`, or `last_symbol`. Add one explicit payload-shape test.

Example test shape:

```python
def test_save_checkpoint_persists_only_recovery_fields(tmp_path):
    path = tmp_path / "history.json"

    save_checkpoint(
        path,
        start_date="2025-02-17",
        failed_symbols=[{"symbol": "AAPL", "market": "us", "drop_reason": "fetch_failed"}],
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert sorted(payload.keys()) == ["failed_symbols", "start_date", "updated_at"]
```

**Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest -q tests/screener/test_market_data.py -k "checkpoint"
```

Expected:
- FAIL because current checkpoint payload still includes extra compatibility fields.

**Step 3: Write the minimal implementation**

Simplify checkpoint persistence to a compact state object:

```python
def save_checkpoint(path: str | Path, *, start_date: str, failed_symbols: list[dict]) -> None:
    payload = {
        "start_date": start_date,
        "failed_symbols": failed_symbols,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
```

In `market_data.py`:
- Stop building `processed_symbols`.
- Stop writing `fetch_failed_symbols`, `universe_total`, and `last_symbol`.
- Keep `failed_symbols` only for rows that will actually drive `skip_checkpoint_failure`.
- If there are no failed symbols at interrupt time, decide whether to skip writing the checkpoint file entirely; prefer no file if it carries no recovery value.

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest -q tests/screener/test_market_data.py
```

Expected:
- PASS with checkpoint tests asserting the smaller payload.

**Step 5: Commit**

```bash
git add diverge/screener/history_cache.py diverge/screener/market_data.py tests/screener/test_market_data.py
git commit -m "refactor: simplify screener checkpoint state"
```

### Task 4: Extract shared CLI helper for screener config construction

**Files:**
- Modify: `cli/main.py`
- Test: `tests/cli/test_screen_command.py`

**Step 1: Write the failing tests**

Add tests that call the shared helper directly, and update command tests so `screen` and `screen-debug` assertions rely on one config-building code path.

Example test shape:

```python
def test_build_screener_config_normalizes_common_options():
    config, note = _build_screener_config(
        date=None,
        markets=["us"],
        top_k=7,
        cn_data_source="tushare",
        cn_data_source_fallbacks="akshare",
        us_data_source="massive",
        cn_manifest=None,
        us_manifest="/tmp/us.csv",
        output_dir="/tmp/out",
    )

    assert config.markets == ["us"]
    assert config.top_k == 7
    assert config.cn_data_source_fallbacks == ["akshare"]
```

**Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest -q tests/cli/test_screen_command.py
```

Expected:
- FAIL because `_build_screener_config` does not exist yet and `screen` / `screen-debug` still duplicate parsing.

**Step 3: Write the minimal implementation**

Extract one helper in `cli/main.py`:

```python
def _build_screener_config(
    *,
    date: str | None,
    markets: list[str],
    top_k: int,
    cn_data_source: str,
    cn_data_source_fallbacks: str,
    us_data_source: str,
    cn_manifest: str | None,
    us_manifest: str | None,
    output_dir: str,
) -> tuple[ScreenRunConfig, str | None]:
    ...
```

Then update both `screen()` and `screen_debug()` to:
- normalize market list
- call the helper
- print the returned date-resolution note

Keep command-specific concerns outside the helper:
- `screen()` still owns progress rendering and candidate summary
- `screen_debug()` still owns symbol/market arguments and debug report printing

**Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest -q tests/cli/test_screen_command.py
python3 -m json.tool .vscode/launch.json
```

Expected:
- `tests/cli/test_screen_command.py`: PASS
- `launch.json` formatting check: PASS

**Step 5: Commit**

```bash
git add cli/main.py tests/cli/test_screen_command.py
git commit -m "refactor: centralize screener cli config building"
```

### Final Verification

**Files:**
- Verify only the files above changed for this refactor series.

**Step 1: Run the focused screener test suite**

Run:

```bash
python3 -m pytest -q tests/screener tests/cli/test_screen_command.py
```

Expected:
- PASS for all screener and CLI tests.

**Step 2: Run git diff sanity check**

Run:

```bash
git diff -- diverge/screener cli/main.py tests/screener tests/cli/test_screen_command.py
```

Expected:
- Only the intended refactor files appear.

**Step 3: Summarize risks before merging**

Check manually:
- Debug output still reports the same stage-level information.
- Full `screen` still emits progress lines and exports the same artifact files.
- Interrupted runs still recover via history cache, and failed-symbol checkpoint behavior remains intentional.

**Step 4: Optional final commit**

If the work was split across the task commits above, no extra commit is needed. If not, use:

```bash
git add diverge/screener cli/main.py tests/screener tests/cli/test_screen_command.py
git commit -m "refactor: streamline screener orchestration and recovery state"
```
