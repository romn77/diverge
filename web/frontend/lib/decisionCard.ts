export type PortfolioRating =
  | "BUY"
  | "OVERWEIGHT"
  | "HOLD"
  | "UNDERWEIGHT"
  | "SELL";

export type PortfolioAction =
  | "OPEN"
  | "ADD"
  | "MAINTAIN"
  | "TRIM"
  | "EXIT"
  | "WATCH"
  | "NO_ACTION"
  | "AVOID";

export type ConfidenceLevel = "high" | "medium" | "low";

export type EvidencePillar =
  | "technical"
  | "fundamentals"
  | "valuation"
  | "news"
  | "sentiment"
  | "risk"
  | "portfolio"
  | "macro";

export interface EvidenceItem {
  pillar: EvidencePillar;
  point: string;
  evidence: string;
  strength: "strong" | "medium" | "weak";
  source?: string | null;
  data_date?: string | null;
  confidence?: ConfidenceLevel | null;
  limitation?: string | null;
}

export interface PricePlan {
  current_price: number | null;
  entry_zone: number[] | null;
  add_condition: string | null;
  stop_loss: number | null;
  take_profit: number[] | null;
  invalidation: string[];
  risk_reward_note: string | null;
}

export type TradeReadiness =
  | "READY"
  | "WAITING_FOR_TRIGGER"
  | "BLOCKED_BY_RISK"
  | "DATA_INSUFFICIENT"
  | "NO_ACTION_REQUIRED";

export type DataQualityLevel = "complete" | "partial" | "weak" | "insufficient";

export interface WhyNot {
  why_not_more_bullish: string | null;
  why_not_more_bearish: string | null;
  why_not_act_now: string | null;
}

export interface ActionPlaybook {
  do_now: string[];
  trigger_to_act: string[];
  invalidation: string[];
  execution_notes: string[];
}

export interface PositionGuidance {
  suggested_exposure: string | null;
  max_exposure: string | null;
  sizing_rationale: string | null;
  risk_budget_note: string | null;
}

export interface DecisionCard {
  card_version: string;
  report_id: string | null;
  symbol: string;
  name: string | null;
  market: "cn" | "us" | "hk" | "unknown";
  analysis_date: string | null;
  generated_at: string;
  rating: PortfolioRating;
  action: PortfolioAction;
  confidence: ConfidenceLevel;
  conviction_score: number;
  time_horizon: string;
  one_line_summary: string;
  thesis: string;
  price_plan: PricePlan;
  suggested_position: string | null;
  key_reasons: EvidenceItem[];
  key_risks: string[];
  catalysts: string[];
  watch_items: string[];
  data_quality_notes: string[];
  source_report_paths: string[];
  raw_signal: string | null;
  trade_readiness?: TradeReadiness | null;
  trade_readiness_reason?: string | null;
  blocking_items?: string[];
  data_quality_level?: DataQualityLevel | null;
  data_quality_summary?: string | null;
  why_not?: WhyNot | null;
  action_playbook?: ActionPlaybook | null;
  position_guidance?: PositionGuidance | null;
}

export interface FieldDelta {
  previous: string | number | null;
  current: string | number | null;
  changed: boolean;
}

export interface DecisionDelta {
  previous_report_id: string | null;
  current_report_id: string;
  symbol: string;
  summary: string;
  rating: FieldDelta;
  action: FieldDelta;
  conviction_score: FieldDelta;
  confidence: FieldDelta;
  trade_readiness: FieldDelta | null;
}
