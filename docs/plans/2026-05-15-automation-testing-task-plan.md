# Automation Testing Strategy Task Plan

## Goal

Analyze how Diverge should add practical automated testing beyond unit tests,
with a focus on reducing pain from frequent feature work, broad refactors, and
Web Workbench regressions.

## Scope

- Inventory current Python, backend, frontend, and workflow test coverage.
- Identify the highest-risk product flows that need automated scenario tests.
- Propose a layered testing strategy that fits the existing repository.
- Outline an implementation roadmap that can start small and expand safely.

## Phases

1. Complete - Map current test commands, test files, app startup, and CI shape.
2. Complete - Identify automation gaps and risk-heavy workflows.
3. Complete - Design target automated test layers and fixture/data strategy.
4. Complete - Produce recommendations, milestones, and first implementation slice.

## Decisions

- Use this branch for analysis only unless implementation is explicitly requested.
- Treat runtime data under `data/` and generated artifacts as out of scope.
- Prefer focused checks that work locally before introducing broader CI gates.

## Open Questions

- Recommended: run locally and in CI, starting with a fast PR smoke lane.
- Recommended: defer auth/database browser tests until the first fixture-backed
  browser smoke layer is stable.
- Recommended: target local backend plus Next.js `API_PROXY_TARGET` first; keep
  Redis/Postgres/Compose for slower nightly or pre-release smoke.
