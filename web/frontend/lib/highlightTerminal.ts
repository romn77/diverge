import type { ReportHighlights, TradeSignal } from "./highlights.ts";

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

function compactCount(value: number): string {
  return String(value);
}

function withFallback(value: string | undefined, fallback: string): string {
  if (!value) {
    return fallback;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : fallback;
}

function baseDeck(
  highlights: ReportHighlights,
  categoryLabel: string,
  heroTitle: string,
  heroChips: TerminalChip[],
  consoles: [TerminalConsole, TerminalConsole]
): HighlightDeck {
  return {
    categoryLabel,
    heroTitle,
    summary: highlights.summary,
    signal: highlights.signal,
    confidence: highlights.signal_confidence,
    heroChips,
    consoles,
  };
}

function buildMarketDeck(
  highlights: Extract<ReportHighlights, { category: "market" }>
): HighlightDeck {
  return baseDeck(
    highlights,
    "Market Outlook",
    "Trend Console",
    [
      { label: "Trend", value: highlights.trend_direction },
      {
        label: "Volatility",
        value: withFallback(highlights.volatility, "Normal"),
      },
      {
        label: "Indicators",
        value: compactCount(highlights.indicators.length),
      },
    ],
    [
      {
        key: "market-console",
        title: "Market Console",
        panels: [
          {
            key: "market-regime",
            title: "Market Regime",
            variant: "story",
            summary: `Primary bias is ${highlights.trend_direction}. Volatility is ${withFallback(
              highlights.volatility,
              "normal"
            ).toLowerCase()}.`,
          },
          {
            key: "key-levels",
            title: "Key Levels",
            variant: "columns",
            columns: [
              { title: "Support", items: highlights.key_levels.support },
              { title: "Resistance", items: highlights.key_levels.resistance },
            ],
          },
        ],
      },
      {
        key: "indicator-console",
        title: "Indicator Console",
        panels: [
          {
            key: "indicator-grid",
            title: "Indicator Grid",
            variant: "table",
            table: {
              columns: ["Indicator", "Value", "Interpretation"],
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
  highlights: Extract<ReportHighlights, { category: "fundamentals" }>
): HighlightDeck {
  return baseDeck(
    highlights,
    "Fundamental Snapshot",
    "Balance Sheet Console",
    [
      {
        label: "Health",
        value: withFallback(highlights.financial_health, "Unspecified"),
      },
      {
        label: "Metrics",
        value: compactCount(highlights.metrics.length),
      },
      {
        label: "Bias",
        value: highlights.signal,
      },
    ],
    [
      {
        key: "balance-console",
        title: "Balance Console",
        panels: [
          {
            key: "balance-sheet-read",
            title: "Balance Sheet Read",
            variant: "story",
            summary: withFallback(
              highlights.financial_health,
              "No explicit financial health tag was provided."
            ),
          },
        ],
      },
      {
        key: "metric-console",
        title: "Metric Console",
        panels: [
          {
            key: "metric-deck",
            title: "Metric Deck",
            variant: "matrix",
            entries: highlights.metrics.map((metric) => ({
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
  highlights: Extract<ReportHighlights, { category: "sentiment" }>
): HighlightDeck {
  return baseDeck(
    highlights,
    "Sentiment Flow",
    "Tape Sentiment",
    [
      { label: "Mood", value: highlights.overall_sentiment },
      {
        label: "Score",
        value: withFallback(highlights.sentiment_score, "N/A"),
      },
      {
        label: "Topics",
        value: compactCount(highlights.key_topics.length),
      },
    ],
    [
      {
        key: "sentiment-console",
        title: "Sentiment Console",
        panels: [
          {
            key: "sentiment-regime",
            title: "Sentiment Regime",
            variant: "story",
            summary: `Overall sentiment is ${highlights.overall_sentiment}. ${
              highlights.social_buzz ? `Social buzz reads ${highlights.social_buzz}.` : ""
            }`.trim(),
          },
        ],
      },
      {
        key: "narrative-console",
        title: "Narrative Console",
        panels: [
          {
            key: "topic-cluster",
            title: "Topic Cluster",
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

function buildNewsDeck(highlights: Extract<ReportHighlights, { category: "news" }>): HighlightDeck {
  return baseDeck(
    highlights,
    "News Catalyst",
    "Catalyst Wire",
    [
      { label: "Impact", value: highlights.market_impact },
      {
        label: "Events",
        value: compactCount(highlights.key_events.length),
      },
      {
        label: "Macro",
        value: withFallback(highlights.macro_outlook, "Watch"),
      },
    ],
    [
      {
        key: "macro-console",
        title: "Macro Console",
        panels: [
          {
            key: "impact-state",
            title: "Impact State",
            variant: "story",
            summary: `Current impact reads ${highlights.market_impact}. ${
              highlights.macro_outlook ? `Macro outlook: ${highlights.macro_outlook}.` : ""
            }`.trim(),
          },
        ],
      },
      {
        key: "event-console",
        title: "Event Console",
        panels: [
          {
            key: "event-wire",
            title: "Event Wire",
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
  highlights: Extract<ReportHighlights, { category: "bull_case" | "bear_case" }>
): HighlightDeck {
  return baseDeck(
    highlights,
    "Research Case",
    "Research Brief",
    [
      { label: "Stance", value: highlights.stance },
      {
        label: "Arguments",
        value: compactCount(highlights.key_arguments.length),
      },
      {
        label: "Counterpoints",
        value: compactCount(highlights.counterpoints?.length ?? 0),
      },
    ],
    [
      {
        key: "thesis-console",
        title: "Thesis Console",
        panels: [
          {
            key: "house-view",
            title: "House View",
            variant: "story",
            summary: `Research stance remains ${highlights.stance}.`,
          },
          ...(highlights.counterpoints && highlights.counterpoints.length > 0
            ? [
                {
                  key: "counter-balance",
                  title: "Counter Balance",
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
        title: "Evidence Console",
        panels: [
          {
            key: "argument-stack",
            title: "Argument Stack",
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
  highlights: Extract<ReportHighlights, { category: "research_decision" }>
): HighlightDeck {
  return baseDeck(
    highlights,
    "Research Decision",
    "Consensus Switchboard",
    [
      { label: "Decision", value: highlights.decision },
      {
        label: "Aligned With",
        value: highlights.aligned_with,
      },
      {
        label: "Action Items",
        value: compactCount(highlights.action_items.length),
      },
    ],
    [
      {
        key: "decision-console",
        title: "Decision Console",
        panels: [
          {
            key: "research-rationale",
            title: "Decision Basis",
            variant: "story",
            summary: highlights.rationale,
          },
        ],
      },
      {
        key: "action-console",
        title: "Action Console",
        panels: [
          {
            key: "action-items",
            title: "Action Items",
            variant: "bullet",
            entries: highlights.action_items.map((item) => ({ title: item })),
          },
        ],
      },
    ]
  );
}

function buildTraderDeck(highlights: Extract<ReportHighlights, { category: "trader" }>): HighlightDeck {
  const queueEntries: TerminalEntry[] = [
    { title: "Action", body: highlights.entry_exit.action, meta: "primary" },
  ];

  if (highlights.entry_exit.exit_target) {
    queueEntries.push({
      title: "Exit Target",
      body: highlights.entry_exit.exit_target,
      meta: "take profit",
    });
  }
  if (highlights.entry_exit.stop_loss) {
    queueEntries.push({
      title: "Stop Loss",
      body: highlights.entry_exit.stop_loss,
      meta: "risk control",
    });
  }
  if (highlights.entry_exit.re_entry) {
    queueEntries.push({
      title: "Re-entry",
      body: highlights.entry_exit.re_entry,
      meta: "watchlist",
    });
  }

  return baseDeck(
    highlights,
    "Trader Playbook",
    "Execution Setup",
    [
      { label: "Decision", value: highlights.decision },
      {
        label: "Plan Steps",
        value: compactCount(queueEntries.length),
      },
      {
        label: "Risk Factors",
        value: compactCount(highlights.risk_factors.length),
      },
    ],
    [
      {
        key: "thesis-console",
        title: "Thesis Console",
        panels: [
          {
            key: "trade-bias",
            title: "Trade Bias",
            variant: "story",
            summary: highlights.entry_exit.action,
          },
          {
            key: "risk-guardrails",
            title: "Risk Guardrails",
            variant: "bullet",
            entries: highlights.risk_factors.map((risk) => ({ title: risk })),
          },
        ],
      },
      {
        key: "execution-console",
        title: "Execution Console",
        panels: [
          {
            key: "execution-queue",
            title: "Execution Queue",
            variant: "queue",
            entries: queueEntries,
          },
        ],
      },
    ]
  );
}

function buildRiskDebateDeck(
  highlights: Extract<ReportHighlights, { category: "risk_aggressive" | "risk_conservative" | "risk_neutral" }>
): HighlightDeck {
  return baseDeck(
    highlights,
    "Risk Desk",
    "Risk Counterparty",
    [
      { label: "Desk", value: highlights.stance_label },
      { label: "Assessment", value: highlights.risk_assessment },
      {
        label: "Recommendations",
        value: compactCount(highlights.key_recommendations.length),
      },
    ],
    [
      {
        key: "stance-console",
        title: "Stance Console",
        panels: [
          {
            key: "risk-stance",
            title: "Risk Stance",
            variant: "story",
            summary: highlights.core_argument,
          },
        ],
      },
      {
        key: "mitigation-console",
        title: "Mitigation Console",
        panels: [
          {
            key: "recommendation-stack",
            title: "Recommendations",
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
  highlights: Extract<ReportHighlights, { category: "portfolio_decision" }>
): HighlightDeck {
  return baseDeck(
    highlights,
    "Portfolio Decision",
    "Allocation Command",
    [
      {
        label: "Decision",
        value: highlights.final_decision,
      },
      {
        label: "Queued Actions",
        value: compactCount(highlights.strategic_actions.length),
      },
      {
        label: "Risk Flags",
        value: compactCount(highlights.risk_warnings.length),
      },
    ],
    [
      {
        key: "decision-console",
        title: "Decision Console",
        panels: [
          {
            key: "decision-basis",
            title: "Decision Basis",
            variant: "story",
            summary: highlights.decision_basis,
          },
          {
            key: "risk-watch",
            title: "Risk Watch",
            variant: "bullet",
            entries: highlights.risk_warnings.map((warning) => ({
              title: warning,
            })),
          },
        ],
      },
      {
        key: "execution-console",
        title: "Execution Console",
        panels: [
          {
            key: "execution-queue",
            title: "Execution Queue",
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

export function buildHighlightDeck(highlights: ReportHighlights): HighlightDeck {
  switch (highlights.category) {
    case "market":
      return buildMarketDeck(highlights);
    case "fundamentals":
      return buildFundamentalsDeck(highlights);
    case "sentiment":
      return buildSentimentDeck(highlights);
    case "news":
      return buildNewsDeck(highlights);
    case "bull_case":
    case "bear_case":
      return buildResearchCaseDeck(highlights);
    case "research_decision":
      return buildResearchDecisionDeck(highlights);
    case "trader":
      return buildTraderDeck(highlights);
    case "risk_aggressive":
    case "risk_conservative":
    case "risk_neutral":
      return buildRiskDebateDeck(highlights);
    case "portfolio_decision":
      return buildPortfolioDecisionDeck(highlights);
    default: {
      const exhaustiveCheck: never = highlights;
      throw new Error(`Unsupported highlight category: ${String(exhaustiveCheck)}`);
    }
  }
}
