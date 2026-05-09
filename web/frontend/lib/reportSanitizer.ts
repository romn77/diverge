const USER_FACING_REPLACEMENTS: Array<[RegExp, string]> = [
  [/当前\s+(?:Current\s+)?Portfolio\s+Ledger\s+Context/gi, "当前持仓参考"],
  [/Current\s+Portfolio\s+Ledger\s+Context/gi, "Current portfolio reference"],
  [/Portfolio\s+Ledger\s+Context/gi, "portfolio reference"],
  [/json-highlights/gi, "structured highlights"],
  [/json-decision-card/gi, "structured decision card"],
  [/Portfolio\s+Manager\s+LLM/gi, "final decision service"],
  [/LLM\s+gateway/gi, "analysis service"],
  [/model\s+gateway/gi, "analysis service"],
];

export function sanitizeUserFacingReportText(value: string): string {
  return USER_FACING_REPLACEMENTS.reduce(
    (text, [pattern, replacement]) => text.replace(pattern, replacement),
    value
  );
}
