import type { CandidateProfile, ExtractedFact } from "./types";

export interface FactGroup {
  section: string;
  facts: ExtractedFact[];
}

export const SECTION_LABELS: Record<string, string> = {
  basic: "基本信息",
  education: "学历背景",
  experience: "实习/工作经验",
  projects: "项目经验",
  skills: "专业技能",
  summary: "自我评价",
  certifications: "证书资质",
  jd: "JD 核心要求"
};

const SECTION_ORDER = ["basic", "education", "experience", "projects", "skills", "summary", "certifications"];
const HIDDEN_RESUME_FACT_TYPES = new Set([
  "target_role",
  "location",
  "contact",
  "phone",
  "email",
  "domain_evidence",
  "领域证据",
  "ai_tool_application",
  "tool_application"
]);
const HIDDEN_DISPLAY_TEXT_PATTERNS = [/^AI\s*工具应用能力\s*[:：]/i];
const FACT_LABELS: Record<string, string> = {
  job_title: "岗位名称",
  required_skill: "必备技能",
  nice_to_have_skill: "加分项",
  responsibility: "核心职责",
  years_required: "年限要求",
  seniority: "级别要求",
  industry: "行业背景",
  hard_requirement: "硬性要求",
  education_summary: "学历背景",
  education: "学历背景",
  degree: "学历背景",
  work_summary: "核心工作",
  experience: "工作经历",
  experience_position: "任职信息",
  project: "项目经验",
  skill: "专业技能",
  certification: "证书资质",
  highlight: "亮点",
  summary: "亮点",
  metric: "量化成果",
  domain_evidence: "领域证据",
  risk: "风险点"
};

export function groupResumeFacts(facts: ExtractedFact[], profile?: CandidateProfile): FactGroup[] {
  const factsWithProfileFallback = addProfileProjectFallback(facts, profile);
  const bySection = new Map<string, ExtractedFact[]>();
  for (const fact of factsWithProfileFallback.filter(isVisibleResumeFact)) {
    const section = fact.section || "unknown";
    bySection.set(section, [...(bySection.get(section) ?? []), fact]);
  }
  return [...bySection.entries()]
    .map(([section, sectionFacts]) => ({ section, facts: compactFactsForSection(section, sortFactsWithinSection(sectionFacts)) }))
    .filter((group) => group.facts.length > 0)
    .sort((left, right) => sectionRank(left.section) - sectionRank(right.section));
}

function sortFactsWithinSection(facts: ExtractedFact[]) {
  const rank: Record<string, number> = {
    education_summary: 1,
    work_summary: 1,
    project: 1,
    responsibility: 2,
    highlight: 3,
    experience_position: 3,
    education: 2,
    degree: 3,
    skill: 4,
    certification: 5,
    metric: 6,
    domain_evidence: 7,
    summary: 8
  };
  return [...facts].sort((left, right) => {
    if (left.section === right.section && ["experience", "projects", "summary"].includes(left.section)) {
      const lineDelta = (left.line_start ?? 9999) - (right.line_start ?? 9999);
      if (lineDelta !== 0) return lineDelta;
    }
    return (rank[left.fact_type] ?? 99) - (rank[right.fact_type] ?? 99);
  });
}

function compactFactsForSection(section: string, facts: ExtractedFact[]) {
  if (section === "education") {
    return facts.filter((fact) => fact.fact_type === "education_summary" || fact.fact_type === "education").slice(0, 1);
  }
  if (section === "experience") {
    const richerFacts = facts.filter(
      (fact) =>
        fact.fact_type === "work_summary"
        || fact.fact_type === "responsibility"
        || fact.fact_type === "highlight"
        || fact.fact_type === "summary"
        || fact.fact_type === "metric"
    );
    const displayFacts = richerFacts.length ? richerFacts : facts;
    return compactNarrativeFacts(displayFacts, "experience").slice(0, 4);
  }
  if (section === "projects") {
    return compactNarrativeFacts(facts, "projects").slice(0, 6);
  }
  if (section === "skills") {
    return compactSkillFacts(facts);
  }
  if (section === "summary") {
    const highlightFacts = facts.filter((fact) => fact.fact_type === "summary" || fact.fact_type === "highlight");
    return compactSummaryFacts(highlightFacts.length ? highlightFacts : facts).slice(0, 4);
  }
  return facts.slice(0, 6);
}

function isVisibleResumeFact(fact: ExtractedFact) {
  return fact.section !== "basic"
    && !HIDDEN_RESUME_FACT_TYPES.has(fact.fact_type)
    && !isCitationOnlyText(fact.value)
    && !isLowContextMetricFact(fact);
}

function addProfileProjectFallback(facts: ExtractedFact[], profile?: CandidateProfile) {
  if (!profile?.projects?.length) return facts;
  const projectFacts = facts.filter((fact) => fact.section === "projects");
  const hasProjectNarrative = projectFacts.some(
    (fact) => fact.fact_type === "project" && cleanFactText(fact.value).length >= 12
  );
  if (hasProjectNarrative) return facts;
  const projectSummary = profile.projects.map(cleanFactText).find((value) => value.length >= 16);
  if (!projectSummary) return facts;
  const fallbackFact: ExtractedFact = {
    fact_type: "project",
    value: projectSummary,
    evidence: projectSummary,
    section: "projects",
    line_start: 0,
    line_end: 0,
    confidence: 0.7,
    extractor: "profile_projection"
  };
  return [fallbackFact, ...facts];
}

function isLowContextMetricFact(fact: ExtractedFact) {
  return fact.fact_type === "metric" && isLowContextMetricText(fact.value);
}

function isLowContextMetricText(value: string) {
  const text = cleanFactText(value);
  if (!text) return true;
  const semanticText = text
    .replace(/百分之|以上|以下|左右|约|超过|余|多|近|达|达到/g, "")
    .replace(/[0-9０-９一二三四五六七八九十百千万亿两零点.,+/%％\s-]/g, "")
    .replace(/(项|件|条|个|次|名|场|倍|人|元|小时|分钟|天|个月|年|分|套|份|篇)$/g, "")
    .trim();
  return semanticText.length < 2;
}

export function visibleDisplayItems(items: string[]) {
  return items.filter((item) => !isHiddenDisplayText(item));
}

function isHiddenDisplayText(value: string) {
  return HIDDEN_DISPLAY_TEXT_PATTERNS.some((pattern) => pattern.test(value.trim()));
}

function compactNarrativeFacts(facts: ExtractedFact[], section: string) {
  const result: ExtractedFact[] = [];
  let current: ExtractedFact | null = null;
  for (const fact of facts.filter((item) => !isCitationOnlyText(item.value))) {
    if (!current) {
      current = fact;
      continue;
    }
    if (isContainedText(current.value, fact.value)) {
      continue;
    }
    if (isContainedText(fact.value, current.value)) {
      current = { ...fact, fact_type: current.fact_type };
      continue;
    }
    if (shouldMergeWithPrevious(current, fact, section)) {
      current = mergeFacts(current, fact, section === "projects" && isProjectTitleLike(current.value) ? "colon" : "plain");
      continue;
    }
    result.push(current);
    current = fact;
  }
  if (current) {
    result.push(current);
  }
  return dedupeFactsByValue(result);
}

function compactSummaryFacts(facts: ExtractedFact[]) {
  if (!facts.length) return [];
  const base = facts[0];
  const phrases: string[] = [];
  for (const fact of facts) {
    for (const phrase of splitSummaryPhrases(fact.value)) {
      appendSummaryPhrase(phrases, phrase);
    }
  }
  return removeRedundantPhrases(phrases).map((value, index) => ({
    ...base,
    value,
    line_start: facts[index]?.line_start ?? base.line_start,
    line_end: facts[index]?.line_end ?? base.line_end
  }));
}

function splitSummaryPhrases(value: string) {
  return cleanFactText(value)
    .split(/\s*[；;]\s*/)
    .map((item) => trimEndingPunctuation(trimStartingPunctuation(item)))
    .filter((item) => item.length >= 4);
}

function appendSummaryPhrase(phrases: string[], phrase: string) {
  if (phrases.some((existing) => isContainedText(existing, phrase))) return;
  const containedIndex = phrases.findIndex((existing) => isContainedText(phrase, existing));
  if (containedIndex >= 0) {
    phrases.splice(containedIndex, 1);
  }
  const last = phrases[phrases.length - 1];
  if (last && shouldJoinSummaryPhrase(last, phrase)) {
    phrases[phrases.length - 1] = `${trimEndingPunctuation(last)}${trimStartingPunctuation(phrase)}`;
    return;
  }
  phrases.push(phrase);
}

function shouldMergeWithPrevious(previous: ExtractedFact, current: ExtractedFact, section: string) {
  const previousText = cleanFactText(previous.value);
  const currentText = cleanFactText(current.value);
  if (!previousText || !currentText) return false;
  if (section === "projects" && isProjectTitleLike(previousText)) return true;
  if (!areAdjacentFacts(previous, current)) return false;
  if (isContinuationFragment(currentText) || isMetricLikeFragment(currentText)) return true;
  if (endsLikeUnfinishedPhrase(previousText)) return true;
  return false;
}

function mergeFacts(previous: ExtractedFact, current: ExtractedFact, mode: "plain" | "colon") {
  const previousText = trimEndingPunctuation(cleanFactText(previous.value));
  const currentText = trimStartingPunctuation(cleanFactText(current.value));
  const separator = mode === "plain" && shouldInsertSpaceBetweenFragments(previousText, currentText) ? " " : "";
  const value = mode === "colon"
    ? `${previousText}：${currentText}`
    : `${previousText}${separator}${currentText}`;
  return {
    ...previous,
    value,
    evidence: [previous.evidence, current.evidence].filter(Boolean).join("\n"),
    line_end: current.line_end ?? previous.line_end
  };
}

function compactSkillFacts(facts: ExtractedFact[]) {
  const skillFacts = facts.filter((fact) => fact.fact_type === "skill");
  if (!skillFacts.length) return facts.slice(0, 6);
  const base = skillFacts[0];
  const groups: SkillDisplayGroup[] = [];
  let activeGroup: SkillDisplayGroup | null = null;
  for (const fact of skillFacts) {
    for (const segment of splitSkillPhrase(fact.value)) {
      const parsed = parseSkillSegment(segment);
      if (!parsed.value) continue;
      if (isParentheticalOnly(parsed.value) && groups.length) {
        appendToLastSkillItem(groups[groups.length - 1], parsed.value, "concat");
        continue;
      }
      if (parsed.label) {
        activeGroup = createSkillGroup(parsed.value, fact, parsed.label);
        groups.push(activeGroup);
        continue;
      }
      if (activeGroup && shouldAttachSkillContinuation(activeGroup, parsed.value, fact)) {
        appendToLastSkillItem(
          activeGroup,
          parsed.value,
          shouldConcatSkillContinuation(activeGroup.items[activeGroup.items.length - 1], parsed.value) ? "concat" : "slash"
        );
        activeGroup.line_end = fact.line_end ?? activeGroup.line_end;
        continue;
      }
      activeGroup = null;
      groups.push(createSkillGroup(parsed.value, fact));
    }
  }
  const displayValues = removeRedundantPhrases(groups.map(formatSkillGroup).filter(Boolean));
  return displayValues.map((value, index) => ({
    ...base,
    value,
    line_start: groups[index]?.line_start ?? base.line_start,
    line_end: groups[index]?.line_end ?? base.line_end
  }));
}

interface SkillDisplayGroup {
  label?: string;
  items: string[];
  line_start?: number;
  line_end?: number;
}

function splitSkillPhrase(value: string) {
  return value
    .split(/\s*[；;]\s*/)
    .map(cleanSkillText)
    .filter((item) => item.length >= 2 && !["熟悉", "熟练", "精通", "掌握"].includes(item));
}

function parseSkillSegment(value: string) {
  const text = cleanSkillText(value);
  const match = text.match(/^([^:：]{2,16})[:：]\s*(.+)$/u);
  if (!match) return { value: text };
  const label = cleanSkillLabel(match[1]);
  const item = cleanSkillText(match[2]);
  if (!label || !item) return { value: text };
  return { label, value: item };
}

function cleanSkillText(value: string) {
  return cleanFactText(value)
    .replace(/^[•·\-\*]\s*/u, "")
    .replace(/\s*\[\d+\]\s*/gu, "")
    .replace(/^(熟练掌握|熟练运用|熟练使用|熟悉掌握|精通|熟悉|掌握|了解|具备)\s*/u, "")
    .replace(/[:：]\s*(熟练掌握|熟练运用|熟练使用|熟悉掌握|精通|熟悉|掌握|了解|具备)\s*/u, "：")
    .replace(/^极强的/u, "")
    .replace(/AIGC\s*工作流/giu, "AIGC 工作流")
    .replace(/TikTok\s*平台/giu, "TikTok平台")
    .replace(/[。；;]+$/u, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function cleanSkillLabel(value: string) {
  const label = cleanFactText(value).replace(/^[•·\-\*]\s*/u, "").trim();
  if (!/^[\u4e00-\u9fa5A-Za-z0-9 /&+-]{2,16}$/u.test(label)) return "";
  return label;
}

function createSkillGroup(value: string, fact: ExtractedFact, label?: string): SkillDisplayGroup {
  return {
    label,
    items: [value],
    line_start: fact.line_start ?? undefined,
    line_end: fact.line_end ?? undefined
  };
}

function shouldAttachSkillContinuation(group: SkillDisplayGroup, value: string, fact: ExtractedFact) {
  if (!group.label) return false;
  if (fact.line_start && group.line_end && fact.line_start > group.line_end + 1) return false;
  if (/^(具备|拥有|负责|带领|参与|主导|获得|获|能够|能)/u.test(value)) return false;
  return true;
}

function appendToLastSkillItem(group: SkillDisplayGroup, value: string, mode: "concat" | "slash") {
  const cleaned = cleanSkillText(value);
  if (!cleaned) return;
  if (!group.items.length) {
    group.items.push(cleaned);
    return;
  }
  if (mode === "concat") {
    group.items[group.items.length - 1] = `${trimEndingPunctuation(group.items[group.items.length - 1])}${trimStartingPunctuation(cleaned)}`;
    return;
  }
  if (!group.items.some((item) => normalizeComparableText(item) === normalizeComparableText(cleaned))) {
    group.items.push(cleaned);
  }
}

function shouldConcatSkillContinuation(previous: string | undefined, current: string) {
  if (!previous) return false;
  if (/^(频|视频|图片|图|片|\/)/u.test(current)) return true;
  return /[视图]$/u.test(previous);
}

function formatSkillGroup(group: SkillDisplayGroup) {
  const items = removeRedundantPhrases(group.items);
  if (!items.length) return "";
  const text = items.join(" / ");
  return group.label ? `${group.label}：${text}` : text;
}

function removeRedundantPhrases(phrases: string[]) {
  const unique = dedupeStrings(phrases);
  return unique.filter((phrase, index) => {
    const normalized = normalizeComparableText(phrase);
    return !unique.some((other, otherIndex) => {
      if (index === otherIndex) return false;
      const otherNormalized = normalizeComparableText(other);
      return otherNormalized.includes(normalized) && otherNormalized.length > normalized.length;
    });
  }).slice(0, 8);
}

function dedupeFactsByValue(facts: ExtractedFact[]) {
  const seen = new Set<string>();
  return facts.filter((fact) => {
    const key = normalizeComparableText(fact.value);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function dedupeStrings(values: string[]) {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const key = normalizeComparableText(value);
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(value);
  }
  return result;
}

function areAdjacentFacts(previous: ExtractedFact, current: ExtractedFact) {
  if (!previous.line_end || !current.line_start) return true;
  return current.line_start <= previous.line_end + 1;
}

function isContinuationFragment(value: string) {
  return /^(至|到|与|及|和|并|量|感|后|成本|爆款|日均|获|获得|提升|降低|缩短|节省)/u.test(value);
}

function isMetricLikeFragment(value: string) {
  return value.length <= 16 && /\d/.test(value) && /(条|个|人|元|%|小时|天|万|次|名|场)/u.test(value);
}

function endsLikeUnfinishedPhrase(value: string) {
  return /(累计产出|从\d+(?:\.\d+)?[天小时分钟]*缩短|节省设计|通过\s*AI\s*批|与情|结合|与售|提升|降低|缩短|产出|完成|利用|使用|负责|拥有|逻辑)$/u.test(value);
}

function shouldInsertSpaceBetweenFragments(previous: string, current: string) {
  return /[\u4e00-\u9fa5]$/u.test(previous) && /^[A-Za-z0-9]/u.test(current);
}

function isCitationOnlyText(value: string) {
  return /^[\s。.,，；;]*[\[［【]\d+[\]］】][\s。.,，；;]*$/u.test(value);
}

function shouldJoinSummaryPhrase(previous: string, current: string) {
  if (/^思维/u.test(current) && /逻辑$/u.test(previous)) return true;
  if (isContinuationFragment(current)) return true;
  return endsLikeUnfinishedPhrase(previous) && !startsLikeNewFact(current);
}

function startsLikeNewFact(value: string) {
  return /^(具备|拥有|负责|带领|参与|主导|使用|利用|熟悉|精通|掌握|获得|获|能够|能)/u.test(value);
}

function isProjectTitleLike(value: string) {
  const text = cleanFactText(value);
  return text.length <= 36
    && /(项目|平台|系统|实战|营销|创业|案例)/u.test(text)
    && !/[，,；;。]/u.test(text)
    && !/(负责|带领|利用|使用|生成|节省|提升|降低|产出|完成)/u.test(text);
}

function isParentheticalOnly(value: string) {
  return /^[（(].+[）)]$/u.test(value);
}

function cleanFactText(value: string) {
  return value.replace(/\s*[\[［【]\d+[\]］】]\s*/gu, " ").replace(/\s+/g, " ").trim();
}

function trimEndingPunctuation(value: string) {
  return value.replace(/[。；;，,\s]+$/u, "");
}

function trimStartingPunctuation(value: string) {
  return value.replace(/^[。；;，,\s]+/u, "");
}

function normalizeComparableText(value: string) {
  return value.replace(/\s+/g, "").replace(/[。；;，,、:：]/g, "").toLowerCase();
}

function isContainedText(container: string, candidate: string) {
  const normalizedContainer = normalizeComparableText(container);
  const normalizedCandidate = normalizeComparableText(candidate);
  return normalizedCandidate.length >= 2
    && normalizedContainer.length > normalizedCandidate.length
    && normalizedContainer.includes(normalizedCandidate);
}

export function factDisplayLabel(fact: ExtractedFact) {
  return FACT_LABELS[fact.fact_type] ?? (containsChinese(fact.fact_type) ? fact.fact_type : "关键事实");
}

function containsChinese(value: string) {
  return /[\u4e00-\u9fa5]/.test(value);
}

function sectionRank(section: string) {
  const index = SECTION_ORDER.indexOf(section);
  return index === -1 ? 99 : index;
}

export function formatScore(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
