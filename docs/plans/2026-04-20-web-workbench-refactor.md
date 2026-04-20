# Web Workbench Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the web workbench into a route-driven, more accessible, and more task-focused Next.js experience without changing backend API contracts.

**Architecture:** Introduce a shared workbench layout and provider so reports, screeners, tasks, and journal views are driven by URLs instead of a single client-side state machine. Move navigation, launch actions, and search into reusable route-aware primitives, then upgrade dialogs and dense data views to be more accessible and actionable.

**Tech Stack:** Next.js App Router, React 19, TypeScript, existing REST API helpers, source-level node tests.

---

### Task 1: Add route and data scaffolding

**Files:**
- Create: `web/frontend/lib/workbenchRoutes.ts`
- Create: `web/frontend/components/WorkbenchProvider.tsx`
- Create: `web/frontend/components/WorkbenchShell.tsx`
- Test: `web/frontend/lib/workbenchRoutes.test.mjs`

**Steps:**
1. Add route helper functions for reports, tasks, screener runs, screener tasks, journal, login redirects, and home search query handling.
2. Add a shared provider that centralizes report/task/screener fetching and exposes refresh helpers plus auth-derived workbench state.
3. Add a shell component that renders the account menu, route-aware sidebar, and launch dialogs around arbitrary page content.
4. Add tests that lock route helper outputs and confirm the new shell/provider entry points exist.

### Task 2: Replace the single-page workbench state machine

**Files:**
- Modify: `web/frontend/app/page.tsx`
- Create: `web/frontend/app/reports/[reportId]/page.tsx`
- Create: `web/frontend/app/tasks/[taskId]/page.tsx`
- Create: `web/frontend/app/screener-tasks/[taskId]/page.tsx`
- Create: `web/frontend/app/screeners/[runId]/page.tsx`
- Create: `web/frontend/app/journal/page.tsx`
- Test: `web/frontend/app/page.test.mjs`

**Steps:**
1. Rewrite the home page to use the shared shell and surface real search results in the content area.
2. Add dedicated App Router pages for report, task, screener task, screener run, and journal views.
3. Remove the state-machine switching logic from the home page and replace it with route links/navigation.
4. Update the page test to assert route-based workbench structure instead of local state buckets.

### Task 3: Refactor navigation for route awareness

**Files:**
- Modify: `web/frontend/components/Sidebar.tsx`
- Test: `web/frontend/components/Sidebar.test.mjs`

**Steps:**
1. Convert sidebar actions for reports, tasks, screeners, and journal into `Link`-backed navigation.
2. Make search submit to the home page query state instead of silently filtering hidden content.
3. Keep launch buttons in the sidebar, but let selection/highlight derive from the current pathname.
4. Update source tests to assert the new route-aware affordances and remove old callback-only expectations.

### Task 4: Improve modal and drawer accessibility

**Files:**
- Create: `web/frontend/components/AccessibleDialog.tsx`
- Modify: `web/frontend/components/NewAnalysisForm.tsx`
- Modify: `web/frontend/components/NewScreenerForm.tsx`
- Modify: `web/frontend/components/WorkspaceAccountMenu.tsx`
- Test: `web/frontend/components/NewAnalysisForm.test.mjs`
- Test: `web/frontend/components/NewScreenerForm.test.mjs`

**Steps:**
1. Add a reusable accessible dialog wrapper with focus trap, restore-focus behavior, and escape handling.
2. Move the analysis and screener launch forms onto that wrapper.
3. Tighten lightweight popover semantics in the account/settings affordances.
4. Update tests to assert the new dialog primitive and accessible behaviors.

### Task 5: Upgrade dense analysis views

**Files:**
- Modify: `web/frontend/components/ScreenerResultsViewer.tsx`
- Modify: `web/frontend/components/TaskProgress.tsx`
- Modify: `web/frontend/components/ScreenerTaskProgress.tsx`
- Modify: `web/frontend/components/TradeJournal.tsx`
- Test: `web/frontend/components/ScreenerResultsViewer.test.mjs`
- Test: `web/frontend/components/TaskProgress.test.mjs`
- Test: `web/frontend/components/ScreenerTaskProgress.test.mjs`
- Test: `web/frontend/components/TradeJournal.test.mjs`

**Steps:**
1. Make screener results feel like a real decision table with sticky metadata, sortable headers, numeric alignment, and row actions.
2. Make task views clearer about status, progress, and next actions now that they are direct destinations.
3. Improve journal hierarchy so filters, record list, and detail panes feel like a route-backed workspace rather than a transient modal view.
4. Update source tests to reflect the upgraded information hierarchy.

### Task 6: Refresh admin and login task framing

**Files:**
- Modify: `web/frontend/app/login/page.tsx`
- Modify: `web/frontend/app/admin/users/page.tsx`
- Test: `web/frontend/app/admin-users.test.mjs`
- Test: `web/frontend/app/login.test.mjs`

**Steps:**
1. Reframe login copy and structure around user tasks instead of backend mechanics.
2. Make the admin page clearer, more navigable, and less backend-explanatory.
3. Update tests to match the new task-oriented framing and navigation.

### Task 7: Verify the refactor

**Files:**
- Modify as needed based on failures from earlier tasks

**Steps:**
1. Run targeted frontend tests for changed app/components/lib files.
2. Run the full frontend test suite.
3. Run a production build for the frontend.
4. If any command fails, fix the issue and rerun before making completion claims.
