# Diverge Decision Card Development Notes

## Scope

The MVP implements one final `DecisionCard` per completed single-stock analysis. Agent outputs remain evidence inputs; the displayed final card is derived from the Portfolio Manager final ruling and persisted as:

```text
reports/{report_id}/artifacts/decision_card.json
```

## Flow

```text
Portfolio Manager output
  -> json-decision-card
  -> json-highlights fallback
  -> unstructured rating fallback
  -> low-confidence fallback card
  -> quality gates
  -> artifacts/decision_card.json
  -> report structure artifact scan
  -> ReportViewer complete-report DecisionCard
```

Decision card generation is intentionally non-blocking. If structured card generation fails, the full markdown report still saves and a low-confidence fallback card is written when possible.

## Rating And Action

Ratings use the five-level portfolio scale:

```text
BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL
```

Actions are separate execution instructions:

```text
OPEN / ADD / MAINTAIN / TRIM / EXIT / WATCH / NO_ACTION / AVOID
```

The backend quality gates correct obvious conflicts such as `SELL + ADD`, `UNDERWEIGHT + OPEN`, and `BUY + EXIT`.

## Quality Gates

The MVP applies these safeguards before persistence:

```text
1. rating/action consistency correction
2. removal of stop-loss/take-profit levels when current_price is unavailable
3. BUY/OVERWEIGHT entry and invalidation checks
4. WATCH condition checks
5. evidence and risk completeness notes
6. confidence downgrade when quality issues accumulate
7. conviction_score recalibration
```

`conviction_score` is a multi-agent conviction score, not an upside probability.

## Frontend Behavior

`ReportViewer` checks the report structure for an artifact with `type === "decision_card"`. When present, it fetches and validates `artifacts/decision_card.json`, renders the final `DecisionCard` above the complete markdown report, and disables markdown highlight cards to avoid duplicate final rulings.

If the artifact is absent or invalid, the complete markdown report falls back to the existing `json-highlights` cards.

## Intelligence Layer v1.1 Scope

DecisionCard v1.1 keeps the single final Portfolio Manager ruling as the
source of truth, while adding a compact decision layer above the full markdown
report. The card should answer whether the decision is actionable, why it is not
more bullish or bearish, what to do next, how to think about generic sizing, and
how the verdict changed from the last visible analysis of the same ticker.

Included in v1.1:

```text
Trade Readiness
Data Quality Badge
Why Not
Action Playbook
Position Guidance, shown as a lightweight generic line
Decision Delta, written as a separate lightweight artifact when local history exists
```

Excluded from v1.1:

```text
Portfolio Fit
Decision Journal
Opportunity Queue / report-list ranking
Confidence Breakdown
Catalyst Calendar
Re-analysis Triggers
Evidence Trace
Contradiction Map
Thesis Validity Monitor
```

The Portfolio Manager may still consider provided portfolio context when
calibrating the final `rating` and `action`, because not every user records
holdings in Diverge. However, the new DecisionCard intelligence fields must not
turn into a Portfolio Fit feature. `position_guidance` must stay generic and
risk-based, and must not assume the user has a current position.

### v1.1 Display Rules

The default card should stay compact:

```text
1. Header verdict:
   rating, action, conviction, confidence, trade readiness, data quality
2. One-line summary below the header
3. Since Last Analysis strip, only when decision_delta.json exists
4. Why Not, always showing the three fixed questions
5. Action Playbook, always showing Do Now / Trigger / Invalidation
6. Position Guidance, as a one-line generic sizing/risk note
```

Detailed thesis text, price-plan details, key evidence, key risks,
catalysts/watch items, data-quality notes, and raw structured JSON should remain
available but folded or visually secondary.

### v1.1 Backend Rules

DecisionCard generation remains non-blocking:

```text
Portfolio Manager output
  -> parser
  -> deterministic enrichment and quality gates
  -> artifacts/decision_card.json
  -> optional local-history delta
  -> artifacts/decision_delta.json
```

Only the final gated card is persisted. Diverge does not write raw or enriched
intermediate DecisionCard artifacts.

The Portfolio Manager should generate the new optional fields when possible, but
the backend is the final authority for:

```text
data_quality_level
trade_readiness
rating/action consistency
price-plan safety when current_price is unavailable
position_guidance wording safety
```

Backend enrichment should normalize, validate, and fill missing fields. It
should not rewrite otherwise acceptable Portfolio Manager prose. Fallback prose
should follow the report `output_language`; enum values stay in English and are
localized only in the frontend display layer.

`data_quality_level` is resolved by worst applicable condition:

```text
insufficient
weak
partial
complete
```

Only `insufficient` forces `trade_readiness = DATA_INSUFFICIENT`. A `weak` data
quality level should be reflected in the readiness reason or blocking items
without automatically overriding the action-derived readiness state.

### Decision Delta v1.1

`decision_delta.json` is a separate derived artifact, generated only when a
local prior DecisionCard exists for the same ticker in the current visible
scope. The MVP does not actively download or query remote storage history.

The delta compares only stable fields:

```text
rating
action
conviction_score
confidence
trade_readiness
```

It does not include semantic reason diffs, new/resolved risk analysis, thesis
diffing, or a second LLM pass. The frontend should render it as a lightweight
"Since Last Analysis" strip with folded details and hide unchanged fields.
