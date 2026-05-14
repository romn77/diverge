import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Gauge,
  ListChecks,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { usePreferences } from "@/components/PreferencesProvider";
import type {
  ActionPlaybook,
  DecisionCard as DecisionCardModel,
  DecisionDelta,
  FieldDelta,
  PortfolioRating,
  PositionGuidance,
  WhyNot,
} from "@/lib/decisionCard";

interface DecisionCardProps {
  card: DecisionCardModel;
  delta?: DecisionDelta | null;
}

function ratingClass(rating: PortfolioRating): string {
  return {
    BUY: "decision-rating--buy",
    OVERWEIGHT: "decision-rating--overweight",
    HOLD: "decision-rating--hold",
    UNDERWEIGHT: "decision-rating--underweight",
    SELL: "decision-rating--sell",
  }[rating];
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

function truncateList(items: string[] | undefined, maxItems = 3): string[] {
  return (items ?? []).filter(Boolean).slice(0, maxItems);
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

function enumLabel(
  prefix: string,
  value: string | null | undefined,
  fallback: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return value ? t(`${prefix}.${value}`, value) : fallback;
}

function ensureWhyNot(
  whyNot: WhyNot | null | undefined,
  t: ReturnType<typeof usePreferences>["t"]
): WhyNot {
  const fallback = t(
    "decisionCard.noStructuredRationale",
    "Not enough structured rationale was provided."
  );
  return {
    why_not_more_bullish: whyNot?.why_not_more_bullish || fallback,
    why_not_more_bearish: whyNot?.why_not_more_bearish || fallback,
    why_not_act_now: whyNot?.why_not_act_now || fallback,
  };
}

function playbookFromCard(card: DecisionCardModel): ActionPlaybook {
  return {
    do_now: truncateList(card.action_playbook?.do_now, 3),
    trigger_to_act: truncateList(
      card.action_playbook?.trigger_to_act ??
        [card.price_plan.add_condition, ...card.watch_items].filter(
          (item): item is string => Boolean(item)
        ),
      3
    ),
    invalidation: truncateList(
      card.action_playbook?.invalidation ?? card.price_plan.invalidation,
      3
    ),
    execution_notes: truncateList(card.action_playbook?.execution_notes, 3),
  };
}

function positionGuidanceText(
  guidance: PositionGuidance | null | undefined,
  fallback: string | null
): string | null {
  if (!guidance) {
    return fallback;
  }
  return [guidance.suggested_exposure, guidance.risk_budget_note]
    .filter(Boolean)
    .join(" ");
}

function deltaRows(delta: DecisionDelta | null | undefined) {
  if (!delta) {
    return [];
  }
  const rows: Array<[string, FieldDelta | null]> = [
    ["Rating", delta.rating],
    ["Action", delta.action],
    ["Conviction", delta.conviction_score],
    ["Confidence", delta.confidence],
    ["Trade Readiness", delta.trade_readiness],
  ];
  return rows.filter((row): row is [string, FieldDelta] =>
    Boolean(row[1]?.changed)
  );
}

function formatDeltaValue(value: string | number | null): string {
  return value === null || value === undefined ? "N/A" : String(value);
}

function DecisionDeltaStrip({ delta }: { delta?: DecisionDelta | null }) {
  const { t } = usePreferences();
  if (!delta) {
    return null;
  }
  const rows = deltaRows(delta);
  const summary = rows.length
    ? rows
        .slice(0, 3)
        .map(
          ([label, field]) =>
            `${label}: ${formatDeltaValue(field.previous)} -> ${formatDeltaValue(
              field.current
            )}`
        )
        .join(" · ")
    : delta.summary;

  return (
    <details className="decision-delta-strip">
      <summary>
        <span>{t("decisionCard.decisionDelta", "Since Last Analysis")}</span>
        <strong>{summary}</strong>
      </summary>
      <div className="decision-delta-detail">
        <p className="decision-muted">{delta.summary}</p>
        {delta.previous_report_id && (
          <p className="decision-muted">
            {t(
              "decisionCard.previousReport",
              ({ reportId }) => `Previous report: ${reportId}`,
              { reportId: delta.previous_report_id }
            )}
          </p>
        )}
        {rows.length > 0 &&
          renderList(
            rows.map(
              ([label, field]) =>
                `${label}: ${formatDeltaValue(field.previous)} -> ${formatDeltaValue(
                  field.current
                )}`
            ),
            t("decisionCard.noDeltaChanges", "No changed fields.")
          )}
      </div>
    </details>
  );
}

function WhyNotPanel({ whyNot }: { whyNot: WhyNot }) {
  const { t } = usePreferences();
  const items = [
    [
      t("decisionCard.whyNotBullish", "Why not more bullish?"),
      whyNot.why_not_more_bullish,
    ],
    [
      t("decisionCard.whyNotBearish", "Why not more bearish?"),
      whyNot.why_not_more_bearish,
    ],
    [
      t("decisionCard.whyNotActNow", "Why not act now?"),
      whyNot.why_not_act_now,
    ],
  ];

  return (
    <section className="decision-section decision-why-not">
      <div className="decision-section-title">
        <Sparkles className="size-4" aria-hidden />
        {t("decisionCard.whyNot", "Why Not?")}
      </div>
      <div className="decision-why-not-grid">
        {items.map(([label, body]) => (
          <div key={label}>
            <span>{label}</span>
            <p>{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ActionPlaybookPanel({ playbook }: { playbook: ActionPlaybook }) {
  const { t } = usePreferences();
  const columns = [
    [
      t("decisionCard.doNow", "Do Now"),
      playbook.do_now,
      t("decisionCard.noDoNow", "No immediate action provided."),
    ],
    [
      t("decisionCard.triggerToAct", "Trigger"),
      playbook.trigger_to_act,
      t("decisionCard.noTrigger", "No trigger provided."),
    ],
    [
      t("decisionCard.playbookInvalidation", "Invalidation"),
      playbook.invalidation,
      t("decisionCard.noInvalidation", "No invalidation condition provided."),
    ],
  ] as const;

  return (
    <section className="decision-section">
      <div className="decision-section-title">
        <ListChecks className="size-4" aria-hidden />
        {t("decisionCard.actionPlaybook", "Action Playbook")}
      </div>
      <div className="decision-playbook-grid">
        {columns.map(([label, items, empty]) => (
          <div key={label}>
            <span>{label}</span>
            {renderList(items, empty)}
          </div>
        ))}
      </div>
      {playbook.execution_notes.length > 0 && (
        <p className="decision-playbook-note">
          {playbook.execution_notes.join(" ")}
        </p>
      )}
    </section>
  );
}

export function DecisionCard({ card, delta }: DecisionCardProps) {
  const { t } = usePreferences();
  const displayName = card.name ? `${card.symbol} / ${card.name}` : card.symbol;
  const plan = card.price_plan;
  const whyNot = ensureWhyNot(card.why_not, t);
  const playbook = playbookFromCard(card);
  const guidanceText = positionGuidanceText(
    card.position_guidance,
    card.suggested_position
  );

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
          <span className="decision-badge">
            {t("decisionCard.conviction", "Conviction")}: {card.conviction_score} / 100
          </span>
          <span className="decision-badge">{card.confidence}</span>
          <span className="decision-badge">
            {enumLabel(
              "decisionCard.tradeReadiness",
              card.trade_readiness,
              t("decisionCard.readinessUnknown", "Readiness unknown"),
              t
            )}
          </span>
          <span className="decision-badge">
            {t("decisionCard.dataQuality", "Data Quality")}:{" "}
            {enumLabel(
              "decisionCard.dataQualityLevel",
              card.data_quality_level,
              t("decisionCard.dataQualityUnknown", "Data quality unknown"),
              t
            )}
          </span>
        </div>
      </header>

      <p className="decision-summary-line">{card.one_line_summary}</p>

      {card.trade_readiness_reason && (
        <p className="decision-readiness-reason">
          {card.trade_readiness_reason}
        </p>
      )}

      {card.data_quality_summary && (
        <p className="decision-muted">{card.data_quality_summary}</p>
      )}

      <DecisionDeltaStrip delta={delta} />

      <WhyNotPanel whyNot={whyNot} />

      <ActionPlaybookPanel playbook={playbook} />

      {guidanceText && (
        <section className="decision-position-guidance">
          <Gauge className="size-4" aria-hidden />
          <span>{t("decisionCard.positionGuidance", "Position Guidance")}</span>
          <p>{guidanceText}</p>
        </section>
      )}

      <details className="decision-evidence-details">
        <summary>
          <span>{t("decisionCard.evidenceDetails", "Evidence and Details")}</span>
          <span className="decision-raw-meta">
            {t("decisionCard.folded", "Folded")}
          </span>
        </summary>

        <div className="decision-section-grid">
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
              {t("decisionCard.pricePlan", "Price Plan")}
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
            </dl>
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

          <section className="decision-section">
            <div className="decision-section-title">
              <ListChecks className="size-4" aria-hidden />
              {t("decisionCard.thesis", "Thesis")}
            </div>
            <p className="decision-thesis">{card.thesis}</p>
          </section>
        </div>
      </details>

      {card.data_quality_notes.length > 0 && (
        <details className="decision-evidence-details decision-quality-details">
          <summary>
            <span>
              <AlertTriangle className="size-4" aria-hidden />
              {t("decisionCard.qualityNotes", "Quality Notes")}
            </span>
            <span className="decision-raw-meta">
              {card.data_quality_notes.length}
            </span>
          </summary>
          {renderList(card.data_quality_notes, "")}
        </details>
      )}
    </section>
  );
}
