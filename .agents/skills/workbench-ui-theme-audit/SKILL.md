---
name: workbench-ui-theme-audit
description: Use when asked to plan, build, refactor, review, or restyle any Workbench frontend page, component, layout, theme, or shared UI primitive that must preserve the existing visual system across light, dark, proof, everforest, and stylful modes.
---

# Workbench UI Theme Audit

## Purpose

Use this skill to prevent one-off buttons, badges, tabs, rows, inputs, or panels
from drifting away from the active theme. The Web Workbench has several theme
layers:

- Base tokens in `web/frontend/app/globals.css`.
- Optional `data-visual-style="stylful"` overrides in `web/frontend/app/stylful.css`.
- Shared UI primitives in `web/frontend/components/ui/`.
- Workbench primitives in `web/frontend/components/workbench/`.
- Page-level feature components under `web/frontend/components/`.

The goal is to make components theme-native by construction, not just patched by
global dark-mode overrides.

## Default Stance

Default to design preservation, not redesign.

- Extend the established Workbench visual language unless the task explicitly
  asks for a redesign.
- Keep page information architecture, density, spacing rhythm, typography
  direction, radius language, shadow language, and motion style stable by
  default.
- Unless the task explicitly asks for a design change, style-element edits such
  as color, type scale, spacing, radius, border treatment, shadow treatment,
  and motion should follow the site-wide design language.
- Do not introduce a new visual language unless the task explicitly calls for
  one.
- Do not "freshen up" a page while solving an unrelated product or data task.
- If a surface looks weak, first fix it by using shared primitives, semantic
  tokens, or existing workbench classes before inventing a new local pattern.

Treat this skill as required for any `web/frontend/app/**/*.tsx`,
`web/frontend/components/**/*.tsx`, `web/frontend/app/globals.css`, or
`web/frontend/app/stylful.css` edit, not just explicit theme tickets.

## Current Audit Snapshot

The analysis dashboard screenshots are broadly cohesive in both light and dark
stylful mode, but the codebase still has a recurring failure mode: local
components mix theme tokens with hard-coded Tailwind colors. Examples found by
static scan include `bg-white/*`, `text-slate-*`, `text-white`,
`bg-amber-50`, `text-sky-700`, and literal `rgba(...)` colors in high-traffic
components such as:

- `web/frontend/components/HomeDashboard.tsx`
- `web/frontend/components/Sidebar.tsx`
- `web/frontend/components/NewAnalysisForm.tsx`
- `web/frontend/components/ScreenerResultsViewer.tsx`
- `web/frontend/components/TaskProgress.tsx`
- `web/frontend/components/ScreenerTaskProgress.tsx`
- `web/frontend/components/AssetsWorkspace.tsx`
- `web/frontend/components/ActivityDashboard.tsx`
- trade form components

`globals.css` currently contains dark/everforest compatibility shims for common
legacy classes. Treat those shims as a safety net only. New work should migrate
the component to tokens or shared primitives instead of adding more hard-coded
color utilities.

## Workflow

1. Identify the UI surface.
   - Note the route, viewport sizes, current `data-theme`, and whether
     `data-visual-style="stylful"` is active.
   - For screenshots, list the visible controls: primary actions, icon buttons,
     segmented filters, tabs, badges, inputs, rows, cards, empty/error states,
     and collapsible headers.

2. Run a static theme scan before editing.

```bash
rg -n '(bg-|text-|border-|ring-|shadow-).*?(slate|zinc|neutral|stone|gray|white|black|amber|yellow|blue|emerald|red|green|purple|orange)|#[0-9a-fA-F]{3,8}|rgba\(|rgb\(' web/frontend/components web/frontend/app
```

3. Classify every match.
   - Allowed: brand assets, SVG icons, chart fallback colors wrapped by token
     lookup, login-only variables, generated markdown styling, or a local CSS
     variable with per-theme overrides.
   - Needs attention: hard-coded colors on interactive controls, selected
     states, disabled states, badges inside buttons, hover/focus styles, list
     rows, cards, panels, inputs, dropdowns, dialogs, and empty/error blocks.

4. Inspect the actual UI in a theme matrix.
   - Minimum routes for workbench changes: `/`, `/screeners`, `/activity`,
     `/assets`, `/journal`, a task page if relevant, and `/login` if auth UI
     changed.
   - Minimum themes: light/default, dark, everforest, and stylful light/dark.
   - Minimum states: default, hover, focus-visible, active/pressed, selected,
     disabled, loading, error, empty, expanded, and collapsed.
   - Minimum widths: desktop around 1440px and mobile around 390px.

5. Fix at the lowest shared layer that owns the behavior.
   - Prefer `Button`, `Badge`, `Tabs`, `Input`, `Select`, `Card`, `Dialog`, and
     workbench primitives before page-local class strings.
   - If many pages repeat the same surface, create or extend a small shared
     class in `globals.css` or a workbench primitive.
   - Update `stylful.css` when the visual style needs a specific border,
     radius, shadow, or sketch treatment.

6. Decide whether the change is preserving or redesigning the page.
   - Preserving: keep the existing shell, content order, typography system,
     token set, and visual personality while fixing the local issue.
   - Redesigning: any intentional shift in page hierarchy, hero treatment,
     card grammar, button style, radius/shadow direction, or motion language.
   - If the task did not explicitly request redesign, stay in preserving mode.

7. Freeze debt unless you are explicitly paying it down.
   - Existing hard-coded color debt may remain temporarily, but do not spread it
     to new files or add new raw color tokens to existing files.
   - Prefer shrinking debt by migrating touched surfaces to shared primitives or
     semantic tokens.
   - If you must keep or add debt for a justified case such as chart internals,
     document it and update the baseline test intentionally.

## Token Rules

Use semantic tokens and shared classes:

- Page/background: `var(--bg)`, `var(--surface-page)`.
- Panels/cards: `card-surface`, `viewer-frame`, `metric-card`,
  `bg-[var(--surface)]`, `bg-[var(--surface-strong)]`.
- Text: `text-[var(--text)]`, `text-muted-foreground`, or `var(--muted)`.
- Borders: `border-[var(--border)]`, `border-[var(--border-strong)]`.
- Primary fills: `bg-[var(--primary)] text-[var(--primary-foreground)]`.
- Accent fills: `bg-[var(--accent)] text-[var(--accent-foreground)]`, only when
  both tokens are correct in all themes.
- Hover: `hover:bg-[color:var(--surface-hover)]` or a tokenized variant.
- Focus: `focus-visible:ring-[color:var(--ring-strong)]`.
- Shadows: `var(--shadow-soft)`, `var(--shadow-hover)`,
  `var(--button-primary-shadow)`, `var(--button-secondary-shadow)`.
- Status: use `var(--success)`, `var(--danger)`, and tokenized soft backgrounds.
  Add a new semantic token before spreading raw warning/info colors.

Avoid these in workbench components unless explicitly justified:

- `bg-white*`, `text-white`, `text-black`
- `text-slate-*`, `bg-slate-*`, `border-slate-*`
- one-off `amber`, `sky`, `rose`, `emerald`, `blue`, `purple`, or `orange`
  Tailwind colors on controls or surfaces
- literal hex/rgb/rgba colors in JSX class names
- selected states that set only the background but not the foreground
- nested count chips inside active buttons that keep `bg-white/*`

Avoid these behavioral design changes unless explicitly requested:

- route-level layout rewrites while doing unrelated feature work
- replacing established workbench typography with a new font mood
- swapping the current radius/shadow system for a new card language
- introducing decorative gradients, hero art, or motion concepts that change
  the product's overall visual identity
- moving page-level actions, filters, or summary blocks into a new hierarchy
  without a user request to redesign the page

## Button And Control Checklist

For every button-like element, verify:

- It uses `Button`/`buttonVariants` unless there is a strong reason not to.
- Selected and pressed states use tokenized foreground and background together.
- Icons inherit text color and are not stuck on a hard-coded gray.
- Inner badges/counters change with the parent state.
- Hover and focus-visible styles are visible in light and dark themes.
- Disabled style remains legible and does not look selected.
- Icon-only controls have a visible focus ring and accessible label.

For tabs, segmented controls, and filters:

- Use `aria-pressed`, `data-state`, or `data-active` consistently.
- Active state should not rely on black/white as a theme shortcut.
- Counts and small chips must be tokenized, especially inside active pills.

For cards, rows, and panels:

- Use shared surface classes instead of repeated `bg-white/*` panels.
- Row hover should use `var(--surface-hover)`.
- Empty/error/warning blocks should use semantic status tokens.

## Verification

Run focused source-contract tests when UI primitives or stylful behavior change:

```bash
cd web/frontend
node --test app/stylful.test.mjs components/ui-layer.test.mjs lib/themeGuard.test.mjs
```

Run broader frontend checks when page components or shared tokens changed:

```bash
cd web/frontend
npm test
npm run build
```

A theme fix is not done until:

- The static scan has no new hard-coded color utilities outside allowed cases.
- `lib/themeGuard.test.mjs` passes, so the design-debt baseline did not expand.
- The changed route was visually checked in light and dark.
- Stylful mode was checked if the changed element has border, radius, shadow, or
  active-state styling.
- The final response names any remaining hard-coded colors that were left
  intentionally.

## Review Output

When reporting a theme audit, lead with concrete findings:

```markdown
**Findings**
- [P2] Active filter count chip ignores dark theme - web/frontend/components/Example.tsx:123
  The parent button switches to a tokenized active fill, but the nested count
  stays `bg-white/55`, making it look detached in stylful dark mode.

**Verification**
- Static theme scan run.
- Checked `/` in light and dark stylful mode.
```

If no issues are found, say that clearly and still list the themes and routes
that were actually checked.
