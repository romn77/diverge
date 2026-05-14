# Plan: Web UI "New Analysis" Task Launcher

## Context

Currently, report generation only works via `cli/main.py` — users must run CLI commands, answer interactive prompts, and wait for the multi-agent analysis. This plan adds a "New Analysis" button to the web frontend that collects parameters, kicks off background analysis via the backend, streams progress in real-time, and auto-saves the report without asking for save confirmation.

## Architecture Overview

```
Frontend (Next.js)                    Backend (FastAPI)                  Core Library
┌─────────────────┐   POST /api/tasks  ┌──────────────┐   import        ┌──────────────┐
│ NewAnalysisForm  │ ──────────────────>│ Create Task  │ ──────────────>│ runner.py    │
│                  │                    │ + bg thread  │                │ (streaming   │
│ TaskProgress     │  SSE /api/tasks/   │              │  yields events │  generator)  │
│ (EventSource)    │ <══════════════════│ SSE stream   │ <──────────────│              │
└─────────────────┘                    └──────────────┘                └──────────────┘
```

## Storage and visibility contract

- 保持现有扁平目录结构不变: `reports/{TICKER}_{timestamp}/`
- In-progress task output writes to临时目录: `reports/.tmp/<task_id>/`
- 任务成功后, 将 `.tmp/<task_id>/` 重命名/移动到 `reports/{TICKER}_{timestamp}/`
- `GET /api/reports` 扫描时忽略 `.tmp` 目录
- 现有 3 个报告 API 端点都不得暴露 `.tmp` 内容: `_resolve_report_dir()` 必须拒绝 `.tmp` 作为 `report_id`
- `GET /api/reports` 不暴露未完成的报告
- 任务失败时, 删除 `.tmp/<task_id>/` 目录, 不保存报告
- v1 限制: 任务运行状态只保存在内存中; 后端重启后, 活跃任务和 SSE 历史会丢失

## Step 1: Extract reusable analysis runner

**New file: `diverge/runner.py`**

- `AnalysisRequest` dataclass — validated params: ticker, analysis_date, analysts, research_depth, llm_provider, quick_think_llm, deep_think_llm, output_language, google_thinking_level, openai_reasoning_effort
- `AnalysisProgress` dataclass — timestamp, status, stage_status, agent_status, current_agent, message
- `AnalysisTracker` — 一个按 task 实例化的轻量状态对象, 复用 `cli/main.py` 中 `MessageBuffer` 的现有状态模型和推进规则, 但不复用 CLI 的模块级全局 `message_buffer`
- `run_analysis_streaming(request, temp_dir) -> Generator[AnalysisProgress, None, dict]` — builds config from DEFAULT_CONFIG + request (通过 `get_provider_base_url(provider)` 自动推导 `backend_url`), creates `DivergeGraph`, streams via `graph.stream()`, uses `AnalysisTracker` to update status from each chunk, writes intermediate artifacts to temp_dir, and yields serialized progress snapshots for SSE
- Move `save_report_to_disk()` from `cli/main.py:630-727` here; update CLI to import from new location
- 成功后由调用方将 temp_dir 移动到 `reports/{TICKER}_{timestamp}/`, 返回 report_id
- On any exception, delete the temp directory and return no saved report

**Status model (minimal-change approach)**
- Reuse the existing agent-level status semantics from `MessageBuffer`: `pending | in_progress | completed`
- Web stepper exposes only stage-level states: `not_started | processing | completed`
- Stage status is derived from agent status, not from raw chunk names and not from scanning `/results`
- Stage mapping:
  - Analysts → selected analyst agents
  - Research → Bull Researcher, Bear Researcher, Research Manager
  - Trading → Trader
  - Risk → Aggressive Analyst, Neutral Analyst, Conservative Analyst
  - Portfolio → Portfolio Manager
- Mapping rule:
  - all agents `pending` → `not_started`
  - any agent `in_progress` → `processing`
  - all agents `completed` → `completed`
- Keep the existing transition rules from `cli/main.py` for analyst, research, trader, risk, and portfolio updates; do not redesign a new event taxonomy for v1

## Step 2: Backend endpoints

**Modify: `web/backend/main.py`**

2a. **CORS**: Change `allow_methods=["GET"]` → `allow_methods=["GET", "POST"]`

2b. **In-memory task store**:
```python
tasks: dict[str, Task] = {}  # task_id → Task dataclass
```
Each Task holds: id, ticker, analysis_date, analysts, status (pending/running/completed/failed), latest_progress, progress_events list, report_id, error, _subscribers (asyncio.Queue list for SSE)

Use a small `threading.Lock` around task mutation / subscriber registration to avoid races between the worker thread and SSE readers.

2b+. **报告扫描和临时目录保护**:
- `list_reports()` 扫描逻辑跳过 `.tmp`
- `_resolve_report_dir()` 拒绝 `.tmp` 作为 `report_id`, 防止通过 `/api/reports/.tmp/...` 访问未完成内容

2c. **`POST /api/tasks`** — validate inputs, create Task, launch `_run_task()` in `threading.Thread(daemon=True)`, return `{task_id, status}`

2d. **`_run_task(task)`** — background function that:
- Calls `run_analysis_streaming()` from runner.py
- Stores each yielded `AnalysisProgress` snapshot on the task and 通过 `loop.call_soon_threadsafe(queue.put_nowait, event)` 将线程中的快照推送到 async SSE 端点
- On completion: 将 `.tmp/<task_id>/` 移动到 `reports/{TICKER}_{timestamp}/`, sets report_id, status=completed
- On error: sets error, status=failed, 删除 `.tmp/<task_id>/`

2e. **`GET /api/tasks/{task_id}/stream`** — SSE endpoint using `StreamingResponse(media_type="text/event-stream")`:
- Replays existing progress snapshots first (for reconnection)
- Then yields new events from subscriber Queue
- No new dependencies (manual SSE formatting: `data: {json}\n\n`)

2f. **`GET /api/tasks`** — list all tasks with status

2g. **`GET /api/tasks/{task_id}`** — single task status (polling fallback), including `latest_progress`

2h. **`GET /api/config/options`** — returns only currently supported options already defined in config/model config:
- available providers
- quick/deep models for each provider
- analyst options
- research depth options
- output language options
- provider-specific reasoning/thinking options
- No freeform model entry in the web UI for this phase

## Step 3: Frontend API client

**Modify: `web/frontend/lib/api.ts`**

Add TypeScript interfaces and functions:
- `TaskCreateRequest`, `Task`, `ConfigOptions`, `ProgressEvent` interfaces
- `getConfigOptions()`, `createTask()`, `listTasks()`, `getTask()`
- `subscribeToTask(taskId, onEvent)` — uses `EventSource` for SSE, returns cleanup function

`ProgressEvent` payload shape should match the runner snapshot:
- `timestamp`
- `status`
- `stage_status`
- `agent_status`
- `current_agent`
- `message`

## Step 4: New Analysis form component

**New file: `web/frontend/components/NewAnalysisForm.tsx`**

- Modal dialog triggered from Sidebar
- Form sections: Ticker + Date, Analysts (checkboxes), Research Depth (radio), LLM Provider + Models (dropdowns, cascading), Language
- Fetches options from `/api/config/options` on mount
- On submit: POST to `/api/tasks`, closes dialog, starts progress view
- Form choices are strictly limited to values returned by `/api/config/options`
- Styling: existing CSS variables (--primary, --border, --bg), consistent with current design

## Step 5: Task progress component

**New file: `web/frontend/components/TaskProgress.tsx`**

- Agent pipeline stepper: Analysts → Research → Trading → Risk → Portfolio (`not_started` / `processing` / `completed`)
- Event log with timestamps (from SSE progress snapshots / latest message text)
- SSE subscription via `subscribeToTask()`
- Do not infer stage state from filenames or raw backend chunks on the client; render directly from `stage_status`
- On completion: show "View Report" button and refresh the report list, but do not auto-switch to the new report
- On error: shows error message

## Step 6: Wire into existing pages

**Modify: `web/frontend/app/page.tsx`**
- Add state: `activeTaskId`, `showNewAnalysis`
- Render NewAnalysisForm modal when `showNewAnalysis` is true
- Render TaskProgress when `activeTaskId` is set and no report selected
- Refresh report list when task completes, without auto-selecting the new report

**Modify: `web/frontend/components/Sidebar.tsx`**
- Add "New Analysis" button in header area (above search)
- Accept `onNewAnalysis` prop
- Optionally show running tasks with pulsing indicator

**Modify: `web/frontend/app/globals.css`**
- Add modal overlay, form input, stepper styles as needed

## Step 7: Update CLI to use shared runner

**Modify: `cli/main.py`**
- Import `save_report_to_disk` from `diverge/runner.py` instead of local definition
- Keep existing CLI flow otherwise unchanged
- Preserve the current terminal-specific global `message_buffer`; do not reuse it directly in the backend task runner

## Files to create
- `diverge/runner.py` — reusable analysis runner
- `web/frontend/components/NewAnalysisForm.tsx` — form dialog
- `web/frontend/components/TaskProgress.tsx` — progress view

## Files to modify
- `web/backend/main.py` — task endpoints, SSE, CORS, config options
- `web/frontend/lib/api.ts` — new API functions
- `web/frontend/app/page.tsx` — orchestration state
- `web/frontend/components/Sidebar.tsx` — "New Analysis" button
- `web/frontend/app/globals.css` — modal/form/stepper styles
- `cli/main.py` — import save_report_to_disk from runner.py

## Verification

1. Start backend: `cd web/backend && uvicorn main:app --port 8000 --reload`
2. Start frontend: `cd web/frontend && npm run dev`
3. Click "New Analysis" → fill form → submit
4. Verify SSE events stream in browser DevTools (Network → EventStream)
5. Verify agent pipeline stepper updates in real-time using `not_started` / `processing` / `completed`
6. While task is running, verify no in-progress report appears in `/api/reports` or sidebar
7. Manually request `/api/reports/.tmp/...` and verify temp artifacts are rejected
8. On completion, verify report appears in sidebar and can be opened manually, but is not auto-opened
9. Test error case: invalid ticker or missing API keys; verify temp artifacts are cleaned up and no report is saved
10. Verify config form options only show values returned from current backend config endpoints
11. Test concurrent tasks: start 2 analyses simultaneously
