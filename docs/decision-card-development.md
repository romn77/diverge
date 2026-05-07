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
