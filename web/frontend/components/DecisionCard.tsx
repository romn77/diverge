import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Gauge,
  ListChecks,
  ShieldAlert,
} from "lucide-react";
import { usePreferences } from "@/components/PreferencesProvider";
import type {
  DecisionCard as DecisionCardModel,
  PortfolioRating,
} from "@/lib/decisionCard";

interface DecisionCardProps {
  card: DecisionCardModel;
}

function ratingClass(rating: PortfolioRating): string {
  switch (rating) {
    case "BUY":
      return "decision-rating--buy";
    case "OVERWEIGHT":
      return "decision-rating--overweight";
    case "HOLD":
      return "decision-rating--hold";
    case "UNDERWEIGHT":
      return "decision-rating--underweight";
    case "SELL":
      return "decision-rating--sell";
    default:
      return "";
  }
}

function formatMarket(
  value: DecisionCardModel["market"],
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return value === "unknown"
    ? t("decisionCard.marketUnknown", "Market unknown")
    : t("decisionCard.marketLabel", ({ market }) => `${market} Market`, {
        market: value.toUpperCase(),
      });
}

function formatPrice(
  value: number | null | undefined,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return typeof value === "number"
    ? String(value)
    : t("decisionCard.notProvided", "Not provided");
}

function formatNumberList(
  values: number[] | null | undefined,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return values && values.length > 0
    ? values.join(" / ")
    : t("decisionCard.notProvided", "Not provided");
}

function renderList(items: string[], emptyLabel: string) {
  if (items.length === 0) {
    return <p className="decision-muted">{emptyLabel}</p>;
  }

  return (
    <ul className="decision-list">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>{item}</li>
      ))}
    </ul>
  );
}

export function DecisionCard({ card }: DecisionCardProps) {
  const { t } = usePreferences();
  const displayName = card.name ? `${card.symbol} / ${card.name}` : card.symbol;
  const plan = card.price_plan;

  return (
    <section
      className={`decision-card ${ratingClass(card.rating)}`}
      aria-label={t("decisionCard.ariaLabel", "Final decision card")}
    >
      <header className="decision-card-header">
        <div className="decision-card-title-block">
          <p className="decision-card-kicker">
            {t("decisionCard.finalRuling", "Final Portfolio Ruling")}
          </p>
          <h3 className="decision-card-title">{displayName}</h3>
          <p className="decision-card-meta">
            {formatMarket(card.market, t)}
            {card.analysis_date ? ` / ${card.analysis_date}` : ""}
          </p>
        </div>

        <div className="decision-verdict-strip">
          <span className="decision-rating">{card.rating}</span>
          <span className="decision-action">{card.action}</span>
        </div>
      </header>

      <div className="decision-card-grid">
        <div className="decision-score-panel">
          <div
            className="decision-score-ring"
            aria-label={t(
              "decisionCard.convictionScore",
              ({ score }) => `Conviction ${score} out of 100`,
              { score: card.conviction_score }
            )}
          >
            <Gauge className="size-5" aria-hidden />
            <span>{card.conviction_score}</span>
          </div>
          <div>
            <p className="decision-panel-label">
              {t("decisionCard.conviction", "Conviction")}
            </p>
            <p className="decision-panel-value">{card.conviction_score} / 100</p>
            <p className="decision-muted">
              {t(
                "decisionCard.confidenceHorizon",
                ({ confidence, horizon }) => `${confidence} confidence / ${horizon}`,
                { confidence: card.confidence, horizon: card.time_horizon }
              )}
            </p>
          </div>
        </div>

        <div className="decision-summary-panel">
          <p className="decision-panel-label">
            {t("decisionCard.summary", "One-line summary")}
          </p>
          <p className="decision-summary">{card.one_line_summary}</p>
          <p className="decision-thesis">{card.thesis}</p>
        </div>
      </div>

      <div className="decision-section-grid">
        <section className="decision-section">
          <div className="decision-section-title">
            <ListChecks className="size-4" aria-hidden />
            {t("decisionCard.executionPlan", "Execution Plan")}
          </div>
          <dl className="decision-plan-list">
            <div>
              <dt>{t("decisionCard.entryAdd", "Entry / Add")}</dt>
              <dd>{plan.add_condition || formatNumberList(plan.entry_zone, t)}</dd>
            </div>
            <div>
              <dt>{t("decisionCard.stopLoss", "Stop Loss")}</dt>
              <dd>{formatPrice(plan.stop_loss, t)}</dd>
            </div>
            <div>
              <dt>{t("decisionCard.takeProfit", "Take Profit")}</dt>
              <dd>{formatNumberList(plan.take_profit, t)}</dd>
            </div>
            {plan.risk_reward_note && (
              <div>
                <dt>{t("decisionCard.riskReward", "Risk / Reward")}</dt>
                <dd>{plan.risk_reward_note}</dd>
              </div>
            )}
            {card.suggested_position && (
              <div>
                <dt>{t("decisionCard.position", "Position")}</dt>
                <dd>{card.suggested_position}</dd>
              </div>
            )}
          </dl>
          <div className="decision-subsection">
            <p className="decision-subtitle">
              {t("decisionCard.invalidation", "Invalidation")}
            </p>
            {renderList(plan.invalidation, t("decisionCard.noInvalidation", "No invalidation condition provided."))}
          </div>
        </section>

        <section className="decision-section">
          <div className="decision-section-title">
            <CheckCircle2 className="size-4" aria-hidden />
            {t("decisionCard.keyReasons", "Key Reasons")}
          </div>
          {card.key_reasons.length === 0 ? (
            <p className="decision-muted">
              {t("decisionCard.noReasons", "No structured evidence was provided.")}
            </p>
          ) : (
            <ul className="decision-evidence-list">
              {card.key_reasons.map((reason, index) => (
                <li key={`${reason.pillar}-${reason.point}-${index}`}>
                  <span>{reason.pillar}</span>
                  <strong>{reason.point}</strong>
                  <p>{reason.evidence}</p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="decision-section">
          <div className="decision-section-title">
            <ShieldAlert className="size-4" aria-hidden />
            {t("decisionCard.risks", "Key Risks")}
          </div>
          {renderList(card.key_risks, t("decisionCard.noRisks", "No structured risk list was provided."))}
        </section>

        <section className="decision-section">
          <div className="decision-section-title">
            <BarChart3 className="size-4" aria-hidden />
            {t("decisionCard.watch", "Catalysts / Watch")}
          </div>
          {renderList(
            [...card.catalysts, ...card.watch_items],
            t("decisionCard.noWatchItems", "No catalysts or watch items were provided.")
          )}
        </section>
      </div>

      {card.data_quality_notes.length > 0 && (
        <section className="decision-quality">
          <div className="decision-section-title">
            <AlertTriangle className="size-4" aria-hidden />
            {t("decisionCard.dataQuality", "Data Quality")}
          </div>
          {renderList(card.data_quality_notes, "")}
        </section>
      )}
    </section>
  );
}
