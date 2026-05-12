import type { ReportHighlights, TradeSignal } from "./highlights.ts";
import { sanitizeUserFacingReportText } from "./reportSanitizer.ts";
import type { TranslationParams, TranslationTemplate } from "./uiPreferences.ts";

export type TerminalPanelVariant =
  | "story"
  | "columns"
  | "table"
  | "matrix"
  | "bullet"
  | "queue";

export type TerminalPanelSpan = "normal" | "wide" | "full";

export interface TerminalChip {
  label: string;
  value: string;
}

export interface TerminalEntry {
  title: string;
  body?: string;
  meta?: string;
}

export interface TerminalColumn {
  title: string;
  items: string[];
}

export interface TerminalTableRow {
  label: string;
  value: string;
  detail: string;
}

export interface TerminalPanel {
  key: string;
  title: string;
  variant: TerminalPanelVariant;
  span?: TerminalPanelSpan;
  summary?: string;
  chips?: TerminalChip[];
  entries?: TerminalEntry[];
  columns?: TerminalColumn[];
  table?: {
    columns: [string, string, string];
    rows: TerminalTableRow[];
  };
}

export interface TerminalConsole {
  key: string;
  title: string;
  panels: TerminalPanel[];
}

export interface HighlightDeck {
  categoryLabel: string;
  heroTitle: string;
  summary: string;
  signal: TradeSignal;
  confidence?: string;
  heroChips: TerminalChip[];
  consoles: [TerminalConsole, TerminalConsole];
}

export type HighlightTranslator = (
  key: string,
  fallback: TranslationTemplate,
  params?: TranslationParams
) => string;

const defaultHighlightTranslator: HighlightTranslator = (_key, fallback, params) =>
  typeof fallback === "function" ? fallback(params ?? {}) : fallback;

function compactCount(value: number): string {
  return String(value);
}

function withFallback(value: string | undefined, fallback: string): string {
  if (!value) {
    return fallback;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? sanitizeUserFacingReportText(trimmed) : fallback;
}

function cleanText(value: string): string {
  return sanitizeUserFacingReportText(value);
}

function cleanChip(chip: TerminalChip): TerminalChip {
  return {
    label: cleanText(chip.label),
    value: cleanText(chip.value),
  };
}

function cleanEntry(entry: TerminalEntry): TerminalEntry {
  return {
    title: cleanText(entry.title),
    body: entry.body ? cleanText(entry.body) : undefined,
    meta: entry.meta ? cleanText(entry.meta) : undefined,
  };
}

function cleanPanel(panel: TerminalPanel): TerminalPanel {
  return {
    ...panel,
    title: cleanText(panel.title),
    summary: panel.summary ? cleanText(panel.summary) : undefined,
    chips: panel.chips?.map(cleanChip),
    entries: panel.entries?.map(cleanEntry),
    columns: panel.columns?.map((column) => ({
      title: cleanText(column.title),
      items: column.items.map(cleanText),
    })),
    table: panel.table
      ? {
          columns: panel.table.columns.map(cleanText) as [string, string, string],
          rows: panel.table.rows.map((row) => ({
            label: cleanText(row.label),
            value: cleanText(row.value),
            detail: cleanText(row.detail),
          })),
        }
      : undefined,
  };
}

function cleanConsole(consolePanel: TerminalConsole): TerminalConsole {
  return {
    key: consolePanel.key,
    title: cleanText(consolePanel.title),
    panels: consolePanel.panels.map(cleanPanel),
  };
}

function baseDeck(
  highlights: ReportHighlights,
  categoryLabel: string,
  heroTitle: string,
  heroChips: TerminalChip[],
  consoles: [TerminalConsole, TerminalConsole]
): HighlightDeck {
  return {
    categoryLabel: cleanText(categoryLabel),
    heroTitle: cleanText(heroTitle),
    summary: cleanText(highlights.summary),
    signal: highlights.signal,
    confidence: highlights.signal_confidence,
    heroChips: heroChips.map(cleanChip),
    consoles: consoles.map(cleanConsole) as [TerminalConsole, TerminalConsole],
  };
}

function buildMarketDeck(
  highlights: Extract<ReportHighlights, { category: "market" }>,
  t: HighlightTranslator
): HighlightDeck {
  const volatility = withFallback(
    highlights.volatility,
    t("highlights.fallback.normal", "Normal")
  );
  return baseDeck(
    highlights,
    t("highlights.market.category", "Market Outlook"),
    t("highlights.market.hero", "Trend Console"),
    [
      { label: t("highlights.chip.trend", "Trend"), value: highlights.trend_direction },
      {
        label: t("highlights.chip.volatility", "Volatility"),
        value: volatility,
      },
      {
        label: t("highlights.chip.indicators", "Indicators"),
        value: compactCount(highlights.indicators.length),
      },
    ],
    [
      {
        key: "market-console",
        title: t("highlights.market.console", "Market Console"),
        panels: [
          {
            key: "market-regime",
            title: t("highlights.market.regime", "Market Regime"),
            variant: "story",
            summary: t(
              "highlights.market.regimeSummary",
              ({ trend, volatility: value }) =>
                `Primary bias is ${trend}. Volatility is ${String(value ?? "normal").toLowerCase()}.`,
              {
                trend: highlights.trend_direction,
                volatility,
              }
            ),
          },
          {
            key: "key-levels",
            title: t("highlights.market.keyLevels", "Key Levels"),
            variant: "columns",
            columns: [
              { title: t("highlights.market.support", "Support"), items: highlights.key_levels.support },
              { title: t("highlights.market.resistance", "Resistance"), items: highlights.key_levels.resistance },
            ],
          },
        ],
      },
      {
        key: "indicator-console",
        title: t("highlights.market.indicatorConsole", "Indicator Console"),
        panels: [
          {
            key: "indicator-grid",
            title: t("highlights.market.indicatorGrid", "Indicator Grid"),
            variant: "table",
            table: {
              columns: [
                t("highlights.table.indicator", "Indicator"),
                t("highlights.table.value", "Value"),
                t("highlights.table.interpretation", "Interpretation"),
              ],
              rows: highlights.indicators.map((indicator) => ({
                label: indicator.name,
                value: indicator.value,
                detail: indicator.interpretation,
              })),
            },
          },
        ],
      },
    ]
  );
}

function buildFundamentalsDeck(
  highlights: Extract<ReportHighlights, { category: "fundamentals" }>,
  t: HighlightTranslator
): HighlightDeck {
  const dcfApplicabilityMetric = highlights.metrics.find((metric) =>
    /dcf applicability$/i.test(metric.name)
  );
  const dcfApplicabilityReasonMetric = highlights.metrics.find((metric) =>
    /dcf applicability reason/i.test(metric.name)
  );
  const baseCaseMetric = highlights.metrics.find((metric) =>
    /base case/i.test(metric.name)
  );
  const peg1YMetric = highlights.metrics.find((metric) =>
    /^peg \(1y(?: forward)?\)$/i.test(metric.name)
  );
  const valuationMetrics = highlights.metrics.filter((metric) =>
    /dcf applicability|fair value|enterprise value|equity value|net debt|p\/e|peg|p\/b|ev\/ebitda|ev\/sales|fcf yield|wacc|growth rate|terminal growth|Bull Case|Base Case|Bear Case/i.test(
      metric.name
    )
  );
  const operatingMetrics = highlights.metrics.filter(
    (metric) => !valuationMetrics.includes(metric)
  );
  const fairValueMetric = valuationMetrics.find((metric) =>
    /fair value/i.test(metric.name)
  );

  return baseDeck(
    highlights,
    t("highlights.fundamentals.category", "Fundamental Snapshot"),
    t("highlights.fundamentals.hero", "Balance Sheet Console"),
    [
      {
        label: t("highlights.chip.health", "Health"),
        value: withFallback(
          highlights.financial_health,
          t("highlights.fallback.unspecified", "Unspecified")
        ),
      },
      {
        label: t("highlights.chip.baseCaseFairValue", "Base Case Fair Value"),
        value: baseCaseMetric?.value ?? fairValueMetric?.value ?? "N/A",
      },
      {
        label: t("highlights.chip.peg1y", "PEG (1Y)"),
        value: peg1YMetric?.value ?? "N/A",
      },
    ],
    [
      {
        key: "balance-console",
        title: t("highlights.fundamentals.balanceConsole", "Balance Console"),
        panels: [
          {
            key: "balance-sheet-read",
            title: t("highlights.fundamentals.balanceRead", "Balance Sheet Read"),
            variant: "story",
            summary: withFallback(
              highlights.financial_health,
              t(
                "highlights.fundamentals.noHealth",
                "No explicit financial health tag was provided."
              )
            ),
          },
          ...(dcfApplicabilityMetric
            ? [
                {
                  key: "dcf-applicability",
                  title: t("highlights.fundamentals.dcfStatus", "DCF Status"),
                  variant: "story",
                  summary: dcfApplicabilityReasonMetric
                    ? `${dcfApplicabilityMetric.value}. ${dcfApplicabilityReasonMetric.value}`
                    : dcfApplicabilityMetric.value,
                } satisfies TerminalPanel,
              ]
            : []),
        ],
      },
      {
        key: "metric-console",
        title: t("highlights.fundamentals.valuationConsole", "Valuation Console"),
        panels: [
          ...(valuationMetrics.length > 0
            ? [
                {
                  key: "valuation-table",
                  title: t("highlights.fundamentals.valuationTable", "Valuation Table"),
                  variant: "table",
                  span: "wide",
                  table: {
                    columns: [
                      t("highlights.table.metric", "Metric"),
                      t("highlights.table.value", "Value"),
                      t("highlights.table.read", "Read"),
                    ],
                    rows: valuationMetrics.map((metric) => ({
                      label: metric.name,
                      value: metric.value,
                      detail: metric.assessment,
                    })),
                  },
                } satisfies TerminalPanel,
              ]
            : []),
          {
            key: "metric-deck",
            title: t("highlights.fundamentals.metricDeck", "Metric Deck"),
            variant: "matrix",
            entries: (operatingMetrics.length > 0 ? operatingMetrics : highlights.metrics).map((metric) => ({
              title: metric.name,
              body: metric.value,
              meta: metric.assessment,
            })),
          },
        ],
      },
    ]
  );
}

function buildSentimentDeck(
  highlights: Extract<ReportHighlights, { category: "sentiment" }>,
  t: HighlightTranslator
): HighlightDeck {
  return baseDeck(
    highlights,
    t("highlights.sentiment.category", "Sentiment Flow"),
    t("highlights.sentiment.hero", "Tape Sentiment"),
    [
      { label: t("highlights.chip.mood", "Mood"), value: highlights.overall_sentiment },
      {
        label: t("highlights.chip.score", "Score"),
        value: withFallback(highlights.sentiment_score, "N/A"),
      },
      {
        label: t("highlights.chip.topics", "Topics"),
        value: compactCount(highlights.key_topics.length),
      },
    ],
    [
      {
        key: "sentiment-console",
        title: t("highlights.sentiment.console", "Sentiment Console"),
        panels: [
          {
            key: "sentiment-regime",
            title: t("highlights.sentiment.regime", "Sentiment Regime"),
            variant: "story",
            summary: t(
              "highlights.sentiment.regimeSummary",
              ({ sentiment, buzz }) =>
                `Overall sentiment is ${sentiment}. ${
                  buzz ? `Social buzz reads ${buzz}.` : ""
                }`.trim(),
              {
                sentiment: highlights.overall_sentiment,
                buzz: highlights.social_buzz,
              }
            ),
          },
        ],
      },
      {
        key: "narrative-console",
        title: t("highlights.sentiment.narrativeConsole", "Narrative Console"),
        panels: [
          {
            key: "topic-cluster",
            title: t("highlights.sentiment.topicCluster", "Topic Cluster"),
            variant: "matrix",
            entries: highlights.key_topics.map((topic) => ({
              title: topic,
            })),
          },
        ],
      },
    ]
  );
}

function buildNewsDeck(
  highlights: Extract<ReportHighlights, { category: "news" }>,
  t: HighlightTranslator
): HighlightDeck {
  return baseDeck(
    highlights,
    t("highlights.news.category", "News Catalyst"),
    t("highlights.news.hero", "Catalyst Wire"),
    [
      { label: t("highlights.chip.impact", "Impact"), value: highlights.market_impact },
      {
        label: t("highlights.chip.events", "Events"),
        value: compactCount(highlights.key_events.length),
      },
      {
        label: t("highlights.chip.macro", "Macro"),
        value: withFallback(
          highlights.macro_outlook,
          t("highlights.fallback.watch", "Watch")
        ),
      },
    ],
    [
      {
        key: "macro-console",
        title: t("highlights.news.macroConsole", "Macro Console"),
        panels: [
          {
            key: "impact-state",
            title: t("highlights.news.impactState", "Impact State"),
            variant: "story",
            summary: t(
              "highlights.news.impactSummary",
              ({ impact, macro }) =>
                `Current impact reads ${impact}. ${
                  macro ? `Macro outlook: ${macro}.` : ""
                }`.trim(),
              {
                impact: highlights.market_impact,
                macro: highlights.macro_outlook,
              }
            ),
          },
        ],
      },
      {
        key: "event-console",
        title: t("highlights.news.eventConsole", "Event Console"),
        panels: [
          {
            key: "event-wire",
            title: t("highlights.news.eventWire", "Event Wire"),
            variant: "bullet",
            entries: highlights.key_events.map((event) => ({
              title: event.event,
              body: event.impact,
            })),
          },
        ],
      },
    ]
  );
}

function buildResearchCaseDeck(
  highlights: Extract<ReportHighlights, { category: "bull_case" | "bear_case" }>,
  t: HighlightTranslator
): HighlightDeck {
  return baseDeck(
    highlights,
    t("highlights.researchCase.category", "Research Case"),
    t("highlights.researchCase.hero", "Research Brief"),
    [
      { label: t("highlights.chip.stance", "Stance"), value: highlights.stance },
      {
        label: t("highlights.chip.arguments", "Arguments"),
        value: compactCount(highlights.key_arguments.length),
      },
      {
        label: t("highlights.chip.counterpoints", "Counterpoints"),
        value: compactCount(highlights.counterpoints?.length ?? 0),
      },
    ],
    [
      {
        key: "thesis-console",
        title: t("highlights.researchCase.thesisConsole", "Thesis Console"),
        panels: [
          {
            key: "house-view",
            title: t("highlights.researchCase.houseView", "House View"),
            variant: "story",
            summary: t(
              "highlights.researchCase.stanceSummary",
              ({ stance }) => `Research stance remains ${stance}.`,
              { stance: highlights.stance }
            ),
          },
          ...(highlights.counterpoints && highlights.counterpoints.length > 0
            ? [
                {
                  key: "counter-balance",
                  title: t("highlights.researchCase.counterBalance", "Counter Balance"),
                  variant: "bullet",
                  entries: highlights.counterpoints.map((counterpoint) => ({
                    title: counterpoint,
                  })),
                } satisfies TerminalPanel,
              ]
            : []),
        ],
      },
      {
        key: "evidence-console",
        title: t("highlights.researchCase.evidenceConsole", "Evidence Console"),
        panels: [
          {
            key: "argument-stack",
            title: t("highlights.researchCase.argumentStack", "Argument Stack"),
            variant: "bullet",
            entries: highlights.key_arguments.map((argument) => ({
              title: argument.point,
              body: argument.evidence,
            })),
          },
        ],
      },
    ]
  );
}

function buildResearchDecisionDeck(
  highlights: Extract<ReportHighlights, { category: "research_decision" }>,
  t: HighlightTranslator
): HighlightDeck {
  return baseDeck(
    highlights,
    t("highlights.researchDecision.category", "Research Decision"),
    t("highlights.researchDecision.hero", "Consensus Switchboard"),
    [
      { label: t("highlights.chip.decision", "Decision"), value: highlights.decision },
      {
        label: t("highlights.chip.alignedWith", "Aligned With"),
        value: highlights.aligned_with,
      },
      {
        label: t("highlights.chip.actionItems", "Action Items"),
        value: compactCount(highlights.action_items.length),
      },
    ],
    [
      {
        key: "decision-console",
        title: t("highlights.decision.console", "Decision Console"),
        panels: [
          {
            key: "research-rationale",
            title: t("highlights.decision.basis", "Decision Basis"),
            variant: "story",
            summary: highlights.rationale,
          },
        ],
      },
      {
        key: "action-console",
        title: t("highlights.decision.actionConsole", "Action Console"),
        panels: [
          {
            key: "action-items",
            title: t("highlights.decision.actionItems", "Action Items"),
            variant: "bullet",
            entries: highlights.action_items.map((item) => ({ title: item })),
          },
        ],
      },
    ]
  );
}

function buildTraderDeck(
  highlights: Extract<ReportHighlights, { category: "trader" }>,
  t: HighlightTranslator
): HighlightDeck {
  const queueEntries: TerminalEntry[] = [
    {
      title: t("highlights.trader.action", "Action"),
      body: highlights.entry_exit.action,
      meta: t("highlights.trader.primary", "primary"),
    },
  ];

  if (highlights.entry_exit.exit_target) {
    queueEntries.push({
      title: t("highlights.trader.exitTarget", "Exit Target"),
      body: highlights.entry_exit.exit_target,
      meta: t("highlights.trader.takeProfit", "take profit"),
    });
  }
  if (highlights.entry_exit.stop_loss) {
    queueEntries.push({
      title: t("highlights.trader.stopLoss", "Stop Loss"),
      body: highlights.entry_exit.stop_loss,
      meta: t("highlights.trader.riskControl", "risk control"),
    });
  }
  if (highlights.entry_exit.re_entry) {
    queueEntries.push({
      title: t("highlights.trader.reEntry", "Re-entry"),
      body: highlights.entry_exit.re_entry,
      meta: t("highlights.trader.watchlist", "watchlist"),
    });
  }

  return baseDeck(
    highlights,
    t("highlights.trader.category", "Trader Playbook"),
    t("highlights.trader.hero", "Execution Setup"),
    [
      { label: t("highlights.chip.decision", "Decision"), value: highlights.decision },
      {
        label: t("highlights.chip.planSteps", "Plan Steps"),
        value: compactCount(queueEntries.length),
      },
      {
        label: t("highlights.chip.riskFactors", "Risk Factors"),
        value: compactCount(highlights.risk_factors.length),
      },
    ],
    [
      {
        key: "thesis-console",
        title: t("highlights.researchCase.thesisConsole", "Thesis Console"),
        panels: [
          {
            key: "trade-bias",
            title: t("highlights.trader.tradeBias", "Trade Bias"),
            variant: "story",
            summary: highlights.entry_exit.action,
          },
          {
            key: "risk-guardrails",
            title: t("highlights.trader.riskGuardrails", "Risk Guardrails"),
            variant: "bullet",
            entries: highlights.risk_factors.map((risk) => ({ title: risk })),
          },
        ],
      },
      {
        key: "execution-console",
        title: t("highlights.trader.executionConsole", "Execution Console"),
        panels: [
          {
            key: "execution-queue",
            title: t("highlights.trader.executionQueue", "Execution Queue"),
            variant: "queue",
            entries: queueEntries,
          },
        ],
      },
    ]
  );
}

function buildRiskDebateDeck(
  highlights: Extract<ReportHighlights, { category: "risk_aggressive" | "risk_conservative" | "risk_neutral" }>,
  t: HighlightTranslator
): HighlightDeck {
  return baseDeck(
    highlights,
    t("highlights.risk.category", "Risk Desk"),
    t("highlights.risk.hero", "Risk Counterparty"),
    [
      { label: t("highlights.chip.desk", "Desk"), value: highlights.stance_label },
      { label: t("highlights.chip.assessment", "Assessment"), value: highlights.risk_assessment },
      {
        label: t("highlights.chip.recommendations", "Recommendations"),
        value: compactCount(highlights.key_recommendations.length),
      },
    ],
    [
      {
        key: "stance-console",
        title: t("highlights.risk.stanceConsole", "Stance Console"),
        panels: [
          {
            key: "risk-stance",
            title: t("highlights.risk.stance", "Risk Stance"),
            variant: "story",
            summary: highlights.core_argument,
          },
        ],
      },
      {
        key: "mitigation-console",
        title: t("highlights.risk.mitigationConsole", "Mitigation Console"),
        panels: [
          {
            key: "recommendation-stack",
            title: t("highlights.risk.recommendations", "Recommendations"),
            variant: "bullet",
            entries: highlights.key_recommendations.map((recommendation) => ({
              title: recommendation,
            })),
          },
        ],
      },
    ]
  );
}

function buildPortfolioDecisionDeck(
  highlights: Extract<ReportHighlights, { category: "portfolio_decision" }>,
  t: HighlightTranslator
): HighlightDeck {
  return baseDeck(
    highlights,
    t("highlights.portfolio.category", "Portfolio Decision"),
    t("highlights.portfolio.hero", "Allocation Command"),
    [
      {
        label: t("highlights.chip.decision", "Decision"),
        value: highlights.final_decision,
      },
      {
        label: t("highlights.chip.queuedActions", "Queued Actions"),
        value: compactCount(highlights.strategic_actions.length),
      },
      {
        label: t("highlights.chip.riskFlags", "Risk Flags"),
        value: compactCount(highlights.risk_warnings.length),
      },
    ],
    [
      {
        key: "decision-console",
        title: t("highlights.decision.console", "Decision Console"),
        panels: [
          {
            key: "decision-basis",
            title: t("highlights.decision.basis", "Decision Basis"),
            variant: "story",
            summary: highlights.decision_basis,
          },
          {
            key: "risk-watch",
            title: t("highlights.portfolio.riskWatch", "Risk Watch"),
            variant: "bullet",
            entries: highlights.risk_warnings.map((warning) => ({
              title: warning,
            })),
          },
        ],
      },
      {
        key: "execution-console",
        title: t("highlights.trader.executionConsole", "Execution Console"),
        panels: [
          {
            key: "execution-queue",
            title: t("highlights.trader.executionQueue", "Execution Queue"),
            variant: "queue",
            entries: highlights.strategic_actions.map((action) => ({
              title: action.action,
              meta: action.priority,
            })),
          },
        ],
      },
    ]
  );
}

export function buildHighlightDeck(
  highlights: ReportHighlights,
  t: HighlightTranslator = defaultHighlightTranslator
): HighlightDeck {
  switch (highlights.category) {
    case "market":
      return buildMarketDeck(highlights, t);
    case "fundamentals":
      return buildFundamentalsDeck(highlights, t);
    case "sentiment":
      return buildSentimentDeck(highlights, t);
    case "news":
      return buildNewsDeck(highlights, t);
    case "bull_case":
    case "bear_case":
      return buildResearchCaseDeck(highlights, t);
    case "research_decision":
      return buildResearchDecisionDeck(highlights, t);
    case "trader":
      return buildTraderDeck(highlights, t);
    case "risk_aggressive":
    case "risk_conservative":
    case "risk_neutral":
      return buildRiskDebateDeck(highlights, t);
    case "portfolio_decision":
      return buildPortfolioDecisionDeck(highlights, t);
    default: {
      const exhaustiveCheck: never = highlights;
      throw new Error(`Unsupported highlight category: ${String(exhaustiveCheck)}`);
    }
  }
}
