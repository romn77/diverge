---
name: pr-quality-review
description: PR quality review and merge-readiness audit for pull requests, local branches, and code diffs. Use when Codex is asked to review a PR, inspect a branch before merge, assess code quality risks, verify test coverage, check regressions, or produce a quality gate summary for backend, frontend, database, security, performance, or user-facing changes.
---

# PR Quality Review

## Overview

Use this skill to perform a code-review style quality audit of a PR or local branch. Focus on release-blocking defects, regressions, missing tests, security/privacy risks, migration hazards, and user-visible behavior mismatches.

## Workflow

1. Identify the review target.
   - For a PR URL or number, gather title, description, changed files, commits, and diff with `gh pr view` / `gh pr diff` when available.
   - For a local branch, compare against the merge base of the target branch when known; otherwise compare against the current upstream or the branch point.
   - Confirm whether the worktree has uncommitted changes and include them only if they are part of the review target.

2. Build a risk map before judging code.
   - List touched domains: API contracts, auth/permissions, data migrations, financial calculations, scheduling/date logic, background jobs, storage, frontend workflows, tests, and docs.
   - Prioritize files that sit on shared contracts or production data paths over cosmetic or isolated UI changes.

3. Inspect for correctness first.
   - Trace call paths from changed entry points to consumers.
   - Check edge cases, backwards compatibility, empty/error states, timezone/date boundaries, concurrency, retries/idempotency, and authorization boundaries.
   - For frontend changes, check state transitions, accessible controls, responsive layout risks, stale memo dependencies, and whether copy matches behavior.

4. Verify test evidence.
   - Prefer focused tests for changed behavior, then broader suites when shared contracts changed.
   - Treat tests that assert only source text as weaker evidence unless they protect an intentional contract.
   - Call out missing regression coverage when the diff changes behavior without a test that would fail on the old bug.

5. Report findings with review discipline.
   - Lead with findings, ordered by severity.
   - Include exact file and line references when possible.
   - Do not list speculative concerns as findings; put uncertainty under Open Questions.
   - If no blocking issues are found, say that clearly and still note residual risks or checks not run.

## Severity

- `P0`: Must fix immediately; data loss, security break, broken deploy, or catastrophic user impact.
- `P1`: Should block merge; likely regression, incorrect behavior, permission leak, migration hazard, or missing critical test.
- `P2`: Important but may not block; edge-case bug, incomplete coverage, confusing UX, maintainability risk.
- `P3`: Minor quality issue; cleanup, naming, small consistency improvement.

## Output Shape

Use this structure unless the user asks for a different format:

```markdown
**Findings**
- [P1] Short title — path/to/file.ext:123
  Explain the failing scenario, why it matters, and what change would address it.

**Open Questions**
- Any ambiguity that changes the review conclusion.

**Verification**
- Checks run and their result.
- Checks not run and why.

**Summary**
- Brief merge-readiness judgment and the highest-risk area.
```

When reviewing in the Codex app, use inline code comments only for actionable findings with tight line ranges. Keep the final answer concise and avoid restating the whole diff.
