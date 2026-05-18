# Market Brief

Market Brief is now an external markdown ingestion surface. Diverge no longer
generates the brief with its own market-data, web-search, scheduler, or LLM agent
pipeline. multica owns report generation; Diverge owns ingestion, indexing,
permissions, and Workbench rendering.

## Source Directory

By default, Diverge reads markdown files from:

```bash
data/market_briefs
```

Override the location with:

```bash
MARKET_BRIEFS_DIR=/srv/diverge/market_briefs
```

Use one markdown file per brief:

```text
YYYY-MM-DD-us-premarket-market-brief.md
YYYY-MM-DD-cn-premarket-market-brief.md
YYYY-MM-DD-global-premarket-market-brief.md
```

The scanner also tolerates legacy `.md.md` filenames, but new files should use a
single `.md` suffix.

## SSH/SFTP Delivery

When multica writes directly to the server, use an atomic upload pattern:

```bash
scp report.md diverge-briefs@server:/srv/diverge/market_briefs/inbox/report.md.tmp
ssh diverge-briefs@server \
  'mv /srv/diverge/market_briefs/inbox/report.md.tmp /srv/diverge/market_briefs/2026-05-18-us-premarket-market-brief.md'
```

The SSH user should be restricted to the brief directory and should not have
write access to application code or secrets.

## Webhook Delivery

multica can also POST markdown to Diverge:

```http
POST /api/integrations/multica/market-brief
X-Multica-Timestamp: 1779093000
X-Multica-Signature: sha256=<hmac>
Content-Type: application/json
```

The signature is:

```text
hex(hmac_sha256(MULTICA_WEBHOOK_SECRET, timestamp + "." + raw_body))
```

Example JSON payload:

```json
{
  "filename": "2026-05-18-us-premarket-market-brief.md",
  "provider_report_id": "multica-20260518-us-am",
  "markets": ["us"],
  "language": "zh-CN",
  "markdown": "# 美股盘前市场简报｜2026-05-18\n\n..."
}
```

Required environment:

```bash
MULTICA_WEBHOOK_SECRET=change-me
MULTICA_WEBHOOK_MAX_SKEW_SECONDS=300
```

Raw `text/markdown` requests are also accepted. For raw uploads, pass the target
filename in `X-Multica-Filename`.

## Workbench Behavior

`GET /api/market-briefs` scans `MARKET_BRIEFS_DIR`, extracts lightweight index
metadata from frontmatter, filename, headings, and markdown links, and returns
the latest seven-day window.

Clicking a brief opens the normal report viewer via a synthetic
`MARKET_BRIEF_...` report id. The report viewer reads the original markdown as
`complete_report.md`; Diverge does not rewrite the multica report with an
internal renderer.

Optional frontmatter improves indexing:

```yaml
---
provider: multica
provider_report_id: multica-20260518-us-am
markets: [us]
trading_day: 2026-05-18
generated_at: 2026-05-18T08:34:00-04:00
language: zh-CN
---
```
