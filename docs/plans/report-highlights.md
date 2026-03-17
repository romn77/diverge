# Report Highlights Optimization

## TL;DR
> **Summary**: Modify **all 12 prompt-producing agent files** (4 analysts + 2 researchers + 1 research manager + 1 trader + 3 risk debators + 1 risk manager) to append a structured JSON highlights block (`json-highlights` fenced code block) to each individual report, then build frontend components that parse this block and render highlight cards above the markdown narrative for quick scanning.
> **Deliverables**: Modified agent prompts (12 files), highlights parser/strip utility, HighlightCards component, updated MarkdownContent, updated ReportViewer, updated globals.css
> **Effort**: Medium-Large
> **Parallel**: YES - 4 waves
> **Critical Path**: Baseline verification → Task 1 (schema + parsing/stripping design) → Tasks 2-13 (prompts, parallel) → Tasks 14 and 16 (component + CSS) → Task 15 (MarkdownContent + ReportViewer integration) → Final verification

## Context
### Original Request
Optimize the report display system. Reports are currently pure markdown rendered as-is, with inconsistent formats across categories and low information density. User wants structured highlights extracted and prominently displayed.

### Interview Summary
- **Approach**: Hybrid — modify LLM prompts + build frontend highlight cards
- **Scope**: All 12 prompt-producing agent files + frontend components. New reports only.
- **Backward compat**: Old reports render as-is (no highlights). No backend changes.
- **Test strategy**: Tests after implementation. QA scenarios in plan.
- **Language**: Bilingual support (EN/CN). JSON keys and enum literals stay in English; free-form values follow the report language.

### Coverage Map: Reports → Agents

| 目录 | 报告文件 | 对应 Agent 文件 | 原计划 | 扩展 |
|------|---------|----------------|--------|------|
| `1_analysts/` | `market.md` | `analysts/market_analyst.py` | ✅ | — |
| | `fundamentals.md` | `analysts/fundamentals_analyst.py` | ✅ | — |
| | `sentiment.md` | `analysts/social_media_analyst.py` | ✅ | — |
| | `news.md` | `analysts/news_analyst.py` | ✅ | — |
| `2_research/` | `bull.md` | `researchers/bull_researcher.py` | ❌ | ✅ NEW |
| | `bear.md` | `researchers/bear_researcher.py` | ❌ | ✅ NEW |
| | `manager.md` | `managers/research_manager.py` | ❌ | ✅ NEW |
| `3_trading/` | `trader.md` | `trader/trader.py` | ❌ | ✅ NEW |
| `4_risk/` | `aggressive.md` | `risk_mgmt/aggressive_debator.py` | ❌ | ✅ NEW |
| | `conservative.md` | `risk_mgmt/conservative_debator.py` | ❌ | ✅ NEW |
| | `neutral.md` | `risk_mgmt/neutral_debator.py` | ❌ | ✅ NEW |
| `5_portfolio/` | `decision.md` | `managers/risk_manager.py` | ❌ | ✅ NEW |
| 根目录 | `complete_report.md` | 合成拼接（非单一 agent） | — | 前端特殊处理 |

> **Note**: `complete_report.md` 是子报告的原样拼接合成。由于新子报告会各自包含 `json-highlights`，本迭代 **不在 Complete Report 页面渲染 highlight cards**；前端只负责在 complete 视图中剥离所有 `json-highlights` block，避免原始 JSON 泄露到页面。

### Metis Review (gaps addressed)
- **LLM format drift**: Enforced fail-open parsing — if JSON block is absent/malformed, render original markdown unchanged.
- **Complete report safety**: `complete_report.md` strips ALL `json-highlights` blocks and renders markdown only.
- **Duplicate blocks**: Individual report parsing uses the FIRST `json-highlights` block found. Ignore subsequent ones.
- **FINAL TRANSACTION PROPOSAL fallback**: If missing from JSON, parse from markdown text as fallback.
- **Security**: No `dangerouslySetInnerHTML`. Card values rendered as plain text. react-markdown safe defaults preserved.
- **Bilingual contract**: JSON keys and enum literals remain stable English constants even when the narrative is Chinese.
- **Prompt conflicts**: Prompts that currently say "without special formatting" or "always conclude with FINAL TRANSACTION PROPOSAL" must be rewritten to explicitly allow a trailing `json-highlights` block without weakening the existing narrative contract.
- **Schema sprawl**: Minimal required keys per category + optional extras. Unrecognized fields ignored gracefully.
- **Race conditions**: Preserve existing `requestIdRef` flow in ReportViewer.tsx.
- **Backend unchanged**: Zero API/endpoint/AgentState changes.

## Work Objectives
### Core Objective
Add structured highlight cards above markdown narrative in the report viewer for all individual report categories, powered by structured JSON output from all 12 prompt-producing agent files, while keeping `complete_report.md` in markdown-only mode with all highlight blocks stripped.

### Deliverables
- 12 modified agent prompt files with JSON highlights schema appended to prompts
- `web/frontend/lib/highlights.ts` — parser/strip utility (extract JSON block, validate, type-safe, strip all blocks for complete report mode)
- `web/frontend/components/HighlightCards.tsx` — renders highlight cards from parsed data
- Updated `web/frontend/components/MarkdownContent.tsx` — integrates parser/stripper + highlight cards
- Updated `web/frontend/components/ReportViewer.tsx` — passes complete-vs-subreport highlight mode
- Updated `web/frontend/app/globals.css` — highlight card styles

### Definition of Done (verifiable conditions with commands)
1. `cd web/frontend && npm run lint` exits 0
2. `cd web/frontend && npm run build` exits 0 (Next.js production build succeeds)
3. All 12 modified Python prompt files import successfully
4. `grep -rl "json-highlights" tradingagents/agents/ | wc -l` returns 12
5. Individual report views render highlight cards for reports with a valid JSON block
6. Complete report view renders no highlight cards and no raw `json-highlights` blocks
7. Frontend renders original markdown unchanged for reports without JSON block (old reports)
8. Individual report views render original markdown unchanged for malformed JSON blocks
9. At least one newly generated report is verified end-to-end; if runtime generation cannot be executed in the environment, do not mark the feature complete

### Must Have
- Per-category highlight schemas for all 12 prompt producers / 9 UI category types
- Signal/decision badge (BUY/HOLD/SELL) prominently displayed
- Fail-open parsing: invalid/missing JSON → graceful fallback to markdown-only
- Bilingual support: English schema keys and enum literals, free-form values in report language
- Complete report view strips all `json-highlights` blocks and stays markdown-only
- Responsive design matching existing glass-panel aesthetic

### Must NOT Have (guardrails)
- No backend API changes
- No AgentState schema changes
- No old report backward compatibility processing
- No `dangerouslySetInnerHTML` or rehype-raw
- No new npm dependencies (use existing react-markdown, remark-gfm, tailwind)
- No test infrastructure setup (no jest/vitest config changes)
- No modification to `complete_report.md` generation logic

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after + static verification + runtime generation check
- Static QA policy: lint, typecheck/build, prompt import checks, grep/file-scope checks are mandatory
- Runtime QA policy: generate at least one fresh report through the existing pipeline if current environment supports it; if generation is blocked by credentials/network/runtime limits, stop and report the feature as runtime-unverified rather than claiming completion
- UI QA policy: use existing browser tooling or existing Playwright setup if already available; do NOT add new browser test infrastructure as part of this feature
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves

**Wave 0: Baseline Validation** (1 task)
- Task 0: Record current frontend baseline (`lint`, `build`) and confirm whether any standalone `@/lib/api` alias issue reproduces outside the sandbox. No product code change unless the bug is independently reproduced.

**Wave 1: Foundation** (1 task)
- Task 1: Highlight schema types + parser utility (`highlights.ts`) — covers all 12 prompt producers / 9 UI category types

**Wave 2: Prompt modifications** (12 tasks, fully parallel)
- Task 2: Market analyst prompt
- Task 3: Fundamentals analyst prompt
- Task 4: Social media analyst prompt
- Task 5: News analyst prompt
- Task 6: Bull researcher prompt
- Task 7: Bear researcher prompt
- Task 8: Research manager prompt
- Task 9: Trader prompt
- Task 10: Aggressive debator prompt
- Task 11: Conservative debator prompt
- Task 12: Neutral debator prompt
- Task 13: Risk manager prompt (portfolio decision)

**Wave 3: Frontend components** (2 parallel tasks + 1 integration task)
- Task 14: HighlightCards component (expanded for all categories)
- Task 16: CSS styles for highlight cards
- Task 15: Integrate into MarkdownContent + ReportViewer updates

**Wave 4: Verification** (final verification wave)
- F1-F4: Standard final verification agents

### Dependency Matrix
| Task | Depends On | Blocks |
|------|-----------|--------|
| 0 (Baseline validation) | — | none |
| 1 (Schema + Parser) | — | 2-13,14,15,16 |
| 2-13 (All prompts) | 1 | Final verification |
| 14 (HighlightCards) | 1 | 15 |
| 16 (CSS) | 1 | 15 |
| 15 (Integration) | 1,14,16 | Final verification |

## TODOs

- [x] 0. Record Frontend Baseline + Alias Repro Status

  **What to do**:
  Record the current frontend baseline before feature work:
  - Run `cd web/frontend && npm run lint`
  - Run `cd web/frontend && npm run build`
  - Record whether a real `@/lib/api` alias issue can be reproduced outside the sandboxed environment

  This task is a validation gate, not a product change. The current repository already resolves `@/lib/api` for lint/build, so do **not** edit `next.config.ts` unless the alias bug is independently reproduced with a concrete stack trace.

  **Must NOT do**:
  - Do NOT change the project structure or move files
  - Do NOT remove the `@/*` path alias from `tsconfig.json`
  - Do NOT add speculative Turbopack config just because the issue was mentioned in planning

  **Parallelization**: Can Parallel: NO | Wave 0 | Blocks: none | Blocked By: none

  **Acceptance Criteria**:
  - [ ] `cd web/frontend && npm run lint` exits 0
  - [ ] `cd web/frontend && npm run build` exits 0
  - [ ] Any alias failure is either reproduced with exact evidence or explicitly marked as not reproduced

  **Commit**: NO

- [x] 1. Define Highlight Schema Types + Parser Utility

  **What to do**:
  Create `web/frontend/lib/highlights.ts` containing:

  1. TypeScript interfaces for **all** category highlight schemas:

  ```typescript
  // Common fields across all categories
  interface BaseHighlights {
    signal: "BUY" | "HOLD" | "SELL";
    signal_confidence?: "high" | "medium" | "low";
    summary: string; // 1-2 sentence executive summary
  }

  // === ANALYST SCHEMAS (1_analysts/) ===

  interface MarketHighlights extends BaseHighlights {
    category: "market";
    trend_direction: "bullish" | "bearish" | "neutral" | "mixed";
    key_levels: {
      support: string[];
      resistance: string[];
    };
    indicators: Array<{
      name: string;
      value: string;
      interpretation: string;
    }>;
    volatility?: string;
  }

  interface FundamentalsHighlights extends BaseHighlights {
    category: "fundamentals";
    metrics: Array<{
      name: string;
      value: string;
      assessment: string;
    }>;
    financial_health?: string;
  }

  interface SentimentHighlights extends BaseHighlights {
    category: "sentiment";
    overall_sentiment: "positive" | "negative" | "neutral" | "mixed";
    sentiment_score?: string;
    key_topics: string[];
    social_buzz?: string;
  }

  interface NewsHighlights extends BaseHighlights {
    category: "news";
    market_impact: "positive" | "negative" | "neutral" | "mixed";
    key_events: Array<{
      event: string;
      impact: string;
    }>;
    macro_outlook?: string;
  }

  // === RESEARCHER SCHEMAS (2_research/) ===

  interface ResearcherHighlights extends BaseHighlights {
    category: "bull_case" | "bear_case";
    stance: "bullish" | "bearish";
    key_arguments: Array<{
      point: string;
      evidence: string;
    }>;
    counterpoints?: string[];
  }

  interface ResearchManagerHighlights extends BaseHighlights {
    category: "research_decision";
    decision: "BUY" | "HOLD" | "SELL";
    aligned_with: "bull" | "bear";
    rationale: string;
    action_items: string[];
  }

  // === TRADER SCHEMA (3_trading/) ===

  interface TraderHighlights extends BaseHighlights {
    category: "trader";
    decision: "BUY" | "HOLD" | "SELL";
    entry_exit: {
      action: string;
      exit_target?: string;
      stop_loss?: string;
      re_entry?: string;
    };
    risk_factors: string[];
  }

  // === RISK DEBATE SCHEMAS (4_risk/) ===

  interface RiskDebateHighlights extends BaseHighlights {
    category: "risk_aggressive" | "risk_conservative" | "risk_neutral";
    stance_label: string;
    core_argument: string;
    risk_assessment: "high" | "moderate" | "low";
    key_recommendations: string[];
  }

  // === PORTFOLIO DECISION SCHEMA (5_portfolio/) ===

  interface PortfolioDecisionHighlights extends BaseHighlights {
    category: "portfolio_decision";
    final_decision: "BUY" | "HOLD" | "SELL";
    decision_basis: string;
    strategic_actions: Array<{
      action: string;
      priority: string;
    }>;
    risk_warnings: string[];
  }

  type ReportHighlights =
    | MarketHighlights | FundamentalsHighlights | SentimentHighlights | NewsHighlights
    | ResearcherHighlights | ResearchManagerHighlights
    | TraderHighlights
    | RiskDebateHighlights
    | PortfolioDecisionHighlights;
  ```

  2. Parser functions:
  ```typescript
  export function parseHighlights(markdown: string): {
    highlights: ReportHighlights | null;
    cleanMarkdown: string;
  }

  export function stripHighlightsBlocks(markdown: string): string;
  ```

  3. Parsing/stripping rules:
     - Find FIRST occurrence of ` ```json-highlights ` fence
     - Extract content between opening fence and next ` ``` ` closing fence
     - Parse as JSON, validate required fields (`signal`, `summary`, `category`)
     - Validate enum literals as stable English constants (`BUY`, `HOLD`, `SELL`, `bullish`, `bearish`, etc.)
     - If valid: return parsed highlights + markdown with that block stripped
     - If invalid/missing: return null highlights + original markdown unchanged
     - FALLBACK: If `signal` is missing from JSON, attempt regex extraction of `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**` from full markdown
     - `stripHighlightsBlocks(markdown)` removes ALL `json-highlights` fenced blocks, regardless of whether their payload parses, and is used only for `complete_report.md`

  **Must NOT do**:
  - Do NOT add any new npm dependencies
  - Do NOT modify any backend files
  - Do NOT use `eval()` or unsafe parsing

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2-16 | Blocked By: none

  **References**:
  - Pattern: `web/frontend/lib/api.ts:1-70` — existing lib utility pattern
  - Sample: `reports/SPY_20260311_222019/1_analysts/market.md` — actual report format
  - Complete report assembly: `cli/main.py:724-726` — confirms `complete_report.md` is a concatenation of subreports

  **Acceptance Criteria**:
  - [ ] File `web/frontend/lib/highlights.ts` exists and exports `parseHighlights`, `stripHighlightsBlocks`, and all type interfaces
  - [ ] `cd web/frontend && npx tsc --noEmit` exits 0
  - [ ] `cd web/frontend && npm run lint` exits 0

  **Commit**: YES | Message: `feat(highlights): add highlight schema types and parser utility` | Files: [`web/frontend/lib/highlights.ts`]

### Shared Prompt Rules (Tasks 2-13)

- Every prompt must explicitly say: keep the `json-highlights` fence, JSON keys, and enum literals in English exactly as shown, even when the rest of the report is in Chinese.
- Free-form string values inside the JSON block should follow the report language (`en` or `zh-CN`).
- Prompts that currently require "without special formatting" must be revised to mean: narrative stays conversational/plain, then append one final `json-highlights` block.
- Prompts that currently require `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**` must preserve that line as the final narrative line, then append the JSON block after it.
- Do not add more than one `json-highlights` block per report.

- [x] 2. Modify Market Analyst Prompt

  **What to do**:
  Edit `tradingagents/agents/analysts/market_analyst.py` line 49 to append instructions for the structured JSON highlights block after the existing "Markdown table" instruction.

  Add this text after the existing `Make sure to append a Markdown table...` line:

  ```
  After the markdown table, also append a structured highlights block in the following exact format (replace values with your actual analysis findings). This block MUST use the json-highlights code fence:

  \`\`\`json-highlights
  {
    "category": "market",
    "signal": "BUY or HOLD or SELL",
    "signal_confidence": "high or medium or low",
    "summary": "1-2 sentence executive summary of your analysis",
    "trend_direction": "bullish or bearish or neutral or mixed",
    "key_levels": {
      "support": ["level1", "level2"],
      "resistance": ["level1", "level2"]
    },
    "indicators": [
      {"name": "indicator name", "value": "current value", "interpretation": "brief meaning"}
    ],
    "volatility": "high or moderate or low"
  }
  \`\`\`
  ```

  **Must NOT do**:
  - Do NOT change the core analysis instructions (lines 24-48)
  - Do NOT modify the prompt template structure (lines 52-68)
  - Do NOT change any tool bindings or function signature
  - Do NOT remove the existing "Markdown table" instruction

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: none | Blocked By: 1

  **References**:
  - Pattern: `tradingagents/agents/analysts/market_analyst.py:23-50` — current prompt structure

  **Acceptance Criteria**:
  - [ ] `market_analyst.py` contains `json-highlights` fence instruction text
  - [ ] `market_analyst.py` still contains original "Markdown table" instruction
  - [ ] `python -c "from tradingagents.agents.analysts.market_analyst import create_market_analyst"` exits 0

  **Commit**: YES | Message: `feat(prompts): add structured highlights schema to market analyst prompt` | Files: [`tradingagents/agents/analysts/market_analyst.py`]

- [x] 3. Modify Fundamentals Analyst Prompt

  **What to do**:
  Edit `tradingagents/agents/analysts/fundamentals_analyst.py` line 28.

  Add after the existing "Markdown table" instruction:

  ```
  After the markdown table, also append a structured highlights block in the following exact format:

  \`\`\`json-highlights
  {
    "category": "fundamentals",
    "signal": "BUY or HOLD or SELL",
    "signal_confidence": "high or medium or low",
    "summary": "1-2 sentence executive summary of fundamental analysis",
    "metrics": [
      {"name": "metric name", "value": "current value", "assessment": "brief assessment"}
    ],
    "financial_health": "strong or moderate or weak"
  }
  \`\`\`
  ```

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocked By: 1

  **Acceptance Criteria**:
  - [ ] `fundamentals_analyst.py` contains `json-highlights` fence
  - [ ] `python -c "from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst"` exits 0

  **Commit**: YES | Message: `feat(prompts): add structured highlights schema to fundamentals analyst prompt`

- [x] 4. Modify Social Media Analyst Prompt

  **What to do**:
  Edit `tradingagents/agents/analysts/social_media_analyst.py` line 19.

  Add after the existing "Markdown table" instruction:

  ```
  After the markdown table, also append a structured highlights block:

  \`\`\`json-highlights
  {
    "category": "sentiment",
    "signal": "BUY or HOLD or SELL",
    "signal_confidence": "high or medium or low",
    "summary": "1-2 sentence executive summary of sentiment analysis",
    "overall_sentiment": "positive or negative or neutral or mixed",
    "sentiment_score": "score like 65/100 if determinable",
    "key_topics": ["topic1", "topic2", "topic3"],
    "social_buzz": "high or moderate or low"
  }
  \`\`\`
  ```

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocked By: 1

  **Commit**: YES | Message: `feat(prompts): add structured highlights schema to social media analyst prompt`

- [x] 5. Modify News Analyst Prompt

  **What to do**:
  Edit `tradingagents/agents/analysts/news_analyst.py` line 23.

  ```
  \`\`\`json-highlights
  {
    "category": "news",
    "signal": "BUY or HOLD or SELL",
    "signal_confidence": "high or medium or low",
    "summary": "1-2 sentence executive summary of news analysis",
    "market_impact": "positive or negative or neutral or mixed",
    "key_events": [
      {"event": "event description", "impact": "brief market impact assessment"}
    ],
    "macro_outlook": "cautious or optimistic or pessimistic or neutral"
  }
  \`\`\`
  ```

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocked By: 1

  **Commit**: YES | Message: `feat(prompts): add structured highlights schema to news analyst prompt`

- [x] 6. Modify Bull Researcher Prompt

  **What to do**:
  Edit `tradingagents/agents/researchers/bull_researcher.py`. In the f-string prompt (line 25-44), insert the following block before `{language_instruction}` (line 43):

  ```
  After your complete analysis, append a structured highlights block in the following exact format:

  \`\`\`json-highlights
  {
    "category": "bull_case",
    "signal": "BUY or HOLD or SELL",
    "signal_confidence": "high or medium or low",
    "summary": "1-2 sentence executive summary of your bull case",
    "stance": "bullish",
    "key_arguments": [
      {"point": "core argument title", "evidence": "supporting evidence or data"}
    ],
    "counterpoints": ["rebuttal to bear argument 1", "rebuttal 2"]
  }
  \`\`\`
  ```

  **Must NOT do**:
  - Do NOT change the core analysis instructions or debate logic
  - Do NOT modify the state management (`new_investment_debate_state`)
  - Do NOT change the `Bull Analyst:` prefix in the argument formatting

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocked By: 1

  **References**:
  - Pattern: `tradingagents/agents/researchers/bull_researcher.py:25-44` — f-string prompt

  **Acceptance Criteria**:
  - [ ] `bull_researcher.py` contains `json-highlights` fence
  - [ ] `python -c "from tradingagents.agents.researchers.bull_researcher import create_bull_researcher"` exits 0

  **Commit**: YES | Message: `feat(prompts): add structured highlights schema to bull researcher prompt`

- [x] 7. Modify Bear Researcher Prompt

  **What to do**:
  Edit `tradingagents/agents/researchers/bear_researcher.py`. Same pattern as Task 6, but with `category: "bear_case"` and `stance: "bearish"`.

  Insert before `{language_instruction}` (line 45):

  ```
  After your complete analysis, append a structured highlights block:

  \`\`\`json-highlights
  {
    "category": "bear_case",
    "signal": "BUY or HOLD or SELL",
    "signal_confidence": "high or medium or low",
    "summary": "1-2 sentence executive summary of your bear case",
    "stance": "bearish",
    "key_arguments": [
      {"point": "core argument title", "evidence": "supporting evidence or data"}
    ],
    "counterpoints": ["rebuttal to bull argument 1", "rebuttal 2"]
  }
  \`\`\`
  ```

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocked By: 1

  **Commit**: YES | Message: `feat(prompts): add structured highlights schema to bear researcher prompt`

- [x] 8. Modify Research Manager Prompt

  **What to do**:
  Edit `tradingagents/agents/managers/research_manager.py`. Replace the existing "without special formatting" wording so it explicitly allows one trailing `json-highlights` block, then insert the block before `{language_instruction}` in the prompt (line 40):

  ```
  After your complete decision, append a structured highlights block:

  \`\`\`json-highlights
  {
    "category": "research_decision",
    "signal": "BUY or HOLD or SELL",
    "signal_confidence": "high or medium or low",
    "summary": "1-2 sentence executive summary of your ruling",
    "decision": "BUY or HOLD or SELL",
    "aligned_with": "bull or bear",
    "rationale": "one sentence explaining why you sided this way",
    "action_items": ["action 1", "action 2", "action 3"]
  }
  \`\`\`
  ```

  **Must NOT do**:
  - Do NOT change the `investment_plan` state output
  - Do NOT modify the debate facilitation logic

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocked By: 1

  **Acceptance Criteria**:
  - [ ] `research_manager.py` contains `json-highlights` fence
  - [ ] `research_manager.py` no longer forbids a trailing structured block via "without special formatting" wording

  **Commit**: YES | Message: `feat(prompts): add structured highlights schema to research manager prompt`

- [x] 9. Modify Trader Prompt

  **What to do**:
  Edit `tradingagents/agents/trader/trader.py`. Revise the system message so that:
  - the report still includes `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`
  - that line remains the **final narrative line**
  - one trailing `json-highlights` block is appended after that line

  Do not merely append a conflicting sentence after the current "always conclude your response" wording; rewrite the instruction so the contract is internally consistent.

  ```
  Also append a structured highlights block at the end of your response:

  \`\`\`json-highlights
  {
    "category": "trader",
    "signal": "BUY or HOLD or SELL",
    "signal_confidence": "high or medium or low",
    "summary": "1-2 sentence executive summary of your trading decision",
    "decision": "BUY or HOLD or SELL",
    "entry_exit": {
      "action": "core trading action description",
      "exit_target": "target exit price or condition",
      "stop_loss": "stop loss level",
      "re_entry": "conditions for re-entry"
    },
    "risk_factors": ["risk 1", "risk 2"]
  }
  \`\`\`
  ```

  **Must NOT do**:
  - Do NOT remove the `FINAL TRANSACTION PROPOSAL` requirement
  - Do NOT modify the message list structure or `functools.partial` pattern
  - Do NOT change the `trader_investment_plan` state output

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocked By: 1

  **Acceptance Criteria**:
  - [ ] `trader.py` contains `json-highlights` fence
  - [ ] `trader.py` explicitly preserves `FINAL TRANSACTION PROPOSAL` as the last narrative line before the JSON block

  **Commit**: YES | Message: `feat(prompts): add structured highlights schema to trader prompt`

- [x] 10. Modify Aggressive Debator Prompt

  **What to do**:
  Edit `tradingagents/agents/risk_mgmt/aggressive_debator.py`. Replace the existing "without special formatting" wording so it allows one trailing `json-highlights` block, then insert the block before `{language_instruction}` (line 37):

  ```
  After your complete argument, append a structured highlights block:

  \`\`\`json-highlights
  {
    "category": "risk_aggressive",
    "signal": "BUY or HOLD or SELL",
    "signal_confidence": "high or medium or low",
    "summary": "1-2 sentence summary of your aggressive risk stance",
    "stance_label": "Aggressive",
    "core_argument": "one sentence core thesis",
    "risk_assessment": "high or moderate or low",
    "key_recommendations": ["recommendation 1", "recommendation 2"]
  }
  \`\`\`
  ```

  **Must NOT do**:
  - Do NOT change the debate state management
  - Do NOT modify the `Aggressive Analyst:` prefix

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocked By: 1

  **Acceptance Criteria**:
  - [ ] `aggressive_debator.py` contains `json-highlights` fence
  - [ ] `aggressive_debator.py` no longer forbids a trailing structured block via "without special formatting" wording

  **Commit**: YES | Message: `feat(prompts): add structured highlights schema to aggressive debator prompt`

- [x] 11. Modify Conservative Debator Prompt

  **What to do**:
  Edit `tradingagents/agents/risk_mgmt/conservative_debator.py`. Same pattern as Task 10 with `category: "risk_conservative"` and `stance_label: "Conservative"`, including replacement of any wording that would forbid a trailing structured block.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocked By: 1

  **Commit**: YES | Message: `feat(prompts): add structured highlights schema to conservative debator prompt`

- [x] 12. Modify Neutral Debator Prompt

  **What to do**:
  Edit `tradingagents/agents/risk_mgmt/neutral_debator.py`. Same pattern as Task 10 with `category: "risk_neutral"` and `stance_label: "Neutral"`, including replacement of any wording that would forbid a trailing structured block.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocked By: 1

  **Commit**: YES | Message: `feat(prompts): add structured highlights schema to neutral debator prompt`

- [x] 13. Modify Risk Manager (Portfolio Decision) Prompt

  **What to do**:
  Edit `tradingagents/agents/managers/risk_manager.py`. Insert before `{language_instruction}` (line 46):

  ```
  After your complete decision, append a structured highlights block:

  \`\`\`json-highlights
  {
    "category": "portfolio_decision",
    "signal": "BUY or HOLD or SELL",
    "signal_confidence": "high or medium or low",
    "summary": "1-2 sentence executive summary of your final ruling",
    "final_decision": "BUY or HOLD or SELL",
    "decision_basis": "one sentence explaining the primary reason",
    "strategic_actions": [
      {"action": "action description", "priority": "immediate or conditional or long-term"}
    ],
    "risk_warnings": ["warning 1", "warning 2"]
  }
  \`\`\`
  ```

  **Must NOT do**:
  - Do NOT change the `final_trade_decision` state output
  - Do NOT modify the risk debate state management

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocked By: 1

  **Commit**: YES | Message: `feat(prompts): add structured highlights schema to risk manager prompt`

- [x] 14. Build HighlightCards Component

  **What to do**:
  Create `web/frontend/components/HighlightCards.tsx` — a React component that renders structured highlight data as visually prominent cards. Must handle **all 9 category types**.

  Component design:

  1. **Signal Badge** (always shown): BUY (green), HOLD (amber), SELL (red)
  2. **Executive Summary** (always shown)
  3. **Category-specific cards**:
     - **Market**: Trend badge, key levels grid, indicators table, volatility
     - **Fundamentals**: Financial health badge, metrics grid
     - **Sentiment**: Sentiment badge, score, topic tag pills, social buzz
     - **News**: Market impact badge, key events list, macro outlook
     - **Bull/Bear Case**: Stance badge, key arguments list with evidence, counterpoints
     - **Research Decision**: Decision badge, aligned_with indicator, action items
     - **Trader**: Decision badge, entry/exit strategy card, risk factors
     - **Risk Debate** (aggressive/conservative/neutral): Stance label badge, core argument, recommendations
     - **Portfolio Decision**: Final decision badge, strategic actions timeline, risk warnings

  4. **Layout**: CSS Grid, responsive (1 col mobile, 2-3 col desktop)

  **Must NOT do**:
  - Do NOT use `dangerouslySetInnerHTML`
  - Do NOT add new npm dependencies
  - Do NOT hardcode colors — use CSS variables

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 15 | Blocked By: 1

  **Commit**: YES | Message: `feat(ui): add HighlightCards component for structured report highlights`

- [x] 15. Integrate Highlights into MarkdownContent + ReportViewer

  **What to do**:

  **A. Update `MarkdownContent.tsx`**:
  1. Import `parseHighlights` from `@/lib/highlights`
  2. Import `stripHighlightsBlocks` from `@/lib/highlights`
  3. Import `HighlightCards` from `@/components/HighlightCards`
  4. Add a prop such as `highlightMode?: "single" | "off"` to distinguish individual reports from `complete_report.md`
  5. In `useMemo`, call `parseHighlights(content)` only when `highlightMode === "single"`
  6. When `highlightMode === "off"`, call `stripHighlightsBlocks(content)` and render markdown only
  7. Render `HighlightCards` above `ReactMarkdown` only when highlights are non-null
  8. Pass cleaned markdown to `ReactMarkdown`

  **B. Update `ReportViewer.tsx`**:
  1. Pass `highlightMode="off"` for the `complete_report.md` tab
  2. Pass `highlightMode="single"` for individual subreports
  3. Keep all existing loading, request de-duping, tab navigation, and skeleton behavior unchanged

  **Must NOT do**:
  - Do NOT change loading skeleton, overlay, or memoization behavior
  - Do NOT change ReportViewer's tab navigation or async loading

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: none | Blocked By: 1, 14, 16

  **Commit**: YES | Message: `feat(ui): integrate highlight cards into MarkdownContent renderer`

- [x] 16. Add CSS Styles for Highlight Cards

  **What to do**:
  Add styles to `web/frontend/app/globals.css` for all highlight card variants. Place after existing `.markdown-content` styles.

  Required style classes:
  - `.signal-badge`, `.signal-buy`, `.signal-hold`, `.signal-sell`
  - `.highlights-container`, `.highlight-summary`, `.highlight-card`
  - `.highlight-badge`, `.highlight-tag`, `.highlight-metric`, `.highlight-table`
  - `.stance-bullish`, `.stance-bearish` (for researcher cards)
  - `.priority-immediate`, `.priority-conditional`, `.priority-longterm` (for portfolio actions)

  **Design constraints**:
  - Use existing CSS variables: `--primary`, `--accent`, `--success`, `--border`, etc.
  - Follow `card-surface` and `glass-panel` patterns
  - Responsive: 1 column mobile, 2-3 columns desktop
  - Include `@media (prefers-reduced-motion: reduce)`

  **Must NOT do**:
  - Do NOT modify existing CSS rules
  - Do NOT use !important
  - Do NOT hardcode colors

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 15 | Blocked By: 1

  **Commit**: YES | Message: `feat(ui): add CSS styles for highlight cards and signal badges`

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
> **Status update (2026-03-13):**
> - Static verification completed locally: `npm run lint`, `npm run build`, prompt-file `py_compile`, `json-highlights` grep count = 12, and a runtime regression unittest covering the f-string prompt nodes with embedded JSON blocks.
> - Fresh runtime generation was verified locally with a minimal real pipeline run: `TradingAgentsGraph(selected_analysts=['market'])` generated a new report set under `/tmp/report-highlights-e2e`.
> - Generated output evidence: 9/9 subreports contained `json-highlights`; `complete_report.md` also contained the blocks as expected from raw concatenation.
> - Frontend parser evidence: `parseHighlights()` successfully parsed and stripped the generated `market.md` block; `stripHighlightsBlocks()` removed all highlight blocks from the generated `complete_report.md`.
> - Browser navigation / viewport-specific QA was not executed in this environment, so the final-wave checkboxes remain intentionally unchecked.

- [ ] F1. Plan Compliance Audit — oracle
  Verify all tasks executed match plan. No scope creep. No files modified outside plan scope. Confirm Task 0 remained validation-only unless a real alias bug was reproduced.

- [ ] F2. Code Quality Review — unspecified-high
  Review all modified/created files for: TypeScript types correctness, no `any` types, proper memoization, no security issues, consistent code style.

- [ ] F3. Runtime + UI QA — unspecified-high (+ browser tooling if already available)
  Start the existing app stack if the environment supports it. Navigate through ALL existing reports and verify they render unchanged. Generate at least one fresh report through the real pipeline and verify:
  - individual subreports render highlight cards correctly
  - malformed/no-highlight subreports fall back cleanly
  - `complete_report.md` renders with no cards and no raw `json-highlights` blocks
  - mobile viewport remains usable
  Use Playwright only if it is already configured; do not add browser test infra as part of this feature.

- [ ] F4. Scope Fidelity Check — deep
  Verify: no backend files modified, no AgentState changes, no new npm dependencies, no `complete_report.md` generation logic touched. Only the 12 prompt files + frontend files changed.

## Commit Strategy
Task 0 is validation-only and does not get a commit. Every code-changing task gets its own conventional-commit message. Final squash optional.

1. `feat(highlights): add highlight schema types and parser utility`
2. `feat(prompts): add structured highlights schema to market analyst prompt`
3. `feat(prompts): add structured highlights schema to fundamentals analyst prompt`
4. `feat(prompts): add structured highlights schema to social media analyst prompt`
5. `feat(prompts): add structured highlights schema to news analyst prompt`
6. `feat(prompts): add structured highlights schema to bull researcher prompt`
7. `feat(prompts): add structured highlights schema to bear researcher prompt`
8. `feat(prompts): add structured highlights schema to research manager prompt`
9. `feat(prompts): add structured highlights schema to trader prompt`
10. `feat(prompts): add structured highlights schema to aggressive debator prompt`
11. `feat(prompts): add structured highlights schema to conservative debator prompt`
12. `feat(prompts): add structured highlights schema to neutral debator prompt`
13. `feat(prompts): add structured highlights schema to risk manager prompt`
14. `feat(ui): add HighlightCards component for structured report highlights`
15. `feat(ui): integrate highlight cards into MarkdownContent renderer`
16. `feat(ui): add CSS styles for highlight cards and signal badges`

## Success Criteria
1. All 12 prompt-produced subreports contain parseable `json-highlights` blocks when newly generated
2. Frontend renders highlight cards with signal badge, summary, and category-specific metrics above markdown for every individual subreport type
3. `complete_report.md` stays readable: no highlight cards, no raw `json-highlights` blocks
4. Old reports render exactly as before when no highlight block is present
5. `npm run build` succeeds with zero errors
6. `npm run lint` passes
7. All 12 Python prompt files import successfully
8. No new npm dependencies added
9. No backend API changes
10. `complete_report.md` generation logic untouched
11. At least one fresh end-to-end generated report is verified, or the work is explicitly marked runtime-unverified
