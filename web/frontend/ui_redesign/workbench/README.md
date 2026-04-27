# Diverge Workbench — UI Kit

A high-fidelity clickable prototype of the Diverge web workbench.

## Screens included
1. **Login** — Split-panel sign-in with brand mark
2. **Home / Analysis Workspace** — Report library, ticker coverage, metric cards
3. **Task Progress** — 6-stage pipeline tracker with live event log
4. **Screener Dashboard** — Candidate workspace with recent runs
5. **Assets Workspace** — Portfolio ledger with positions table

## Usage
Open `index.html` directly — no build step needed. Uses React + Babel inline.

## Components
All components are defined inline in their respective JSX files and exported to `window`:
- `Sidebar.jsx` — collapsible sidebar with nav items
- `Shell.jsx` — app shell (topbar + sidebar layout)
- `Screens.jsx` — all screen components
