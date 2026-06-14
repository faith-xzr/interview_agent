import { visibleDisplayItems } from "./factDisplay";
import type { MatchReport } from "./types";

export function candidateSummary(report: MatchReport) {
  const matchReasons = visibleDisplayItems(report.match_reasons);
  const gapReasons = visibleDisplayItems(report.gap_reasons);
  if (shouldPreferGapSummary(report)) {
    return gapReasons[0] ?? "暂未识别到明确匹配依据";
  }
  return matchReasons[0] ?? gapReasons[0] ?? "暂未识别到明确匹配依据";
}

export function hasQuestionMaterials(report: MatchReport) {
  return report.interview_questions.length > 0;
}

function shouldPreferGapSummary(report: MatchReport) {
  const hasStrongEvidence = report.requirement_matches.some(
    (item) => (item.status === "强匹配" || item.status === "直接匹配") && item.contribution > 0
  );
  return report.total_score < 60 || !hasStrongEvidence;
}
