# Ticker Workspace MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a dedicated ticker workspace route that aggregates reports, opportunities, assets, trades, and price context for one symbol, without adding a new top-level navigation tab.

**Architecture:** Add a new App Router page at `/tickers/[ticker]` and keep the first version front-end composed. Reuse `WorkbenchProvider` report cache plus existing read APIs (`listTrades(ticker)`, `listOpportunityWatchlist()`, `getAssetSummary()`, `getTickerHistory()`, `getStructure(reportId)`) to render a dense symbol-centric page. Defer any new backend “ticker summary” aggregation endpoint until the UI contract is validated.

**Tech Stack:** Next.js App Router, React, TypeScript, existing Workbench shell/providers, FastAPI read APIs, Node built-in source-contract tests, Tailwind/shared Workbench UI primitives.

---

## Scope

### In Scope

- New ticker route: `/tickers/[ticker]`
- Route helper support in `web/frontend/lib/workbenchRoutes.ts`
- One new page component that aggregates:
  - latest report + quick open CTA
  - report history for the same ticker
  - decision/thesis artifact summary when available
  - watchlist/opportunity presence
  - asset position snapshot for the ticker
  - recent trade history and feedback reuse status
  - price panel / recent history
- Entry links from the most important existing surfaces:
  - `HomeDashboard`
  - `ScreenerResultsViewer`
  - `OpportunityRadarPage`
  - `AssetsWorkspace`
  - `TradeJournal`

### Out Of Scope

- New top-level sidebar tab
- New backend ticker-aggregation endpoint in MVP
- Cross-ticker compare workspace
- New write flows beyond existing “open report / run analysis / add to watchlist / record trade” actions
- Redesign of existing Workbench information architecture

## MVP UX Contract

The ticker workspace is a **detail route**, not a global tab. Users arrive by clicking a symbol from existing modules. The page should answer:

1. What is the latest research view on this ticker?
2. Has the view changed over time?
3. Is this ticker currently in our watchlist, positions, or trade journal?
4. What should the user do next?

## Data Strategy

### MVP data sources

- Reports: `useWorkbench().reports`, grouped client-side by ticker
- Latest report artifacts: `getStructure(latestReport.id)` for artifact summaries
- Trades: `listTrades(ticker)`
- Same-ticker feedback: `getTickerTradeFeedback(ticker, { limit: 3 })`
- Assets: `getAssetSummary()` then filter positions by `position.ticker === ticker`
- Opportunity watchlist: `listOpportunityWatchlist()` then filter `symbol === ticker`
- Price context: `getTickerHistory({ symbol: ticker, ... })`

### Why front-end composition first

- Reuses existing auth/permission boundaries
- Avoids backend schema churn before validating the page contract
- Lets us ship the route fast and learn which sections are actually used

### Explicit trade-off

- This introduces multiple client reads for first load
- Acceptable for MVP because the page is a drill-down destination, not the default landing page
- If the page proves useful, add a backend summary endpoint in phase 2

## Recommended Build Order

1. Route plumbing
2. Page shell
3. Data composition layer
4. Core sections
5. Entry-point links
6. Tests, copy, and verification

## Tasks

### Task 1: Add ticker route helper

**Files:**
- Modify: `web/frontend/lib/workbenchRoutes.ts`
- Modify: `web/frontend/lib/workbenchRoutes.test.mjs`

**Step 1: Write the failing test**

Add assertions in `web/frontend/lib/workbenchRoutes.test.mjs` for:

```js
assert.match(source, /export function buildTickerHref/);
assert.match(source, /return `\/tickers\/\$\{encodeURIComponent\(ticker\)\}`;/);
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/yaoma/project/TradingAgents/web/frontend && npm test -- workbenchRoutes.test.mjs
```

Expected: FAIL because `buildTickerHref` does not exist yet.

**Step 3: Write minimal implementation**

Add:

```ts
export function buildTickerHref(ticker: string): string {
  return `/tickers/${encodeURIComponent(ticker.trim().toUpperCase())}`;
}
```

**Step 4: Run test to verify it passes**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add web/frontend/lib/workbenchRoutes.ts web/frontend/lib/workbenchRoutes.test.mjs
git commit -m "feat: add ticker workspace route helper"
```

### Task 2: Add the App Router page contract

**Files:**
- Create: `web/frontend/app/(workbench)/tickers/[ticker]/page.tsx`
- Create: `web/frontend/app/ticker-route.test.mjs`

**Step 1: Write the failing test**

Create `web/frontend/app/ticker-route.test.mjs` with source-contract assertions for:

```js
assert.match(source, /TickerWorkspace/);
assert.match(source, /useParams/);
assert.match(source, /params\.ticker/);
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/yaoma/project/TradingAgents/web/frontend && npm test -- ticker-route.test.mjs
```

Expected: FAIL because the route file does not exist.

**Step 3: Write minimal implementation**

Create a small route file:

```tsx
"use client";

import { useParams } from "next/navigation";
import { TickerWorkspace } from "@/components/TickerWorkspace";

export default function TickerRoutePage() {
  const params = useParams<{ ticker: string }>();
  return <TickerWorkspace ticker={params.ticker} />;
}
```

**Step 4: Run test to verify it passes**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add web/frontend/app/(workbench)/tickers/[ticker]/page.tsx web/frontend/app/ticker-route.test.mjs
git commit -m "feat: scaffold ticker workspace route"
```

### Task 3: Add a ticker workspace data-composition layer

**Files:**
- Create: `web/frontend/lib/tickerWorkspace.ts`
- Create: `web/frontend/lib/tickerWorkspace.test.mjs`
- Reference: `web/frontend/lib/api.ts`
- Reference: `web/frontend/lib/assetsApi.ts`
- Reference: `web/frontend/components/WorkbenchProvider.tsx`

**Step 1: Write the failing test**

Add source-contract coverage for helper functions that normalize ticker comparisons and build page sections, for example:

```js
assert.match(source, /export function normalizeTickerKey/);
assert.match(source, /export function filterReportsForTicker/);
assert.match(source, /export function filterAssetPositionsForTicker/);
assert.match(source, /export function filterWatchlistItemsForTicker/);
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/yaoma/project/TradingAgents/web/frontend && npm test -- tickerWorkspace.test.mjs
```

Expected: FAIL because the helper file does not exist.

**Step 3: Write minimal implementation**

Create pure helpers only, no React:

- `normalizeTickerKey(value: string): string`
- `filterReportsForTicker(reports, ticker): Report[]`
- `filterAssetPositionsForTicker(summary, ticker): AssetPositionRecord[]`
- `filterWatchlistItemsForTicker(items, ticker): WatchlistItem[]`
- `sortReportsNewestFirst(reports): Report[]`
- `findLatestReport(reports): Report | null`

Keep this file deliberately small and deterministic so the UI component is mostly orchestration.

**Step 4: Run test to verify it passes**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add web/frontend/lib/tickerWorkspace.ts web/frontend/lib/tickerWorkspace.test.mjs
git commit -m "feat: add ticker workspace data helpers"
```

### Task 4: Build the ticker workspace shell and load state

**Files:**
- Create: `web/frontend/components/TickerWorkspace.tsx`
- Modify: `web/frontend/app/globals.css`
- Create: `web/frontend/components/TickerWorkspace.test.mjs`

**Step 1: Write the failing test**

Create source-contract assertions for:

```js
assert.match(source, /useWorkbench/);
assert.match(source, /listTrades/);
assert.match(source, /listOpportunityWatchlist/);
assert.match(source, /getAssetSummary/);
assert.match(source, /getTickerHistory/);
assert.match(source, /getStructure/);
assert.match(source, /PageHeader/);
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/yaoma/project/TradingAgents/web/frontend && npm test -- TickerWorkspace.test.mjs
```

Expected: FAIL because the component does not exist.

**Step 3: Write minimal implementation**

Create the component with:

- `ticker` prop
- `useWorkbench()` for cached reports/auth state
- `useEffect` loaders for:
  - report structure of latest report
  - ticker trades
  - trade feedback
  - watchlist
  - asset summary
  - ticker history
- top-level states:
  - `isLoading`
  - `loadError`
  - `latestReportStructure`
  - `trades`
  - `feedback`
  - `watchlistItems`
  - `assetSummary`
  - `history`

Keep load orchestration explicit. Do not introduce a new global provider for MVP.

**Step 4: Run test to verify it passes**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add web/frontend/components/TickerWorkspace.tsx web/frontend/components/TickerWorkspace.test.mjs web/frontend/app/globals.css
git commit -m "feat: add ticker workspace shell"
```

### Task 5: Implement the MVP sections

**Files:**
- Modify: `web/frontend/components/TickerWorkspace.tsx`
- Optionally create: `web/frontend/components/ticker-workspace/TickerWorkspaceSection.tsx`
- Optionally create: `web/frontend/components/ticker-workspace/TickerWorkspaceMetric.tsx`
- Modify: `web/frontend/components/TickerWorkspace.test.mjs`

**Step 1: Write the failing test**

Extend `TickerWorkspace.test.mjs` to require the observable sections:

```js
assert.match(source, /Latest Report/);
assert.match(source, /Report History/);
assert.match(source, /Watchlist/);
assert.match(source, /Positions/);
assert.match(source, /Trade Journal/);
assert.match(source, /TickerPricePanel|TickerSparkline|getTickerHistory/);
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/yaoma/project/TradingAgents/web/frontend && npm test -- TickerWorkspace.test.mjs
```

Expected: FAIL until the UI sections exist.

**Step 3: Write minimal implementation**

Render these blocks, in this order:

1. Header
   - ticker
   - latest report timestamp
   - quick actions: open latest report, run new analysis, record trade
2. Summary metrics
   - report count
   - open positions count
   - matching trade count
   - watchlist status
3. Latest report panel
   - latest report link
   - latest artifact summaries from `decision_card`, `decision_delta`, `thesis`, or `trade_feedback`
4. Report history panel
   - newest-first list of reports for this ticker
5. Position panel
   - matching asset positions, value/state/staleness
6. Trade journal panel
   - recent trades for ticker and whether reusable feedback exists
7. Opportunity/watchlist panel
   - current watchlist item(s) for the ticker
8. Price context panel
   - recent price history using existing chart/sparkline primitives where possible

The page should prefer existing Workbench visual language: dense cards, compact tables, no redesign.

**Step 4: Run test to verify it passes**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add web/frontend/components/TickerWorkspace.tsx web/frontend/components/TickerWorkspace.test.mjs
git commit -m "feat: add ticker workspace summary sections"
```

### Task 6: Add entry links from existing modules

**Files:**
- Modify: `web/frontend/components/HomeDashboard.tsx`
- Modify: `web/frontend/components/ScreenerResultsViewer.tsx`
- Modify: `web/frontend/components/opportunity/OpportunityRadarPage.tsx`
- Modify: `web/frontend/components/AssetsWorkspace.tsx`
- Modify: `web/frontend/components/TradeJournal.tsx`
- Modify tests:
  - `web/frontend/components/HomeDashboard.test.mjs`
  - `web/frontend/components/ScreenerResultsViewer.test.mjs`
  - `web/frontend/components/TradeJournal.test.mjs`
  - add/update contract tests for the other touched components if present

**Step 1: Write the failing tests**

Add source assertions that each component imports or uses `buildTickerHref(...)`.

Examples:

```js
assert.match(source, /buildTickerHref/);
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/yaoma/project/TradingAgents/web/frontend && npm test -- HomeDashboard.test.mjs ScreenerResultsViewer.test.mjs TradeJournal.test.mjs
```

Expected: FAIL until each touched surface links the ticker route.

**Step 3: Write minimal implementation**

Entry rules:

- `HomeDashboard`: ticker text in both calendar rows and grouped rows should link to `/tickers/[ticker]`
- `ScreenerResultsViewer`: symbol cell should link to `/tickers/[symbol]`
- `OpportunityRadarPage`: candidate symbol and watchlist symbol should link to `/tickers/[symbol]`
- `AssetsWorkspace`: if `position.ticker` exists, link it
- `TradeJournal`: selected trade ticker / grouped ticker labels should link to `/tickers/[ticker]`

Do not replace existing “open report” affordances. Add ticker drill-down alongside them.

**Step 4: Run tests to verify they pass**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add web/frontend/components/HomeDashboard.tsx web/frontend/components/ScreenerResultsViewer.tsx web/frontend/components/opportunity/OpportunityRadarPage.tsx web/frontend/components/AssetsWorkspace.tsx web/frontend/components/TradeJournal.tsx web/frontend/components/HomeDashboard.test.mjs web/frontend/components/ScreenerResultsViewer.test.mjs web/frontend/components/TradeJournal.test.mjs
git commit -m "feat: link workbench modules to ticker workspace"
```

### Task 7: Add copy, empty states, and permission-safe behavior

**Files:**
- Modify: `web/frontend/components/TickerWorkspace.tsx`
- Modify: `web/frontend/lib/uiPreferences.ts`
- Modify: `web/frontend/components/TickerWorkspace.test.mjs`

**Step 1: Write the failing test**

Require page copy keys and empty-state labels such as:

```js
assert.match(source, /tickerWorkspace\./);
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/yaoma/project/TradingAgents/web/frontend && npm test -- TickerWorkspace.test.mjs
```

Expected: FAIL until copy keys exist.

**Step 3: Write minimal implementation**

Add localized labels for:

- page title / subtitle
- latest report
- no reports
- no positions
- no trade history
- not on watchlist
- feedback available / unavailable
- open latest report
- run analysis
- record trade

Permission behavior:

- if reports are inaccessible, show the existing protected error pattern
- if one section fails, keep the page partially useful instead of crashing the whole route

**Step 4: Run test to verify it passes**

Run the same command and expect PASS.

**Step 5: Commit**

```bash
git add web/frontend/components/TickerWorkspace.tsx web/frontend/lib/uiPreferences.ts web/frontend/components/TickerWorkspace.test.mjs
git commit -m "feat: add ticker workspace copy and empty states"
```

### Task 8: Verify the route end-to-end

**Files:**
- No required product code changes
- Optional notes update: `docs/plans/2026-05-17-ticker-workspace-mvp.md`

**Step 1: Run focused tests**

Run:

```bash
cd /Users/yaoma/project/TradingAgents/web/frontend && npm test -- workbenchRoutes.test.mjs ticker-route.test.mjs TickerWorkspace.test.mjs HomeDashboard.test.mjs ScreenerResultsViewer.test.mjs TradeJournal.test.mjs
```

Expected: PASS.

**Step 2: Run broader frontend verification**

Run:

```bash
cd /Users/yaoma/project/TradingAgents/web/frontend && npm test
cd /Users/yaoma/project/TradingAgents/web/frontend && npm run build
```

Expected: PASS.

**Step 3: Optional browser verification**

Open the local app and verify:

1. open a ticker from home
2. open a ticker from screener results
3. open a ticker from opportunities watchlist
4. open a ticker from assets
5. open a ticker from journal

Expected: all routes land on the same `/tickers/[ticker]` page and show consistent data slices.

**Step 4: Commit**

```bash
git add web/frontend
git commit -m "test: verify ticker workspace mvp"
```

## Risks And Guardrails

- **Too much backend work too early**
  Keep MVP front-end composed; do not add a ticker summary endpoint unless performance becomes the dominant problem.

- **Turning this into a new top-level product area**
  Do not add a new sidebar tab in MVP. This feature is a drill-down route.

- **Breaking established report/open-report behaviors**
  Add ticker links without removing report links or task links.

- **UI sprawl**
  Reuse dense Workbench cards/tables and existing typography tokens. Do not redesign the shell.

- **Permission mismatch**
  Treat each section as independently fallible; show partial data when some modules are permission-gated.

## Phase 2 Follow-Up (Not Part Of MVP)

- Add backend `/api/tickers/{ticker}/summary`
- Add catalyst / earnings timeline section
- Add cross-report conclusion diff beyond the current `decision_delta`
- Add compare view between two or more tickers
- Add one-click actions from ticker workspace into screener presets / watchlist / trade templates

## Verification Matrix

- Ticker with many reports and trades: `AMD`-like
- Ticker with reports but no trades
- Ticker in watchlist but not in assets
- Ticker in assets but no report
- Ticker with protected modules unavailable under RBAC

## Recommended First Release Slice

If scope must be cut further, ship this order:

1. route helper + route page
2. report history + latest report card
3. ticker links from home and screener
4. trade + watchlist + asset sections

That still proves the navigation model without forcing the full orchestration cost on day one.
