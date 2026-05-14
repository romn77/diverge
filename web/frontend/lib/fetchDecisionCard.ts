import { getContent } from "./api";
import type { DecisionCard, DecisionDelta } from "./decisionCard";

export async function fetchDecisionCard(
  reportId: string,
  path: string
): Promise<DecisionCard> {
  const content = await getContent(reportId, path);
  return JSON.parse(content) as DecisionCard;
}

export async function fetchDecisionDelta(
  reportId: string,
  path: string
): Promise<DecisionDelta> {
  const content = await getContent(reportId, path);
  return JSON.parse(content) as DecisionDelta;
}
