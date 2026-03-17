# Report Viewer (Read-Only) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a read-only web UI that lets users browse and read TradingAgents analysis reports from the `reports/` directory.

**Architecture:** FastAPI backend scans `reports/` and exposes 3 read-only REST endpoints (list, structure, content). Next.js frontend renders a sidebar + tabbed markdown viewer. No database, no auth, no write operations.

**Tech Stack:** FastAPI, uvicorn, Next.js (App Router), TypeScript, Tailwind CSS, react-markdown, remark-gfm, @tailwindcss/typography

---

## TL;DR
> **Summary**: Read-only report viewer — FastAPI serves report files, Next.js renders them with tabs.
> **Deliverables**: `web/backend/main.py` (3 endpoints), `web/frontend/` (sidebar + tabbed viewer)
> **Effort**: Short (1-2 hours of agent execution)
> **Parallel**: YES - 2 waves
> **Critical Path**: Task 1 → Task 2 → Task 3 (backend) → Task 4+5 (frontend, parallel) → Task 6 (verify)

## Context

### Original Request
Simplify the full report-ui plan to only display existing reports. No analysis trigger, no SSE streaming, no job management.

### UI Reference
`docs/ui_design/screen.png` — QuantCore-style layout:
- **Left sidebar**: Search box + report list grouped by ticker (tree structure)
- **Top bar**: Ticker name + tab navigation (Complete Report / Analysts / Research / Trading / Risk / Portfolio)
- **Main content**: Markdown rendering of selected report file, with analyst cards per tab

### Report Data Structure
Reports live in `reports/{TICKER}_{YYYYMMDD_HHMMSS}/`:
```
reports/SPY_20260305_155836/
├── complete_report.md
├── 1_analysts/    → market.md, sentiment.md, news.md, fundamentals.md
├── 2_research/    → bull.md, bear.md, manager.md
├── 3_trading/     → trader.md
├── 4_risk/        → aggressive.md, conservative.md, neutral.md
└── 5_portfolio/   → decision.md
```
**Important**: All subdirectories and files are conditionally created (`cli/main.py:638-719`). A report may be missing entire categories.

### Metis Review (gaps addressed)
- Directory names treated as **opaque IDs** (not parsed for ticker/date) — display metadata extracted from `complete_report.md` header
- Partial reports handled with graceful empty states per tab
- Path traversal guard via `Path.resolve()` + `.is_relative_to()`
- `.gitignore` updated for frontend artifacts
- FastAPI/uvicorn added as optional deps in `pyproject.toml`

## Work Objectives

### Core Objective
A working local web UI where users can browse and read all existing analysis reports.

### Deliverables
- `web/backend/main.py` — 3 read-only API endpoints
- `web/frontend/` — Next.js app with sidebar + tabbed viewer
- Updated `.gitignore` and `pyproject.toml`

### Definition of Done (verifiable conditions)
- `curl http://localhost:8000/api/reports` returns JSON list of reports
- `curl http://localhost:8000/api/reports/{id}/structure` returns actual files present
- `curl http://localhost:8000/api/reports/{id}/content?path=complete_report.md` returns markdown
- Path traversal attempt returns 403
- `npm run build` succeeds with zero TS errors
- Frontend renders sidebar, tabs, and markdown content at http://localhost:3000

### Must Have
- Report listing grouped by ticker
- Tab navigation: Complete Report + 5 category tabs
- Markdown rendering with GFM tables
- Path safety on all file access
- Graceful empty states for missing categories
- Search/filter in sidebar

### Must NOT Have (guardrails)
- No write/delete/trigger endpoints
- No SSE, WebSocket, or polling for live updates
- No authentication or user management
- No date-range filtering or comparison views
- No download/export buttons
- No `rehype-raw` without sanitization
- No caching infrastructure (Redis, SWR)
- No over-abstracted API client SDK

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: manual curl + build verification (no pytest framework needed for 3 read-only endpoints)
- QA policy: Every task has agent-executed scenarios
- Evidence: .sisyphus/evidence/task-{N}-{slug}.{ext}

## Execution Strategy

### Parallel Execution Waves

**Wave 1** (foundation — sequential):
- Task 1: Scaffold project structure
- Task 2: Backend read-only API
- Task 3: Backend path safety + edge cases

**Wave 2** (frontend — can parallel after Wave 1):
- Task 4: Frontend sidebar + layout
- Task 5: Frontend report viewer with tabs

**Wave 3** (verification):
- Task 6: Integration smoke test + polish

### Dependency Matrix
| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 | none | 2, 4 |
| 2 | 1 | 3, 4, 5 |
| 3 | 2 | 6 |
| 4 | 2 | 6 |
| 5 | 2 | 6 |
| 6 | 3, 4, 5 | none |

## TODOs

- [x] 1. Scaffold Project Structure

  **What to do**:
  1. Create `web/backend/` directory
  2. Create `web/backend/requirements.txt`:
     ```
     fastapi>=0.115.0
     uvicorn[standard]>=0.34.0
     ```
  3. Create Next.js frontend:
     ```bash
     cd web && npx create-next-app@latest frontend \
       --typescript --tailwind --eslint --app --no-src-dir --import-alias "@/*"
     ```
  4. Install frontend deps:
     ```bash
     cd web/frontend && npm install react-markdown remark-gfm @tailwindcss/typography
     ```
  5. Add `.env.local`:
     ```
     NEXT_PUBLIC_API_URL=http://localhost:8000
     ```
  6. Update root `.gitignore` — append:
     ```
     web/frontend/node_modules/
     web/frontend/.next/
     web/frontend/out/
     ```
  7. Update `pyproject.toml` — add optional deps:
     ```toml
     [project.optional-dependencies]
     web = ["fastapi>=0.115.0", "uvicorn[standard]>=0.34.0"]
     ```
  8. Create `web/README.md` with start instructions

  **Must NOT do**: Don't install shadcn/ui yet. Don't create any React components.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: File creation + CLI commands only
  - Skills: [] — no special skills needed
  - Omitted: [`frontend-patterns`] — no component work yet

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 4 | Blocked By: none

  **References**:
  - Pattern: `pyproject.toml:1-42` — existing project packaging config
  - Pattern: `.gitignore` — needs node artifact entries appended
  - External: Next.js create-next-app docs

  **Acceptance Criteria**:
  - [ ] `web/backend/requirements.txt` exists with fastapi + uvicorn
  - [ ] `web/frontend/package.json` exists with react-markdown, remark-gfm, @tailwindcss/typography
  - [ ] `web/frontend/.env.local` contains `NEXT_PUBLIC_API_URL=http://localhost:8000`
  - [ ] `cd web/frontend && npm run build` exits 0
  - [ ] Root `.gitignore` contains `web/frontend/node_modules/`
  - [ ] `pyproject.toml` contains `[project.optional-dependencies]` with `web` group

  **QA Scenarios**:
  ```
  Scenario: Frontend builds successfully
    Tool: Bash
    Steps: cd web/frontend && npm run build
    Expected: Exit code 0, no TypeScript errors
    Evidence: .sisyphus/evidence/task-1-scaffold-build.txt

  Scenario: Backend deps installable
    Tool: Bash
    Steps: pip install -r web/backend/requirements.txt --dry-run
    Expected: All packages resolvable
    Evidence: .sisyphus/evidence/task-1-scaffold-deps.txt
  ```

  **Commit**: YES | Message: `feat(web): scaffold project structure with FastAPI + Next.js` | Files: `web/`, `.gitignore`, `pyproject.toml`

---

- [x] 2. FastAPI Read-Only API (3 endpoints)

  **What to do**:
  Create `web/backend/main.py` with these endpoints:

  **Endpoint 1: `GET /api/reports`** — List all reports
  - Scan `REPORTS_DIR` (env `REPORTS_DIR` or default `../../reports` relative to file)
  - For each subdirectory: read first line of `complete_report.md` to extract ticker (`# Trading Analysis Report: {TICKER}`), second line for date (`Generated: YYYY-MM-DD HH:MM:SS`)
  - If `complete_report.md` missing, use directory name as fallback display
  - Return: `[{"id": "SPY_20260305_155836", "ticker": "SPY", "date": "2026-03-05", "time": "15:58:40"}, ...]` sorted by date desc

  **Endpoint 2: `GET /api/reports/{report_id}/structure`** — List actual files in a report
  - Filesystem scan of the report directory
  - Return actual contents only (not assumed):
    ```json
    {
      "id": "SPY_20260305_155836",
      "ticker": "SPY",
      "has_complete": true,
      "categories": {
        "analysts": ["market", "sentiment", "news", "fundamentals"],
        "research": ["bull", "bear", "manager"],
        "trading": ["trader"],
        "risk": ["aggressive", "conservative", "neutral"],
        "portfolio": ["decision"]
      }
    }
    ```
  - Only include categories that actually have a corresponding directory with `.md` files

  **Endpoint 3: `GET /api/reports/{report_id}/content`** — Get file content
  - Query param `path`: relative path within the report (e.g., `complete_report.md`, `1_analysts/market.md`)
  - **PATH SAFETY** (critical):
    ```python
    report_dir = REPORTS_DIR / report_id
    target = (report_dir / path).resolve()
    if not target.is_relative_to(report_dir.resolve()):
        raise HTTPException(403, "Access denied")
    ```
  - Read file with `encoding='utf-8'`
  - Return: `{"content": "markdown string..."}`

  **CORS**: Allow `http://localhost:3000` origin.

  **Must NOT do**: No write endpoints. No SSE endpoints. No job management. Don't import tradingagents package.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` — Reason: Single-file Python with clear spec
  - Skills: [`api-design`] — REST endpoint patterns
  - Omitted: [`backend-patterns`] — overkill for 3 endpoints

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 3, 4, 5 | Blocked By: 1

  **References**:
  - Pattern: `cli/main.py:630-727` — report structure (category dirs, file names, conditional creation)
  - Pattern: `cli/main.py:725-726` — complete_report.md header format: `# Trading Analysis Report: {TICKER}\n\nGenerated: {YYYY-MM-DD HH:MM:SS}`
  - Data: `reports/SPY_20260305_155836/` — sample report to test against
  - Data: `reports/QQQ_20260306_174555/` — second sample

  **Acceptance Criteria**:
  - [ ] `uvicorn main:app --port 8000` starts without error
  - [ ] `GET /api/reports` returns JSON array with 2 reports (SPY, QQQ)
  - [ ] `GET /api/reports/SPY_20260305_155836/structure` returns categories with actual files
  - [ ] `GET /api/reports/SPY_20260305_155836/content?path=complete_report.md` returns markdown content containing "Trading Analysis Report"
  - [ ] `GET /api/reports/SPY_20260305_155836/content?path=1_analysts/market.md` returns market analyst content
  - [ ] `GET /api/reports/NONEXISTENT/structure` returns 404

  **QA Scenarios**:
  ```
  Scenario: List reports returns both samples
    Tool: Bash
    Steps: cd web/backend && uvicorn main:app --port 8000 & sleep 2 && curl -s http://localhost:8000/api/reports | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d)>=2; print('PASS:', [r['ticker'] for r in d])"
    Expected: PASS with SPY and QQQ tickers
    Evidence: .sisyphus/evidence/task-2-list.txt

  Scenario: Structure shows actual files only
    Tool: Bash
    Steps: curl -s http://localhost:8000/api/reports/SPY_20260305_155836/structure | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['has_complete']==True; assert 'market' in d['categories']['analysts']; print('PASS')"
    Expected: PASS
    Evidence: .sisyphus/evidence/task-2-structure.txt

  Scenario: Content returns valid markdown
    Tool: Bash
    Steps: curl -s "http://localhost:8000/api/reports/SPY_20260305_155836/content?path=complete_report.md" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'Trading Analysis Report' in d['content']; print('PASS')"
    Expected: PASS
    Evidence: .sisyphus/evidence/task-2-content.txt
  ```

  **Commit**: YES | Message: `feat(web): add read-only report API endpoints` | Files: `web/backend/main.py`

---

- [x] 3. Backend Path Safety + Edge Cases

  **What to do**:
  Verify and harden the backend against edge cases:

  1. **Path traversal**: Ensure `../../../.env` and similar attacks are blocked with 403
  2. **Nonexistent report**: Returns 404
  3. **Nonexistent file in valid report**: Returns 404
  4. **Empty reports directory**: `GET /api/reports` returns `[]`
  5. **Report with missing categories**: `GET /structure` only shows present dirs

  Run the verification commands. Fix any issues found.

  **Must NOT do**: Don't add any new endpoints. Don't add auth.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Verification and minor fixes
  - Skills: [`security-review`] — path safety patterns
  - Omitted: [] — none

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 6 | Blocked By: 2

  **References**:
  - Pattern: Python `pathlib.Path.is_relative_to()` — available in Python 3.9+
  - External: OWASP path traversal cheatsheet

  **Acceptance Criteria**:
  - [ ] `curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/reports/SPY_20260305_155836/content?path=../../.env"` returns `403`
  - [ ] `curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/reports/SPY_20260305_155836/content?path=..%2F..%2F.env"` returns `403`
  - [ ] `curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/reports/FAKE_123/structure"` returns `404`
  - [ ] `curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/reports/SPY_20260305_155836/content?path=nonexistent.md"` returns `404`

  **QA Scenarios**:
  ```
  Scenario: Path traversal blocked
    Tool: Bash
    Steps: curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/reports/SPY_20260305_155836/content?path=../../.env"
    Expected: 403
    Evidence: .sisyphus/evidence/task-3-security.txt

  Scenario: URL-encoded traversal blocked
    Tool: Bash
    Steps: curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/reports/SPY_20260305_155836/content?path=..%2F..%2F.env"
    Expected: 403
    Evidence: .sisyphus/evidence/task-3-security-encoded.txt
  ```

  **Commit**: YES | Message: `fix(web): harden API path safety and error handling` | Files: `web/backend/main.py`

---

- [x] 4. Frontend Layout + Report Sidebar

  **What to do**:
  Build the shell layout and sidebar component matching the UI mockup:

  1. **`web/frontend/app/layout.tsx`**: Clean layout with global styles
  2. **`web/frontend/app/page.tsx`**: Main page with sidebar + content area (flexbox)
  3. **`web/frontend/lib/api.ts`**: Fetch helpers for the 3 API endpoints (inline, not SDK):
     ```typescript
     const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
     
     export interface Report { id: string; ticker: string; date: string; time: string; }
     export interface ReportStructure { id: string; ticker: string; has_complete: boolean; categories: Record<string, string[]>; }
     
     export async function listReports(): Promise<Report[]> { ... }
     export async function getStructure(id: string): Promise<ReportStructure> { ... }
     export async function getContent(id: string, path: string): Promise<string> { ... }
     ```
  4. **`web/frontend/components/Sidebar.tsx`** ("use client"):
     - Search input at top (filters by ticker name, client-side)
     - Reports grouped by ticker in collapsible sections
     - Each report item shows date + time
     - Selected report highlighted
     - Empty state: "No reports found" when `reports/` is empty
     - Style: dark sidebar matching mockup (dark bg, light text, orange accent for active)

  **Must NOT do**: Don't build the report viewer yet. Don't add Active Agent Tasks panel. Don't add Export/Live View buttons.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: Layout + styling work referencing mockup
  - Skills: [`frontend-patterns`] — React component patterns
  - Omitted: [`ui-ux-pro-max`] — mockup already provided

  **Parallelization**: Can Parallel: YES (after Task 2) | Wave 2 | Blocks: 6 | Blocked By: 2

  **References**:
  - UI: `docs/ui_design/screen.png` — sidebar layout, colors, typography
  - Data: `reports/` — 2 reports (SPY, QQQ) to verify against
  - Pattern: Tailwind dark sidebar: `bg-gray-900 text-gray-300`

  **Acceptance Criteria**:
  - [ ] `http://localhost:3000` shows sidebar with SPY and QQQ reports listed
  - [ ] Typing in search box filters the report list
  - [ ] Clicking a report highlights it in sidebar
  - [ ] Empty state text shown when search matches nothing
  - [ ] Sidebar matches mockup color scheme (dark background)

  **QA Scenarios**:
  ```
  Scenario: Sidebar lists reports from API
    Tool: Bash
    Steps: cd web/frontend && npm run build
    Expected: Build succeeds with 0 errors
    Evidence: .sisyphus/evidence/task-4-build.txt

  Scenario: Visual check of sidebar layout
    Tool: Playwright (or interactive_bash with curl)
    Steps: Start both servers, navigate to localhost:3000, verify sidebar renders with report list
    Expected: Sidebar visible with grouped reports
    Evidence: .sisyphus/evidence/task-4-sidebar.png
  ```

  **Commit**: YES | Message: `feat(web): add sidebar layout with report listing and search` | Files: `web/frontend/app/`, `web/frontend/components/Sidebar.tsx`, `web/frontend/lib/api.ts`

---

- [x] 5. Frontend Report Viewer with Tabs

  **What to do**:
  Build the tabbed report viewer matching the UI mockup:

  1. **`web/frontend/components/ReportViewer.tsx`** ("use client"):
     - Receives `reportId` prop
     - Fetches structure on mount / reportId change
     - Tab bar: "Complete Report" + one tab per present category (Analysts / Research / Trading / Risk / Portfolio)
     - **Only show tabs for categories that exist** in the structure response
     - Default to "Complete Report" tab
     - When on category tab (e.g., Analysts), show sub-tabs or cards for each file (Market / Sentiment / News / Fundamentals)

  2. **`web/frontend/components/MarkdownContent.tsx`** ("use client"):
     - Renders markdown with `react-markdown` + `remark-gfm`
     - Wrapped in Tailwind `prose` class for typography
     - Memoized with `React.memo` to avoid re-render on parent state changes
     - Loading skeleton while fetching

  3. **Tab-to-path mapping** (hardcoded, matching `cli/main.py:636-721`):
     ```typescript
     const CATEGORY_MAP: Record<string, { dir: string; label: string }> = {
       analysts:  { dir: "1_analysts",  label: "Analysts" },
       research:  { dir: "2_research",  label: "Research" },
       trading:   { dir: "3_trading",   label: "Trading" },
       risk:      { dir: "4_risk",      label: "Risk" },
       portfolio: { dir: "5_portfolio", label: "Portfolio" },
     };

     const FILE_LABELS: Record<string, string> = {
       market: "Market Analyst", sentiment: "Social Analyst",
       news: "News Analyst", fundamentals: "Fundamentals Analyst",
       bull: "Bull Researcher", bear: "Bear Researcher", manager: "Research Manager",
       trader: "Trader",
       aggressive: "Aggressive", conservative: "Conservative", neutral: "Neutral",
       decision: "Portfolio Decision",
     };
     ```

  4. **Empty state per tab**: If a category has no files, show "No data available for this category"

  5. **Update `page.tsx`**: Wire sidebar selection → ReportViewer

  **Must NOT do**: Don't add download/export. Don't add comparison view. Don't parse structured data from markdown (just render as-is).

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: Component + layout work with mockup reference
  - Skills: [`frontend-patterns`] — React state/effect patterns
  - Omitted: [`e2e-testing`] — manual QA sufficient for MVP

  **Parallelization**: Can Parallel: YES (after Task 2) | Wave 2 | Blocks: 6 | Blocked By: 2

  **References**:
  - UI: `docs/ui_design/screen.png` — tab layout, card styling, typography
  - Pattern: `cli/main.py:636-721` — category dir names and file names
  - Data: `reports/SPY_20260305_155836/1_analysts/market.md` — sample content with tables
  - External: react-markdown docs for GFM table rendering

  **Acceptance Criteria**:
  - [ ] Clicking a report in sidebar shows the viewer with tabs
  - [ ] "Complete Report" tab renders full markdown with tables
  - [ ] "Analysts" tab shows cards/sub-tabs for Market, Sentiment, News, Fundamentals
  - [ ] "Research" tab shows Bull, Bear, Manager sub-sections
  - [ ] Switching between reports updates the viewer
  - [ ] Missing category tab not shown (if a report had no risk data, no Risk tab)
  - [ ] `npm run build` succeeds

  **QA Scenarios**:
  ```
  Scenario: Complete report renders with tables
    Tool: Playwright (or interactive_bash)
    Steps: Open localhost:3000, click SPY report, verify Complete Report tab shows markdown with table
    Expected: Markdown tables render as HTML tables, headings are styled
    Evidence: .sisyphus/evidence/task-5-viewer.png

  Scenario: Category tabs show correct sub-files
    Tool: Playwright (or interactive_bash)
    Steps: Click Analysts tab, verify Market/Sentiment/News/Fundamentals sub-tabs appear
    Expected: 4 sub-tabs visible, each loads different content
    Evidence: .sisyphus/evidence/task-5-tabs.png

  Scenario: Build passes
    Tool: Bash
    Steps: cd web/frontend && npm run build
    Expected: Exit code 0
    Evidence: .sisyphus/evidence/task-5-build.txt
  ```

  **Commit**: YES | Message: `feat(web): add tabbed report viewer with markdown rendering` | Files: `web/frontend/components/ReportViewer.tsx`, `web/frontend/components/MarkdownContent.tsx`, `web/frontend/app/page.tsx`

---

- [x] 6. Integration Smoke Test + Dev Script

  **What to do**:
  1. Create `web/start.sh`:
     ```bash
     #!/bin/bash
     set -e
     SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
     
     echo "Starting TradingAgents Report Viewer..."
     
     cd "$SCRIPT_DIR/backend"
     pip install -r requirements.txt -q
     uvicorn main:app --port 8000 &
     BACKEND_PID=$!
     
     cd "$SCRIPT_DIR/frontend"
     npm install --silent
     npm run dev &
     FRONTEND_PID=$!
     
     echo "Backend:  http://localhost:8000"
     echo "Frontend: http://localhost:3000"
     echo "Press Ctrl+C to stop"
     
     trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
     wait
     ```
  2. `chmod +x web/start.sh`
  3. Run full integration smoke test:
     - Start both servers
     - Verify API endpoints respond
     - Verify frontend serves HTML
     - Verify CORS headers present
     - Verify path traversal blocked
  4. Fix any issues found

  **Must NOT do**: Don't add Docker, CI, or deployment config.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Script + verification
  - Skills: [`verification-before-completion`] — thorough final checks
  - Omitted: [] — none

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: none | Blocked By: 3, 4, 5

  **References**:
  - Pattern: Original plan's `web/start.sh` concept

  **Acceptance Criteria**:
  - [ ] `./web/start.sh` starts both servers
  - [ ] `curl http://localhost:8000/api/reports` returns report list
  - [ ] `curl http://localhost:3000` returns HTML
  - [ ] CORS header present on API response for localhost:3000 origin
  - [ ] Path traversal returns 403

  **QA Scenarios**:
  ```
  Scenario: Full integration
    Tool: Bash
    Steps: ./web/start.sh & sleep 8 && curl -s http://localhost:8000/api/reports | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d)>=2; print('API OK')" && curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep 200 && echo "Frontend OK"
    Expected: API OK and Frontend OK printed
    Evidence: .sisyphus/evidence/task-6-integration.txt

  Scenario: Security final check
    Tool: Bash
    Steps: curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/reports/SPY_20260305_155836/content?path=../../.env"
    Expected: 403
    Evidence: .sisyphus/evidence/task-6-security.txt
  ```

  **Commit**: YES | Message: `feat(web): add dev start script and complete integration` | Files: `web/start.sh`

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
Each task produces one atomic commit. Total: 6 commits.

## Success Criteria
1. Both servers start with `./web/start.sh`
2. Sidebar lists existing reports grouped by ticker
3. Clicking a report shows tabbed viewer with Complete Report + category tabs
4. Each tab renders markdown content correctly (including tables)
5. Missing categories gracefully handled (no crash, no empty tab)
6. Path traversal attempts blocked
7. `npm run build` produces zero errors
