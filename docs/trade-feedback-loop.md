# Trade Feedback Loop

Phase 1 stores manual trade records and structured reviews as files under the existing reports root.

## Directory contract

```
reports/
├── .trade_feedback/
│   └── {TICKER}/
│       └── {trade_id}/
│           ├── trade_record.json
│           └── reviews/
│               ├── entry_review.json
│               └── exit_review.json
└── {report_id}/
    └── artifacts/
        ├── thesis.json
        └── trade_feedback.json   # present when historical review injection was used
```

`trade_id` is a stable UUID-like identifier generated once on create and preserved on update.

## Schemas

`trade_record.json` fields:

- `trade_id`
- `ticker`
- `exchange_or_market`
- `side`
- `status`
- `entry_timestamp`
- `entry_price`
- `exit_timestamp`
- `exit_price`
- `size`
- `initial_thesis`
- `planned_horizon`
- `stop_loss`
- `take_profit`
- `notes`
- `analysis_references`
- `created_at`
- `updated_at`

`trade_review.json` fields:

- `review_id`
- `trade_id`
- `ticker`
- `review_type`
- `analysis_date`
- `analysis_references`
- `thesis_assessment`
- `timing_assessment`
- `sizing_assessment`
- `discipline_assessment`
- `outcome_summary`
- `improvement_actions`
- `ticker_specific_lessons`
- `cross_ticker_tags`
- `created_at`
- `updated_at`

`analysis_date` stays tied to the analysis snapshot being reviewed. Historical prompt injection visibility is controlled by the saved review timestamps (`updated_at`, with `created_at` fallback) so later backfilled reviews do not leak into earlier analyses.

## Analysis references

Each trade record or review can carry one or more `analysis_references` objects:

```json
{
  "analysis_date": "2026-04-01",
  "report_path": "reports/MSFT_20260401_120000/complete_report.md",
  "full_state_log_path": "eval_results/MSFT/DivergeStrategy_logs/full_states_log_2026-04-01.json"
}
```

Paths are stored relative to the repo root and must remain inside the project workspace.

## Backend endpoints

- `GET /api/trades`
- `POST /api/trades`
- `GET /api/trades/{trade_id}`
- `PUT /api/trades/{trade_id}`
- `GET /api/trades/{trade_id}/reviews`
- `POST /api/trades/{trade_id}/reviews`
- `PUT /api/trades/{trade_id}/reviews/{review_type}`
- `GET /api/trade-feedback/{ticker}?analysis_date=YYYY-MM-DD`

## Prompt injection contract

When a new analysis runs for ticker `T`, the backend loads recent reviews from `reports/.trade_feedback/{T}/...`, filters out any review whose saved visibility timestamp (`updated_at`, with `created_at` fallback) is later than the active analysis date, then builds a prompt block from the structured review fields and injects it into the live analysis state as `historical_trade_feedback`.

That payload is also written to `artifacts/trade_feedback.json` in the generated report so QA can verify which historical feedback was injected.
