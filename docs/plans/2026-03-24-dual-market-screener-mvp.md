# Dual-Market Screener MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a dual-market daily screener MVP that generates a ranked candidate pool for CN and US stocks without invoking LLM analysis.

**Architecture:** Add a new `tradingagents.screener` subsystem that reads a market universe, fetches DataFrame-level OHLCV data through internal vendor helpers, computes daily indicators and derived factors, applies hard filters, ranks survivors within each market, and writes standardized artifacts for downstream human review or LLM research selection. Keep the existing `analyze` workflow unchanged; expose the screener only through a new CLI command and file outputs under `results/screener/`. The implementation must normalize vendor unit differences, use sequential rate-limited Tushare fetching with retry/backoff, and surface progress updates while long-running fetches are in flight.

**Tech Stack:** Python 3.10+, pandas, stockstats, typer, existing `tushare` / `yfinance` internal helpers, pytest/unittest.

---

## Locked Decisions

- The output plan file lives in `docs/plans/2026-03-24-dual-market-screener-mvp.md`.
- Market scope is dual-market (`cn` + `us`) from day one.
- Delivery surface for MVP is backend library + CLI + Web list view.
- Persistence is file-snapshot based; no DB for MVP.
- MVP does not run LLMs; Web only launches background screener tasks and renders screener run results.
- MVP does not include backtesting.
- CN universe source is Tushare `stock_basic`.
- US universe source is a CSV manifest file:
  - CLI path: user-supplied `--us-manifest`
  - Web path: backend-configured `SCREEN_US_MANIFEST_PATH`
- Ranking uses technical and liquidity factors only; fundamentals are out of scope for MVP ranking.
- Tushare `amount` must be normalized from `千元` to `元` immediately after fetch so CN thresholds remain readable in yuan.
- CN history fetches must be sequential and rate-limited; free-tier Tushare limits are a first-class constraint.
- Web analysis tasks and screener tasks share one global background queue limit of 2 active tasks total.

## Public Interfaces And Artifacts

- New Python entrypoint: `tradingagents.screener.pipeline.run_screen(config: ScreenRunConfig, progress_callback: Callable | None = None) -> ScreenRunResult`
- New CLI command: `tradingagents screen --date YYYY-MM-DD --markets cn,us --top-k 100 --limit-per-market 500 --us-manifest /abs/path.csv --output-dir ./results/screener`
- New web endpoints:
  - `GET /api/screener/config/options`
  - `POST /api/screener/tasks`
  - `GET /api/screener/tasks`
  - `GET /api/screener/tasks/{task_id}`
  - `GET /api/screener/tasks/{task_id}/stream`
  - `GET /api/screener/runs`
  - `GET /api/screener/runs/{run_id}`
  - `GET /api/screener/runs/{run_id}/candidates`
- New artifact directory per run: `results/screener/<YYYYMMDD_HHMMSS>/`
- Required output files:
  - `run_meta.json`
  - `universe.csv`
  - `features.csv`
  - `filtered_out.csv`
  - `candidates.csv`
  - `llm_pool.json`
- `llm_pool.json` is the only downstream handoff file for later agent/LLM research. The screener itself must never call any LLM or graph workflow.

### `run_meta.json`

`run_meta.json` must contain this fixed schema:

- `run_timestamp`
- `as_of_date`
- `config`
- `universe_count_by_market`
- `fetch_failed_count`
- `filtered_count_by_reason`
- `candidate_count`
- `elapsed_seconds`
- `artifact_paths`

`artifact_paths` must be an object with keys:

- `run_meta`
- `universe`
- `features`
- `filtered_out`
- `candidates`
- `llm_pool`

## Data Contracts

### `ScreenRunConfig`

Implement as a dataclass in `tradingagents/screener/schema.py` with these fields and defaults:

- `markets: list[str]`
- `as_of_date: str`
- `top_k: int`
- `limit_per_market: int | None = None`
- `min_listing_days: int = 180`
- `cn_min_avg_amount_20d: float = 50_000_000`
- `us_min_avg_dollar_volume_20d: float = 10_000_000`
- `output_dir: str = "./results/screener"`
- `us_manifest_path: str | None = None`

Validation rules:

- `markets` values must be subset of `{"cn", "us"}` with no duplicates.
- `as_of_date` must use `YYYY-MM-DD` and cannot be in the future.
- `top_k` must be positive.
- `limit_per_market` must be positive when provided.
- `us_manifest_path` is required whenever `"us"` is in `markets`.
- `cn_min_avg_amount_20d` is expressed in yuan after Tushare amount normalization, not in Tushare's source `千元` unit.

### `ScreenTaskCreatePayload`

Implement as a Pydantic model in `web/backend/main.py` with these fields:

- `markets: list[str]`
- `as_of_date: str`
- `top_k: int`
- `limit_per_market: int | None = None`

Rules:

- Web requests must not accept a raw `us_manifest_path` from the browser.
- If `"us"` is requested, backend resolves `us_manifest_path` from `SCREEN_US_MANIFEST_PATH`.
- If `"us"` is requested and `SCREEN_US_MANIFEST_PATH` is unset, reject the request with HTTP 400 and a clear error.

### `ScreenerTask`

Implement as a backend dataclass parallel to `Task`, with fields:

- `id`
- `request_payload`
- `status`
- `latest_progress`
- `progress_events`
- `run_id`
- `error`

Status values are `pending`, `running`, `completed`, `failed`.

### `ScreenerRunSummary`

`GET /api/screener/runs` must return rows with:

- `id`
- `as_of_date`
- `markets`
- `candidate_count`
- `generated_at`

### `ScreenerRunDetail`

`GET /api/screener/runs/{run_id}` must return:

- `id`
- `as_of_date`
- `markets`
- `candidate_count`
- `generated_at`
- `filtered_count_by_reason`
- `artifact_paths`

### Universe row shape

Normalize both markets into a shared DataFrame with these columns:

- `symbol`
- `market`
- `name`
- `exchange`
- `sector`
- `list_date`

Rules:

- `market` is exactly `cn` or `us`.
- `symbol` stays in vendor-ready form for downstream fetchers:
  - CN uses Tushare symbol form like `600519.SH`.
  - US uses plain ticker like `AAPL`.
- `sector` and `list_date` may be blank for US manifest rows.

### Features row shape

Each row in `features.csv` must contain:

- Identity: `symbol`, `market`, `name`, `exchange`, `sector`, `list_date`, `as_of_date`
- Price/liquidity: `close`, `volume`, `amount`, `avg_amount_20d`
- Rolling fields: `ma20`, `ma60`, `ret_20`, `ret_60`
- Technical indicators: `rsi`, `macd`, `macds`, `macdh`, `atr`, `atr_pct`, `boll`, `boll_ub`, `boll_lb`, `vwma`, `mfi`
- Status fields: `data_start_date`, `data_end_date`, `bar_count`

Field semantics:

- `amount` and `avg_amount_20d` are always expressed in the source market's base currency unit:
  - CN: yuan
  - US: dollars
- CN Tushare `amount` must be multiplied by `1000` during normalization because the vendor returns `千元`.

### Candidate row shape

Each row in `candidates.csv` and each object in `llm_pool.json` must contain:

- `symbol`
- `market`
- `name`
- `exchange`
- `sector`
- `global_rank`
- `market_rank`
- `total_score`
- `trend_score`
- `momentum_score`
- `risk_score`
- `liquidity_score`
- `strategy_tags`
- `risk_flags`
- `close`
- `ma20`
- `ma60`
- `ret_20`
- `ret_60`
- `rsi`
- `macdh`
- `atr_pct`

## Implementation Tasks

### Task 1: Create screener package scaffolding and config schema

**Files:**
- Create: `tradingagents/screener/__init__.py`
- Create: `tradingagents/screener/schema.py`
- Create: `tests/screener/__init__.py`
- Test: `tests/screener/test_schema.py`

**Step 1: Write the failing test**

Add tests for:

- valid dual-market config
- invalid future date
- invalid market value
- missing `us_manifest_path` when `"us"` is requested

**Step 2: Run test to verify it fails**

Run: `pytest tests/screener/test_schema.py -q`
Expected: FAIL because `tradingagents.screener.schema` does not exist yet.

**Step 3: Write minimal implementation**

Implement:

- `ScreenRunConfig`
- `ScreenRunResult`
- validation helpers used later by CLI and pipeline

Keep `ScreenRunResult` simple:

- `run_dir: Path`
- `universe_count_by_market: dict[str, int]`
- `fetch_failed_count: int`
- `filtered_count_by_reason: dict[str, int]`
- `candidate_count: int`
- `candidate_preview: list[dict]`

`candidate_preview` must always contain at most 10 rows with fields `symbol`, `market`, `global_rank`, `total_score`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/screener/test_schema.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tradingagents/screener/__init__.py tradingagents/screener/schema.py tests/screener/__init__.py tests/screener/test_schema.py
git commit -m "feat(screener): add screener config schema"
```

### Task 2: Implement universe loading for CN and US

**Files:**
- Create: `tradingagents/screener/universe.py`
- Test: `tests/screener/test_universe.py`
- Reference: `tradingagents/dataflows/tushare_fundamentals.py`
- Reference: `tradingagents/dataflows/tushare_common.py`

**Step 1: Write the failing test**

Add tests for:

- CN universe loading maps `stock_basic` rows to the shared universe shape
- US manifest loading validates required columns `symbol,name,exchange,sector,list_date`
- blank optional US fields are allowed
- requesting CN universe without `TUSHARE_TOKEN` surfaces a clear auth error

Use mocks for Tushare client calls; do not hit the network.

**Step 2: Run test to verify it fails**

Run: `pytest tests/screener/test_universe.py -q`
Expected: FAIL because `load_cn_universe()` / `load_us_universe()` do not exist.

**Step 3: Write minimal implementation**

Implement in `universe.py`:

- `load_cn_universe(limit: int | None = None) -> pd.DataFrame`
- `load_us_universe(manifest_path: str, limit: int | None = None) -> pd.DataFrame`
- `load_universe(config: ScreenRunConfig) -> pd.DataFrame`

Rules:

- CN must call `pro.stock_basic(exchange="", list_status="L", fields="ts_code,name,exchange,industry,list_date")`.
- CN output columns map to the shared shape with `market="cn"` and `sector=industry`.
- US manifest must be read from CSV only in MVP.
- Apply `limit_per_market` per source before concatenation.

**Step 4: Run test to verify it passes**

Run: `pytest tests/screener/test_universe.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tradingagents/screener/universe.py tests/screener/test_universe.py
git commit -m "feat(screener): add dual-market universe loaders"
```

### Task 3: Add DataFrame-level market data adapters

**Files:**
- Create: `tradingagents/screener/market_data.py`
- Test: `tests/screener/test_market_data.py`
- Reference: `tradingagents/dataflows/tushare_stock.py`
- Reference: `tradingagents/dataflows/y_finance.py`
- Reference: `tradingagents/dataflows/vendor_errors.py`

**Step 1: Write the failing test**

Add tests for:

- CN path calls `_fetch_tushare_stock_df`
- US path calls `_fetch_yfinance_ohlcv_df`
- empty DataFrame result is recorded as fetch failure
- Tushare `Amount` is multiplied by `1000`
- CN fetch path rate-limits requests between symbols
- `VendorRetryableError` retries with exponential backoff before the symbol is marked as failed
- returned DataFrame is normalized to columns `Date/Open/High/Low/Close/Volume/Amount`

**Step 2: Run test to verify it fails**

Run: `pytest tests/screener/test_market_data.py -q`
Expected: FAIL because `fetch_price_history()` does not exist.

**Step 3: Write minimal implementation**

Implement:

- `fetch_price_history(symbol: str, market: str, start_date: str, end_date: str) -> pd.DataFrame`
- `fetch_history_for_universe(universe_df: pd.DataFrame, as_of_date: str, progress_callback: Callable | None = None) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]`

Rules:

- CN uses `_fetch_tushare_stock_df`.
- US uses `_fetch_yfinance_ohlcv_df(..., use_cache=True, auto_adjust=False)`.
- Compute `start_date` as 400 calendar days before `as_of_date` to guarantee enough bars for 60-day windows and filtering.
- For CN, multiply `Amount` by `1000` immediately after fetch to normalize from Tushare `千元` to yuan.
- For US, if `Amount` is missing, compute `Close * Volume`.
- Use sequential fetching for CN with a base pause of `0.35s` between Tushare calls.
- On `VendorRetryableError`, retry up to 3 times with exponential backoff `0.5s`, `1.0s`, `2.0s`.
- If a symbol still fails after retries, record it in the returned failures DataFrame with `drop_reason="fetch_failed"` and continue.
- Invoke `progress_callback(stage, current, total, symbol)` after each symbol when a callback is provided.
- Do not use public tool wrappers that return formatted strings.

**Step 4: Run test to verify it passes**

Run: `pytest tests/screener/test_market_data.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tradingagents/screener/market_data.py tests/screener/test_market_data.py
git commit -m "feat(screener): add dataframe-level market data adapters"
```

### Task 4: Compute derived features and technical indicators

**Files:**
- Create: `tradingagents/screener/indicators.py`
- Test: `tests/screener/test_indicators.py`
- Reference: `tradingagents/dataflows/cn_market_utils.py`
- Reference: `tradingagents/dataflows/stockstats_utils.py`

**Step 1: Write the failing test**

Add tests for:

- all required feature columns are present
- `avg_amount_20d`, `ma20`, `ma60`, `ret_20`, `ret_60`, and `atr_pct` use the expected formulas
- indicator rows are taken from the latest available trading row on or before `as_of_date`
- too-short history marks the row insufficient instead of producing fake zeros

Use a deterministic OHLCV fixture DataFrame; do not depend on vendor calls.

**Step 2: Run test to verify it fails**

Run: `pytest tests/screener/test_indicators.py -q`
Expected: FAIL because `build_feature_row()` / `build_features_table()` do not exist.

**Step 3: Write minimal implementation**

Implement:

- `build_feature_row(meta_row: pd.Series, price_df: pd.DataFrame, as_of_date: str) -> dict`
- `build_features_table(universe_df: pd.DataFrame, histories: dict[str, pd.DataFrame], as_of_date: str) -> pd.DataFrame`

Rules:

- Use pandas for `ma20`, `ma60`, `ret_20`, `ret_60`, `avg_amount_20d`, and `bar_count`.
- Use `stockstats.wrap()` for `rsi`, `macd`, `macds`, `macdh`, `atr`, `boll`, `boll_ub`, `boll_lb`, `vwma`, `mfi`.
- `atr_pct = atr / close`.
- If no valid trading row exists on or before `as_of_date`, record the row as insufficient and leave factor columns blank.

**Step 4: Run test to verify it passes**

Run: `pytest tests/screener/test_indicators.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tradingagents/screener/indicators.py tests/screener/test_indicators.py
git commit -m "feat(screener): add feature and indicator computation"
```

### Task 5: Apply hard filters and compute scores

**Files:**
- Create: `tradingagents/screener/filters.py`
- Create: `tradingagents/screener/ranker.py`
- Test: `tests/screener/test_filters.py`
- Test: `tests/screener/test_ranker.py`

**Step 1: Write the failing tests**

Add filter tests for:

- bar count lower than 60
- listing age below 180 days when `list_date` exists
- missing required indicator fields
- CN liquidity threshold
- US dollar-volume threshold
- `fetch_failed` rows are preserved into `filtered_out.csv`

Add ranking tests for:

- per-market z-score standardization
- weight application `trend 0.35`, `momentum 0.30`, `risk 0.20`, `liquidity 0.15`
- global rank is assigned after market-level scoring
- `strategy_tags` and `risk_flags` are derived from numeric thresholds

**Step 2: Run tests to verify they fail**

Run: `pytest tests/screener/test_filters.py tests/screener/test_ranker.py -q`
Expected: FAIL because filter and ranker modules do not exist yet.

**Step 3: Write minimal implementation**

Implement filters:

- `apply_hard_filters(features_df: pd.DataFrame, config: ScreenRunConfig) -> tuple[pd.DataFrame, pd.DataFrame]`

Required drop reasons:

- `fetch_failed`
- `insufficient_bars`
- `too_new`
- `missing_features`
- `illiquid_cn`
- `illiquid_us`

Implement ranking:

- `score_candidates(filtered_df: pd.DataFrame) -> pd.DataFrame`

Fixed formulas:

- `trend_score` from normalized `close/ma20 - 1` and `close/ma60 - 1`
- `momentum_score` from normalized `ret_20`, `ret_60`, `macdh`, and centered `rsi`
- `risk_score` from inverse-normalized `atr_pct`
- `liquidity_score` from normalized `avg_amount_20d` and `close-vs-vwma`

Derived text fields:

- `strategy_tags` includes:
  - `trend_up` when `close > ma20` and `ma20 > ma60`
  - `momentum_positive` when `ret_20 > 0`, `ret_60 > 0`, and `macdh > 0`
  - `above_vwma` when `close > vwma`
- `risk_flags` includes:
  - `high_atr` when `atr_pct > 0.05`
  - `rsi_hot` when `rsi > 70`
  - `rsi_cold` when `rsi < 35`

Filtering rule rationale:

- `min_listing_days=180` handles seasoning when `list_date` exists.
- `bar_count >= 60` only guarantees that 60-day rolling metrics can be computed.
- Apply `too_new` before `insufficient_bars` so recently listed stocks with valid `list_date` get the correct drop reason.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/screener/test_filters.py tests/screener/test_ranker.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tradingagents/screener/filters.py tradingagents/screener/ranker.py tests/screener/test_filters.py tests/screener/test_ranker.py
git commit -m "feat(screener): add filtering and ranking"
```

### Task 6: Persist artifacts and orchestrate the end-to-end pipeline

**Files:**
- Create: `tradingagents/screener/storage.py`
- Create: `tradingagents/screener/pipeline.py`
- Test: `tests/screener/test_pipeline.py`

**Step 1: Write the failing test**

Add end-to-end pipeline tests with mocked universe/history functions covering:

- output directory creation
- all six required artifact files written
- `filtered_out.csv` contains `drop_reason`
- `filtered_out.csv` contains `fetch_failed` rows from market-data fetch failures
- `llm_pool.json` contains exactly the top `top_k` candidates
- `run_meta.json` includes config snapshot and counts
- run directory name uses `YYYYMMDD_HHMMSS`

**Step 2: Run test to verify it fails**

Run: `pytest tests/screener/test_pipeline.py -q`
Expected: FAIL because pipeline and storage modules do not exist.

**Step 3: Write minimal implementation**

Implement in `storage.py`:

- `prepare_run_dir(base_output_dir: str, as_of_date: str) -> Path`
- `write_run_artifacts(...) -> ScreenRunResult`

Implement in `pipeline.py`:

- `run_screen(config: ScreenRunConfig, progress_callback: Callable | None = None) -> ScreenRunResult`

Pipeline order is fixed:

1. load universe
2. fetch histories
3. build features
4. merge fetch failures into the filtered-out table
5. apply hard filters
6. score candidates
7. sort by `global_rank`
8. truncate to `top_k`
9. write artifacts

`prepare_run_dir()` must format the directory name as `datetime.now().strftime("%Y%m%d_%H%M%S")` to align with existing report IDs in the codebase.

**Step 4: Run test to verify it passes**

Run: `pytest tests/screener/test_pipeline.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tradingagents/screener/storage.py tradingagents/screener/pipeline.py tests/screener/test_pipeline.py
git commit -m "feat(screener): add artifact writer and pipeline orchestration"
```

### Task 7: Expose the screener through CLI

**Files:**
- Modify: `cli/main.py`
- Create: `tests/cli/__init__.py`
- Create: `tests/cli/test_screen_command.py`
- Reference: `tradingagents/screener/schema.py`
- Reference: `tradingagents/screener/pipeline.py`

**Step 1: Write the failing test**

Add CLI tests for:

- `screen` command parses `--date`, `--markets`, `--top-k`, `--limit-per-market`, `--us-manifest`, `--output-dir`
- missing `--us-manifest` when `us` is requested returns a non-zero error
- long-running path reports progress updates during history fetch
- success path prints counts, top preview, and artifact directory

Use `typer.testing.CliRunner`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_screen_command.py -q`
Expected: FAIL because `screen` command is not registered.

**Step 3: Write minimal implementation**

Add `@app.command()` named `screen` to `cli/main.py`.

CLI behavior:

- parse comma-separated markets
- construct `ScreenRunConfig`
- call `run_screen(config, progress_callback=...)`
- print:
  - per-market universe counts
  - filter reason counts
  - top 10 candidate preview with `symbol`, `market`, `global_rank`, `total_score`
  - run directory path
- render progress for long-running fetches with `rich.progress` so the command does not appear hung

Do not call `TradingAgentsGraph` or any existing agent workflow from this command.

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_screen_command.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/main.py tests/cli/__init__.py tests/cli/test_screen_command.py
git commit -m "feat(cli): add screener command"
```

### Task 8: Add screener web backend endpoints and background task runner

**Files:**
- Modify: `web/backend/main.py`
- Modify: `tests/web/test_backend_main.py`
- Reference: `tradingagents/screener/schema.py`
- Reference: `tradingagents/screener/pipeline.py`

**Step 1: Write the failing test**

Add backend tests for:

- `POST /api/screener/tasks` creates a pending screener task
- requesting `"us"` without `SCREEN_US_MANIFEST_PATH` returns HTTP 400
- screener task creation is rejected when the combined analysis+screener active queue already has 2 jobs
- screener task snapshots persist and recover like analysis tasks
- `GET /api/screener/runs` lists completed screener runs by reading `run_meta.json`
- `GET /api/screener/runs/{run_id}/candidates` returns parsed candidate rows

Use mocks for `run_screen()`; do not run a real screener inside the backend tests.

**Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_backend_main.py -q`
Expected: FAIL because screener task models and endpoints are not registered.

**Step 3: Write minimal implementation**

Add to `web/backend/main.py`:

- `SCREENER_RESULTS_DIR = PROJECT_ROOT / "results" / "screener"`
- `SCREENER_TASKS_STATE_DIRNAME = ".screener_tasks"`
- `ScreenTaskCreatePayload`
- `ScreenerTask`
- separate in-memory `screener_tasks` store and snapshot helpers
- `_run_screener_task()` that calls `run_screen(config, progress_callback=...)`
- REST endpoints for screener config, tasks, runs, and candidates

Rules:

- Do not overload analysis `TaskCreatePayload` or `TaskProgress` shapes.
- Keep screener tasks and analysis tasks logically separate, even if helper code is shared.
- Screener task creation must respect the same combined active-task limit as analysis tasks: no more than 2 pending/running jobs across both task types.
- `GET /api/screener/config/options` must expose:
  - market options (`cn`, `us`)
  - default `top_k`
  - default `limit_per_market`
  - whether backend US screening is enabled via `SCREEN_US_MANIFEST_PATH`
- `GET /api/screener/runs/{run_id}/candidates` must read `candidates.csv` and return JSON rows for the frontend table.

**Step 4: Run test to verify it passes**

Run: `pytest tests/web/test_backend_main.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add web/backend/main.py tests/web/test_backend_main.py
git commit -m "feat(web): add screener task and results endpoints"
```

### Task 9: Add web screener launcher and results list UI

**Files:**
- Modify: `web/frontend/lib/api.ts`
- Modify: `web/frontend/app/page.tsx`
- Modify: `web/frontend/app/page.test.mjs`
- Modify: `web/frontend/components/Sidebar.tsx`
- Modify: `web/frontend/components/Sidebar.test.mjs`
- Create: `web/frontend/components/NewScreenerForm.tsx`
- Create: `web/frontend/components/NewScreenerForm.test.mjs`
- Create: `web/frontend/components/ScreenerTaskProgress.tsx`
- Create: `web/frontend/components/ScreenerTaskProgress.test.mjs`
- Create: `web/frontend/components/ScreenerResultsViewer.tsx`
- Create: `web/frontend/components/ScreenerResultsViewer.test.mjs`

**Step 1: Write the failing frontend tests**

Add tests for:

- `page.tsx` lifts screener run state and screener task state alongside existing report state
- `page.tsx` renders a launch action for screener runs in the main start panel
- `Sidebar.tsx` renders a second launch button for screener runs
- launch controls lock when combined analysis and screener active tasks reach 2
- `NewScreenerForm.tsx` requests screener config options and submits screener tasks
- `ScreenerTaskProgress.tsx` renders background screener stage progress
- `ScreenerResultsViewer.tsx` renders a candidate table with sortable score columns

Use the existing source-based `.test.mjs` style already used by `page`, `Sidebar`, and `TaskProgress`.

**Step 2: Run frontend tests to verify they fail**

Run: `cd web/frontend && npm test`
Expected: FAIL because screener components and API functions do not exist yet.

**Step 3: Write minimal implementation**

Update `web/frontend/lib/api.ts` with:

- screener config types and fetcher
- screener task types and fetchers
- screener run summary/detail types and fetchers
- screener task SSE subscription helper

Update `web/frontend/app/page.tsx` to add state for:

- `showNewScreener`
- `activeScreenerTaskId`
- `selectedScreenerRunId`
- `screenerRuns`
- `screenerTasks`

Add three new components:

- `NewScreenerForm.tsx`
  - modal parallel to `NewAnalysisForm`
  - fields: `markets`, `as_of_date`, `top_k`, `limit_per_market`
  - if US backend support is disabled, the US option is visibly disabled with an explanation
- `ScreenerTaskProgress.tsx`
  - parallel to `TaskProgress`
  - shows screener pipeline stages like `Universe`, `History`, `Features`, `Filters`, `Ranking`, `Export`
  - includes a button to view results when the run is completed
- `ScreenerResultsViewer.tsx`
  - renders the screener result list as a sortable table
  - minimum visible columns: `symbol`, `market`, `global_rank`, `total_score`, `trend_score`, `momentum_score`, `risk_score`, `liquidity_score`, `strategy_tags`, `risk_flags`

Update `Sidebar.tsx`:

- add a second CTA button labeled `New Screener`
- add a `Recent Screeners` section listing recent screener runs
- selecting a screener run opens `ScreenerResultsViewer`

Update the main start panel in `page.tsx`:

- add a visible `Launch Screener` action alongside the existing research-centric affordances
- opening this action must trigger `NewScreenerForm`

Page orchestration rules:

- analysis report selection remains unchanged
- screener run selection is mutually exclusive with report selection
- screener task progress is shown in the main pane while a screener task is active
- after screener completion, auto-refresh screener runs and switch to the newly completed run
- analysis tasks and screener tasks contribute to one shared queue lock in the UI so launch buttons disable consistently once 2 total background jobs are active

**Step 4: Run frontend tests to verify they pass**

Run: `cd web/frontend && npm test`
Expected: PASS

**Step 5: Commit**

```bash
git add web/frontend/lib/api.ts web/frontend/app/page.tsx web/frontend/app/page.test.mjs web/frontend/components/Sidebar.tsx web/frontend/components/Sidebar.test.mjs web/frontend/components/NewScreenerForm.tsx web/frontend/components/NewScreenerForm.test.mjs web/frontend/components/ScreenerTaskProgress.tsx web/frontend/components/ScreenerTaskProgress.test.mjs web/frontend/components/ScreenerResultsViewer.tsx web/frontend/components/ScreenerResultsViewer.test.mjs
git commit -m "feat(web): add screener launcher and results viewer"
```

### Task 10: Final verification and operator docs

**Files:**
- Modify: `README.md`
- Modify: `web/README.md`
- Test: `tests/screener/test_pipeline.py`
- Test: `tests/cli/test_screen_command.py`
- Test: `tests/web/test_backend_main.py`

**Step 1: Write the failing documentation expectation**

Add or update one lightweight test only if docs or example strings are already asserted elsewhere. Otherwise keep verification command-only.

**Step 2: Run targeted tests before docs update**

Run: `pytest tests/screener tests/cli/test_screen_command.py tests/web/test_backend_main.py -q`
Run: `cd web/frontend && npm test`
Run: `cd web/frontend && npm run build`
Expected: PASS before touching docs.

**Step 3: Write minimal documentation**

Update `README.md` and `web/README.md` with a short screener section that includes:

- purpose of the screener
- required CN token
- CLI requirement for `--us-manifest`
- Web requirement for `SCREEN_US_MANIFEST_PATH`
- one CLI example command
- one Web behavior summary
- location of output artifacts
- explicit note that LLM analysis happens after screener output, not during screener execution

**Step 4: Run final verification**

Run: `pytest tests/screener tests/cli/test_screen_command.py tests/web/test_backend_main.py -q`
Run: `cd web/frontend && npm test`
Run: `cd web/frontend && npm run build`
Expected: PASS

Optional smoke run if credentials and manifest are available:

Run: `tradingagents screen --date 2026-03-21 --markets cn,us --top-k 20 --limit-per-market 20 --us-manifest /abs/path/to/us_manifest.csv --output-dir ./results/screener`
Expected: command exits successfully and writes all artifacts under a new timestamped directory.

Optional web smoke:

- start backend and frontend
- click `New Screener`
- launch a CN-only run
- observe progress updates
- verify the completed run appears under `Recent Screeners`
- open the run and confirm the candidate table renders

**Step 5: Commit**

```bash
git add README.md web/README.md
git commit -m "docs: add screener cli and web usage notes"
```

## Acceptance Criteria

- `tradingagents screen` exists and runs independently of the existing `analyze` workflow.
- Web UI includes a `New Screener` launch button separate from `New Analysis`.
- Web list page includes a visible screener launch action without requiring the user to first open a report.
- Web UI can start a screener task, show screener progress, and open a screener results list after completion.
- A single run writes all six required artifacts under `results/screener/<YYYYMMDD_HHMMSS>/`.
- The screener never calls any LLM provider, graph runner, or agent workflow.
- CN and US candidates are normalized into one shared candidate schema.
- Ranking is comparable only after per-market normalization, not by mixing raw metrics directly.
- Runs requesting US data fail fast when `--us-manifest` is missing.
- Web screener requests for US fail fast when `SCREEN_US_MANIFEST_PATH` is missing.
- Runs requesting CN data fail fast when `TUSHARE_TOKEN` is missing.
- CN liquidity filtering uses yuan-normalized Tushare amounts rather than raw `千元`.
- CN fetch loops remain usable on free-tier Tushare by rate-limiting and retrying instead of burst firing all symbols.
- Web launch controls disable once 2 combined analysis/screener background tasks are pending or running.

## Test Commands

- `pytest tests/screener/test_schema.py -q`
- `pytest tests/screener/test_universe.py -q`
- `pytest tests/screener/test_market_data.py -q`
- `pytest tests/screener/test_indicators.py -q`
- `pytest tests/screener/test_filters.py tests/screener/test_ranker.py -q`
- `pytest tests/screener/test_pipeline.py -q`
- `pytest tests/cli/test_screen_command.py -q`
- `pytest tests/web/test_backend_main.py -q`
- `pytest tests/screener tests/cli/test_screen_command.py tests/web/test_backend_main.py -q`
- `cd web/frontend && npm test`
- `cd web/frontend && npm run build`

## Assumptions

- CN universe breadth is acceptable via Tushare `stock_basic` for MVP.
- US universe breadth is delegated to a manifest file; no remote US universe acquisition is implemented in MVP.
- Web-mode US screening depends on backend env `SCREEN_US_MANIFEST_PATH`; the browser never uploads or submits a filesystem path.
- Daily screening is keyed by `as_of_date`, with no intraday or minute-bar support.
- Existing dataflow helper internals may be imported by the screener, but existing public string-returning tool contracts must not be changed.
- If a symbol has no valid history row on or before `as_of_date`, it is excluded from candidates and recorded in `filtered_out.csv`.
- `tests/cli/__init__.py` is included for directory consistency, even though pytest would not strictly require it.
