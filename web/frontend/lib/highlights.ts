export type TradeSignal = "BUY" | "HOLD" | "SELL";
export type SignalConfidence = "high" | "medium" | "low";

export interface BaseHighlights {
  signal: TradeSignal;
  signal_confidence?: SignalConfidence;
  summary: string;
}

export interface MarketHighlights extends BaseHighlights {
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

export interface FundamentalsHighlights extends BaseHighlights {
  category: "fundamentals";
  metrics: Array<{
    name: string;
    value: string;
    assessment: string;
  }>;
  financial_health?: string;
}

export interface SentimentHighlights extends BaseHighlights {
  category: "sentiment";
  overall_sentiment: "positive" | "negative" | "neutral" | "mixed";
  sentiment_score?: string;
  key_topics: string[];
  social_buzz?: string;
}

export interface NewsHighlights extends BaseHighlights {
  category: "news";
  market_impact: "positive" | "negative" | "neutral" | "mixed";
  key_events: Array<{
    event: string;
    impact: string;
  }>;
  macro_outlook?: string;
}

export interface ResearcherHighlights extends BaseHighlights {
  category: "bull_case" | "bear_case";
  stance: "bullish" | "bearish";
  key_arguments: Array<{
    point: string;
    evidence: string;
  }>;
  counterpoints?: string[];
}

export interface ResearchManagerHighlights extends BaseHighlights {
  category: "research_decision";
  decision: TradeSignal;
  aligned_with: "bull" | "bear";
  rationale: string;
  action_items: string[];
}

export interface TraderHighlights extends BaseHighlights {
  category: "trader";
  decision: TradeSignal;
  entry_exit: {
    action: string;
    exit_target?: string;
    stop_loss?: string;
    re_entry?: string;
  };
  risk_factors: string[];
}

export interface RiskDebateHighlights extends BaseHighlights {
  category: "risk_aggressive" | "risk_conservative" | "risk_neutral";
  stance_label: string;
  core_argument: string;
  risk_assessment: "high" | "moderate" | "low";
  key_recommendations: string[];
}

export interface PortfolioDecisionHighlights extends BaseHighlights {
  category: "portfolio_decision";
  final_decision: TradeSignal;
  decision_basis: string;
  strategic_actions: Array<{
    action: string;
    priority: string;
  }>;
  risk_warnings: string[];
}

export type ReportHighlights =
  | MarketHighlights
  | FundamentalsHighlights
  | SentimentHighlights
  | NewsHighlights
  | ResearcherHighlights
  | ResearchManagerHighlights
  | TraderHighlights
  | RiskDebateHighlights
  | PortfolioDecisionHighlights;

type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

const HIGHLIGHTS_BLOCK_RE = /```json-highlights[ \t]*\r?\n([\s\S]*?)\r?\n?```/m;
const HIGHLIGHTS_BLOCK_RE_GLOBAL = /```json-highlights[ \t]*\r?\n[\s\S]*?\r?\n?```/g;
const FINAL_PROPOSAL_RE = /FINAL\s+TRANSACTION\s+PROPOSAL:\s*\**\s*(BUY|HOLD|SELL)\s*\**/i;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isString);
}

function isEnumValue<T extends string>(value: unknown, allowed: readonly T[]): value is T {
  return isString(value) && (allowed as readonly string[]).includes(value);
}

function extractSignalFromMarkdown(markdown: string): TradeSignal | null {
  const match = markdown.match(FINAL_PROPOSAL_RE);
  if (!match?.[1]) {
    return null;
  }

  const signal = match[1].toUpperCase();
  if (signal === "BUY" || signal === "HOLD" || signal === "SELL") {
    return signal;
  }
  return null;
}

function validateBaseHighlights(value: unknown): value is BaseHighlights {
  if (!isObject(value)) {
    return false;
  }

  if (!isString(value.summary) || value.summary.trim().length === 0) {
    return false;
  }

  if (!isEnumValue(value.signal, ["BUY", "HOLD", "SELL"] as const)) {
    return false;
  }

  if (
    value.signal_confidence !== undefined &&
    !isEnumValue(value.signal_confidence, ["high", "medium", "low"] as const)
  ) {
    return false;
  }

  return true;
}

function validateMarketHighlights(value: unknown): value is MarketHighlights {
  if (!isObject(value) || !validateBaseHighlights(value)) {
    return false;
  }

  if (!isEnumValue(value.trend_direction, ["bullish", "bearish", "neutral", "mixed"] as const)) {
    return false;
  }

  if (!isObject(value.key_levels)) {
    return false;
  }

  if (!isStringArray(value.key_levels.support) || !isStringArray(value.key_levels.resistance)) {
    return false;
  }

  if (!Array.isArray(value.indicators)) {
    return false;
  }

  const indicatorsValid = value.indicators.every((indicator) => {
    if (!isObject(indicator)) {
      return false;
    }
    return isString(indicator.name) && isString(indicator.value) && isString(indicator.interpretation);
  });

  return indicatorsValid && (value.volatility === undefined || isString(value.volatility));
}

function validateFundamentalsHighlights(value: unknown): value is FundamentalsHighlights {
  if (!isObject(value) || !validateBaseHighlights(value) || !Array.isArray(value.metrics)) {
    return false;
  }

  const metricsValid = value.metrics.every((metric) => {
    if (!isObject(metric)) {
      return false;
    }
    return isString(metric.name) && isString(metric.value) && isString(metric.assessment);
  });

  return metricsValid && (value.financial_health === undefined || isString(value.financial_health));
}

function validateSentimentHighlights(value: unknown): value is SentimentHighlights {
  if (!isObject(value) || !validateBaseHighlights(value)) {
    return false;
  }

  if (!isEnumValue(value.overall_sentiment, ["positive", "negative", "neutral", "mixed"] as const)) {
    return false;
  }

  if (!isStringArray(value.key_topics)) {
    return false;
  }

  return (
    (value.sentiment_score === undefined || isString(value.sentiment_score)) &&
    (value.social_buzz === undefined || isString(value.social_buzz))
  );
}

function validateNewsHighlights(value: unknown): value is NewsHighlights {
  if (!isObject(value) || !validateBaseHighlights(value)) {
    return false;
  }

  if (!isEnumValue(value.market_impact, ["positive", "negative", "neutral", "mixed"] as const)) {
    return false;
  }

  if (!Array.isArray(value.key_events)) {
    return false;
  }

  const keyEventsValid = value.key_events.every((event) => {
    if (!isObject(event)) {
      return false;
    }
    return isString(event.event) && isString(event.impact);
  });

  return keyEventsValid && (value.macro_outlook === undefined || isString(value.macro_outlook));
}

function validateResearcherHighlights(value: unknown): value is ResearcherHighlights {
  if (!isObject(value) || !validateBaseHighlights(value)) {
    return false;
  }

  if (!isEnumValue(value.stance, ["bullish", "bearish"] as const) || !Array.isArray(value.key_arguments)) {
    return false;
  }

  if (value.category === "bull_case" && value.stance !== "bullish") {
    return false;
  }

  if (value.category === "bear_case" && value.stance !== "bearish") {
    return false;
  }

  const keyArgumentsValid = value.key_arguments.every((argument) => {
    if (!isObject(argument)) {
      return false;
    }
    return isString(argument.point) && isString(argument.evidence);
  });

  return keyArgumentsValid && (value.counterpoints === undefined || isStringArray(value.counterpoints));
}

function validateResearchManagerHighlights(value: unknown): value is ResearchManagerHighlights {
  if (!isObject(value)) {
    return false;
  }

  return (
    validateBaseHighlights(value) &&
    isEnumValue(value.decision, ["BUY", "HOLD", "SELL"] as const) &&
    isEnumValue(value.aligned_with, ["bull", "bear"] as const) &&
    isString(value.rationale) &&
    isStringArray(value.action_items)
  );
}

function validateTraderHighlights(value: unknown): value is TraderHighlights {
  if (!isObject(value)) {
    return false;
  }

  if (
    !validateBaseHighlights(value) ||
    !isEnumValue(value.decision, ["BUY", "HOLD", "SELL"] as const) ||
    !isObject(value.entry_exit)
  ) {
    return false;
  }

  if (!isString(value.entry_exit.action)) {
    return false;
  }

  const hasOptionalEntryExitValues =
    (value.entry_exit.exit_target === undefined || isString(value.entry_exit.exit_target)) &&
    (value.entry_exit.stop_loss === undefined || isString(value.entry_exit.stop_loss)) &&
    (value.entry_exit.re_entry === undefined || isString(value.entry_exit.re_entry));

  return hasOptionalEntryExitValues && isStringArray(value.risk_factors);
}

function validateRiskDebateHighlights(value: unknown): value is RiskDebateHighlights {
  if (!isObject(value)) {
    return false;
  }

  return (
    validateBaseHighlights(value) &&
    isString(value.stance_label) &&
    isString(value.core_argument) &&
    isEnumValue(value.risk_assessment, ["high", "moderate", "low"] as const) &&
    isStringArray(value.key_recommendations)
  );
}

function validatePortfolioDecisionHighlights(value: unknown): value is PortfolioDecisionHighlights {
  if (!isObject(value)) {
    return false;
  }

  if (
    !validateBaseHighlights(value) ||
    !isEnumValue(value.final_decision, ["BUY", "HOLD", "SELL"] as const) ||
    !isString(value.decision_basis) ||
    !Array.isArray(value.strategic_actions) ||
    !isStringArray(value.risk_warnings)
  ) {
    return false;
  }

  return value.strategic_actions.every((item) => {
    if (!isObject(item)) {
      return false;
    }
    return isString(item.action) && isString(item.priority);
  });
}

function validateReportHighlights(value: unknown): value is ReportHighlights {
  if (!isObject(value) || !isString(value.category)) {
    return false;
  }

  switch (value.category) {
    case "market":
      return validateMarketHighlights(value);
    case "fundamentals":
      return validateFundamentalsHighlights(value);
    case "sentiment":
      return validateSentimentHighlights(value);
    case "news":
      return validateNewsHighlights(value);
    case "bull_case":
    case "bear_case":
      return validateResearcherHighlights(value);
    case "research_decision":
      return validateResearchManagerHighlights(value);
    case "trader":
      return validateTraderHighlights(value);
    case "risk_aggressive":
    case "risk_conservative":
    case "risk_neutral":
      return validateRiskDebateHighlights(value);
    case "portfolio_decision":
      return validatePortfolioDecisionHighlights(value);
    default:
      return false;
  }
}

function removeFirstHighlightsBlock(markdown: string, blockMatch: RegExpMatchArray): string {
  const fullMatch = blockMatch[0];
  const start = blockMatch.index ?? -1;

  if (start < 0) {
    return markdown;
  }

  const end = start + fullMatch.length;
  return `${markdown.slice(0, start)}${markdown.slice(end)}`;
}

export function parseHighlights(markdown: string): {
  highlights: ReportHighlights | null;
  cleanMarkdown: string;
} {
  const firstBlock = markdown.match(HIGHLIGHTS_BLOCK_RE);
  if (!firstBlock) {
    return {
      highlights: null,
      cleanMarkdown: markdown,
    };
  }

  const rawJson = firstBlock[1]?.trim();
  if (!rawJson) {
    return {
      highlights: null,
      cleanMarkdown: markdown,
    };
  }

  let parsed: JsonValue;
  try {
    parsed = JSON.parse(rawJson) as JsonValue;
  } catch {
    return {
      highlights: null,
      cleanMarkdown: markdown,
    };
  }

  if (!isObject(parsed)) {
    return {
      highlights: null,
      cleanMarkdown: markdown,
    };
  }

  if (parsed.signal === undefined) {
    const fallbackSignal = extractSignalFromMarkdown(markdown);
    if (fallbackSignal) {
      parsed.signal = fallbackSignal;
    }
  }

  if (!validateReportHighlights(parsed)) {
    return {
      highlights: null,
      cleanMarkdown: markdown,
    };
  }

  return {
    highlights: parsed,
    cleanMarkdown: removeFirstHighlightsBlock(markdown, firstBlock),
  };
}

export function stripHighlightsBlocks(markdown: string): string {
  return markdown.replace(HIGHLIGHTS_BLOCK_RE_GLOBAL, "");
}
