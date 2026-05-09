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
}
