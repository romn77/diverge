# Automation Testing Strategy Progress

## 2026-05-15

- Created a dedicated worktree at `/tmp/diverge-automation-testing`.
- Created branch `codex/automation-testing-strategy`.
- Started analysis files for plan, findings, and progress.
- Added `docs/plans/2026-05-15-automation-testing-strategy.md` with the proposed
  automated testing model, first Playwright slice, fixture strategy, and CI
  recommendation.
- Added repo-local skill `.agents/skills/workbench-automation-testing/` so future
  Codex/agent runs can apply the automation strategy by module workflow.
- Revised the strategy and skill to make browser-driven business workflows the
  default E2E layer; API tests are now framed as setup/support/hidden-contract
  checks rather than the primary automation plan.
- Added `.agents/skills/workbench-automation-testing/references/business-e2e-flows.md`
  for browser-first journeys an agent can execute and later codify.
- Updated `AGENTS.md` so future agents are directed to the browser-first
  business E2E skill and testing rules.
- Checked the new docs for trailing whitespace.
- Validated the skill with `quick_validate.py`.

## Commands And Checks

- `git status --short --branch`
- `git worktree list`
- `git worktree add -b codex/automation-testing-strategy /tmp/diverge-automation-testing`
- `sed -n '1,260p' pyproject.toml`
- `sed -n '1,260p' web/frontend/package.json`
- `sed -n '1,620p' web/start.sh`
- `rg --files .github`
- `rg --files tests`
- `rg --files web/backend`
- `sed -n '1,260p' tests/web/http_harness.py`
- `sed -n '1,260p' tests/web/test_backend_main.py`
- `sed -n '1,260p' tests/test_web_start_script.py`
- `sed -n '1,260p' web/backend/main.py`
- `sed -n '1,260p' web/backend/routers/{auth,assets,trades,tasks,screeners,reports,config,health,data_sync}.py`
- `sed -n '1,340p' web/frontend/components/{HomeDashboard,TaskProgress,ScreenerTaskProgress}.tsx`
- `sed -n '1,280p' web/frontend/components/{AuthProvider,WorkbenchProvider}.tsx`
- `sed -n '1,220p' web/frontend/lib/workbenchRoutes.ts`
- `sed -n '1040,1140p' web/frontend/lib/api.ts`
- `sed -n '1815,2110p' web/frontend/lib/api.ts`
- `sed -n '1,260p' docker-compose.yml`
- `sed -n '1,260p' compose.prod.yml`
- `sed -n '1,260p' .env.example`
- `sed -n '1,220p' .github/pull_request_template.md`
- `rg -n "[[:blank:]]$" docs/plans/2026-05-15-automation-testing-*.md`
- `python3 /mnt/c/Users/may5/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/workbench-automation-testing`

## Errors

- First `git worktree add` attempt failed because the sandbox treated
  `.git/refs` as read-only. Retried with approved escalation and succeeded.
- Unquoted zsh paths containing route groups like `(workbench)` failed with
  `no matches found`; retried with quoted paths.
- Initial `apply_patch` calls created the analysis files in the original
  worktree because the tool has no `workdir` parameter. The files were copied
  into `/tmp/diverge-automation-testing` and removed from the original worktree;
  no user-authored changes were reverted.
- Initial skill initialization failed because the sandbox treated
  `.agents/skills` in the new worktree as read-only. Retried with approved
  escalation and succeeded.
