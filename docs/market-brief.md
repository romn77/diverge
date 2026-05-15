# Market Brief

Market Brief is a report artifact type separate from single-stock `DecisionCard`.
It generates `artifacts/premarket_brief.json` and `complete_report.md` under a
normal report directory, so existing report listing and artifact APIs can read it.

## Manual Trigger

Use the API or the `/market-briefs` workbench page:

```http
POST /api/market-briefs/tasks
```

```json
{
  "markets": ["cn", "us"],
  "output_language": "zh-CN",
  "report_visibility": "workspace"
}
```

Supported markets:

- `cn`: A-share
- `us`: US

Hong Kong (`hk`) is temporarily disabled until the project has a reliable HKEX
holiday calendar and market data feed.

## Automatic Trigger

The automation provider is ARQ cron. It creates regular `market_brief` tasks in
the existing Redis task queue; the standard backend worker executes them.

Required production settings:

```bash
TASK_BACKEND=redis
REDIS_URL=redis://redis:6379/0
MARKET_BRIEF_ENABLED=true
MARKET_BRIEF_SCHEDULER_PROVIDER=arq
MARKET_BRIEF_TIMES=08:30,09:00,09:20
MARKET_BRIEF_MARKETS=cn,us
MARKET_BRIEF_CN_TIMEZONE=Asia/Shanghai
MARKET_BRIEF_US_TIMEZONE=America/New_York
MARKET_BRIEF_REPORT_VISIBILITY=workspace
MARKET_BRIEF_SCHEDULER_QUEUE_NAME=arq:market-brief:scheduler
```

`MARKET_BRIEF_TIMES` is interpreted in each enabled market's timezone. Override
one market independently with `MARKET_BRIEF_CN_TIMES` or `MARKET_BRIEF_US_TIMES`.
For example, US brief slots use New York time by default.

Run the scheduler with:

```bash
arq web.backend.runtime.market_brief_arq.MarketBriefSchedulerSettings
```

Run the normal task worker with:

```bash
TASK_BACKEND=redis python -m web.backend.worker
```

When auth/database mode is enabled, scheduled reports need an owner for report
metadata. Set `MARKET_BRIEF_OWNER_USER_ID`, or configure the bootstrap admin
environment so the scheduler can use the active admin owner.

## Data Sources

Market Brief uses:

- exchange calendar and open-window context from local calendar code;
- index snapshots via `yfinance` when available;
- Web Search sources via `MARKET_BRIEF_WEB_SEARCH_PROVIDER=auto`, preferring
  OpenAI Responses `web_search` when `OPENAI_API_KEY` is configured, then the
  existing Diverge search providers if configured.

If a source is unavailable, the task still writes a report and records the
missing source in `quality_warnings`.
