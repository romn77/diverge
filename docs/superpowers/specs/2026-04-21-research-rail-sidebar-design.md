# Research Rail Sidebar Design

## Goal

Refactor the workbench sidebar into a simpler navigation rail that matches the actual product structure:

- `Analysis`
- `Screener`
- `Journal`

The new sidebar should feel like a modern SaaS research workspace instead of a landing-page-style control stack. It should prioritize orientation and primary actions, while moving browsing-heavy modules back into page content.

## Current Problems

The current sidebar combines too many responsibilities in one vertical stack:

1. Primary navigation
2. Launch actions
3. Task monitoring
4. Search entry
5. Recent content browsing
6. Ticker browsing

This creates three UX failures:

- Navigation and content browsing are visually mixed together.
- Secondary utilities compete with top-level destinations.
- The mobile drawer becomes too long and forces users to scan labels that are not true navigation.

The current visual language also over-emphasizes launch cards, which makes the sidebar feel closer to a marketing surface than a research tool.

## Design Direction

### Product Tone

Use a modern SaaS treatment with a research-workbench attitude:

- quiet, structured, credible
- slightly warm but mostly neutral
- compact and directional instead of decorative

### Visual Character

The sidebar should feel like a persistent rail for workspace movement:

- restrained surfaces
- low-noise typography
- one clear primary action
- compact but confident active states
- subtle status indicators instead of large blocks

### Explicitly Avoid

- stacked hero-like CTA cards
- repeated uppercase section headings for every block
- recent-content modules inside the primary nav rail
- multiple buttons that perform nearly the same routing action
- large saturated fills for every top-level choice

## Information Architecture

The sidebar is reduced to four zones.

### 1. Brand Header

Top of the rail:

- `TradingAgents`
- `Research Workbench`

This area should be compact and stable. It is not a hero and should not consume vertical space unnecessarily.

### 2. Primary Action

One unified `+ New` button sits below the brand header.

Clicking the button opens a small menu or compact action sheet with:

- `New Analysis`
- `New Screener`

Rationale:

- This preserves a single primary action.
- It removes the false hierarchy where launch actions visually overshadow navigation.
- It makes `Journal` a first-class destination rather than a third CTA card.

### 3. Primary Navigation

The rail should expose exactly three first-level destinations:

- `Analysis`
- `Screener`
- `Journal`

Expected behavior:

- `Analysis` routes to the home workbench view and serves as the reports-oriented workspace entry.
- `Screener` routes to the screener workspace entry.
- `Journal` routes to the existing trade journal page.

Each nav item should support:

- icon
- label
- active state
- optional small badge when needed

Active state should be modern SaaS, not card-like:

- subtle tinted background
- stronger text/icon color
- thin leading accent bar or inset indicator

### 4. Activity Utility

The bottom utility area contains one compact entry:

- `Activity`

This entry summarizes background work, for example:

- `Activity`
- `2 active`

Clicking it should reveal or route into the combined task-monitoring surface. This surface may include:

- analysis tasks
- screener tasks

The key rule is that queue details are no longer rendered inline in the main nav stack.

## Content That Must Leave the Sidebar

The following modules should move out of the sidebar and into page content, mainly the home dashboard:

- report search form
- `Open results`
- `Open home results`
- recent screener runs list
- recent reports list
- all tickers list
- inline task queue cards
- inline screener queue cards

These are browse surfaces, not core navigation.

## Destination Strategy

The product should treat the rail as movement between workspace modes, and the page body as the place where users browse and inspect data.

### Analysis

This remains the default workbench destination and should contain:

- search
- recent reports
- tracked tickers
- report entry points
- analysis-related empty states

### Screener

This becomes the screener workspace destination and should contain:

- recent screener runs
- screener-focused empty state
- launch affordance context if needed

### Journal

This remains a standalone destination with no launch-card treatment.

### Activity

This becomes the place to monitor in-flight work rather than scattering queues across the rail.

## Interaction Model

### Desktop

- Sidebar stays persistent.
- Width is slightly narrower than the current expanded layout.
- Collapsed rail remains supported, but only for the simplified structure.
- Collapsed state shows icons plus badges where needed.

### Mobile

- Drawer opens with the same four-zone structure.
- The drawer should be short enough to fit the primary model without long scroll on first load.
- Recent content should not appear in the drawer by default.

### New Menu

The `+ New` control should open a compact menu with two actions. The interaction should feel lightweight and immediate, not like a full modal.

### Activity Entry

The activity entry may open:

- a right-side panel on desktop, or
- a full drawer/sheet on mobile, or
- a dedicated route if the existing architecture makes that cheaper

Implementation should prefer the least invasive route-aware option already consistent with the workbench shell.

## Visual System

### Layout

- tighter vertical rhythm than the current stack
- clearer separation between primary nav and utility zone
- fewer bordered cards
- fewer full-width blocks

### Typography

- reduce excessive tracking on utility labels
- keep labels readable and direct
- avoid making every supporting line uppercase
- preserve good contrast and tab order

### Color

Use the existing brand warmth selectively:

- orange tone for primary action and active emphasis
- slate or charcoal neutrals for structure
- soft surface contrast for selected states

Color should signal hierarchy, not decorate every section.

### Motion

- short hover and press transitions
- no layout-shifting animations
- reduced-motion safe

## Component Plan

Refactor the sidebar into smaller internal sections inside `Sidebar.tsx`, or split into subcomponents if that reduces complexity:

- `SidebarBrand`
- `SidebarNewMenu`
- `SidebarPrimaryNav`
- `SidebarActivityLink`

If extraction is small and local, it is acceptable to keep them in the same file first. If the file remains too large after the redesign, extract them into focused components.

## Route and State Expectations

- Primary nav active state derives from pathname.
- `Analysis` should map cleanly to the home workbench route.
- `Screener` should map to a stable screener-focused destination instead of relying on a recent-run list.
- `Activity` badge derives from combined active analysis and screener tasks.
- Search query state should stay URL-driven, but the search UI itself moves into page content.

## Accessibility Requirements

- full keyboard navigation
- clear focus states
- no icon-only primary nav without labels in expanded mode
- touch targets at least 44px
- active route clearly communicated visually
- menu and drawer escape routes preserved

## Testing Impact

Update sidebar source-level tests to reflect the new model:

- remove assertions that require inline recent reports, recent screeners, all tickers, or inline search controls in the sidebar
- assert presence of a single `New` action surface
- assert three primary nav destinations
- assert `Activity` utility entry
- keep route-aware expectations for active state behavior

Home/dashboard tests should be updated to expect the migrated browse modules there instead.

## Implementation Notes

To minimize churn:

1. Redesign sidebar structure first.
2. Move browse modules into the appropriate destination pages.
3. Introduce the unified `New` menu.
4. Add or adapt a screener landing destination if the current route model needs one.
5. Reconcile tests after structure is stable.

## Success Criteria

The redesign is successful when:

- the sidebar reads as navigation first
- users can identify the three main workspace destinations immediately
- launch actions no longer dominate the rail
- mobile drawer opens into a concise navigation model
- browsing and monitoring surfaces live in content areas, not the nav rail
- the interface feels closer to a modern SaaS workbench than a stacked campaign page
