import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from app.schemas import (
    CandidateProfile,
    DimensionExplanation,
    EvidenceSnippet,
    ExtractedFact,
    JDProfile,
    MatchReport,
    RequirementMatch,
    ScoreBreakdown,
)
from app.text_utils import unique_preserve_order


DIMENSION_MAX_SCORES = {
    "核心技能与工具": 30.0,
    "岗位职责匹配": 20.0,
    "年限与级别": 15.0,
    "项目证据深度": 20.0,
    "行业/业务背景": 8.0,
    "教育/证书/硬条件": 7.0,
}
STATUS_FACTORS = {
    "强匹配": 1.0,
    "直接匹配": 0.85,
    "相关匹配": 0.6,
    "弱匹配": 0.35,
    "未匹配": 0.0,
}
STOP_TERMS = {
    "负责",
    "职责",
    "要求",
    "岗位",
    "相关",
    "建设",
    "开发",
    "优化",
    "平台",
    "系统",
    "服务",
    "以上",
    "经验",
    "熟悉",
    "具备",
    "能力",
    "流程",
}
RELATED_TERMS = {
    "ai": ("rag", "llm", "大模型", "向量检索", "nlp", "prompt"),
    "人工智能": ("rag", "llm", "大模型", "向量检索", "nlp", "prompt"),
}
PROJECT_SECTIONS = {"projects", "experience"}
DIRECT_SECTIONS = {"skills", "projects", "experience", "education", "certifications", "summary", "basic"}


@dataclass
class RequirementSpec:
    dimension: str
    requirement: str
    requirement_type: str
    max_score: float


def score_candidate(
    jd: JDProfile,
    candidate: CandidateProfile,
    evidence_texts: Iterable[str],
    extraction_facts: Optional[Iterable[ExtractedFact]] = None,
) -> MatchReport:
    facts = _build_fact_index(candidate, extraction_facts)
    requirement_specs = _build_requirement_specs(jd, candidate)
    requirement_matches = [_score_requirement(spec, jd, candidate, facts) for spec in requirement_specs]

    dimension_explanations = _dimension_explanations(requirement_matches)
    positive_score = sum(item.score for item in dimension_explanations)
    risk_deduction, risk_reasons = _risk_deduction(jd, candidate, requirement_matches)
    total = max(0, min(100, int(round(positive_score - risk_deduction))))
    total = _apply_score_caps(total, jd, requirement_matches)

    match_reasons = _match_reasons(requirement_matches)
    gap_reasons = _gap_reasons(requirement_matches, risk_reasons)
    evidence_snippets = _evidence_snippets(evidence_texts)

    breakdown = ScoreBreakdown(
        skill_score=round(_dimension_score(dimension_explanations, "核心技能与工具")),
        experience_score=round(_dimension_score(dimension_explanations, "年限与级别")),
        project_score=round(
            _dimension_score(dimension_explanations, "岗位职责匹配")
            + _dimension_score(dimension_explanations, "项目证据深度")
        ),
        industry_score=round(_dimension_score(dimension_explanations, "行业/业务背景")),
        education_score=round(_dimension_score(dimension_explanations, "教育/证书/硬条件")),
        risk_deduction=risk_deduction,
    )
    dimension_scores = {
        explanation.dimension: round(explanation.score) for explanation in dimension_explanations
    }
    dimension_scores["风险扣分"] = -risk_deduction

    return MatchReport(
        total_score=total,
        decision="",
        dimension_scores=dimension_scores,
        score_breakdown=breakdown,
        match_reasons=match_reasons,
        gap_reasons=gap_reasons,
        evidence_snippets=evidence_snippets,
        requirement_matches=requirement_matches,
        dimension_explanations=dimension_explanations,
    )


def _build_requirement_specs(jd: JDProfile, candidate: CandidateProfile) -> List[RequirementSpec]:
    specs: List[RequirementSpec] = []
    if jd.required_skills:
        specs.extend(_weighted_specs("核心技能与工具", jd.required_skills, "required_skill", 24.0, weight=1.0))
        specs.extend(_weighted_specs("核心技能与工具", jd.nice_to_have_skills, "nice_to_have_skill", 6.0, weight=1.0))
    else:
        specs.extend(_weighted_specs("核心技能与工具", jd.nice_to_have_skills, "nice_to_have_skill", 30.0, weight=1.0))
    specs.extend(_weighted_specs("岗位职责匹配", jd.responsibilities, "responsibility", 20.0, weight=1.0))
    if not any(item.dimension == "岗位职责匹配" for item in specs):
        specs.append(
            RequirementSpec(
                dimension="岗位职责匹配",
                requirement="JD 未明确岗位职责",
                requirement_type="responsibility_unspecified",
                max_score=20.0,
            )
        )

    if jd.years_required:
        specs.append(
            RequirementSpec(
                dimension="年限与级别",
                requirement=f"{jd.years_required}年以上经验",
                requirement_type="years_required",
                max_score=10.0,
            )
        )
    if jd.seniority and jd.seniority != "未说明":
        specs.append(
            RequirementSpec(
                dimension="年限与级别",
                requirement=jd.seniority,
                requirement_type="seniority",
                max_score=5.0 if jd.years_required else 15.0,
            )
        )
    if not any(item.dimension == "年限与级别" for item in specs):
        specs.append(
            RequirementSpec(
                dimension="年限与级别",
                requirement="岗位级别/年限未明确",
                requirement_type="seniority_unknown",
                max_score=15.0,
            )
        )

    specs.append(
        RequirementSpec(
            dimension="项目证据深度",
            requirement="相关项目经历",
            requirement_type="project_presence",
            max_score=10.0,
        )
    )
    specs.append(
        RequirementSpec(
            dimension="项目证据深度",
            requirement="个人职责边界",
            requirement_type="project_ownership",
            max_score=5.0,
        )
    )
    specs.append(
        RequirementSpec(
            dimension="项目证据深度",
            requirement="量化结果或业务影响",
            requirement_type="project_metric",
            max_score=5.0,
        )
    )

    if jd.industry_background:
        specs.extend(_weighted_specs("行业/业务背景", jd.industry_background, "industry", 8.0, weight=1.0))
    else:
        specs.append(
            RequirementSpec(
                dimension="行业/业务背景",
                requirement="JD 未限定行业背景",
                requirement_type="industry_unspecified",
                max_score=8.0,
            )
        )

    if jd.hard_requirements:
        specs.extend(_weighted_specs("教育/证书/硬条件", jd.hard_requirements, "hard_requirement", 7.0, weight=1.0))
    else:
        requirement = "教育/证书信息" if candidate.education or candidate.certifications else "JD 未限定教育/证书"
        specs.append(
            RequirementSpec(
                dimension="教育/证书/硬条件",
                requirement=requirement,
                requirement_type="education_signal",
                max_score=7.0,
            )
        )
    return specs


def _weighted_specs(
    dimension: str,
    requirements: Sequence[str],
    requirement_type: str,
    dimension_score: float,
    weight: float,
) -> List[RequirementSpec]:
    cleaned = unique_preserve_order(requirements)
    if not cleaned:
        return []
    total_weight = len(cleaned) * weight
    per_item = dimension_score * weight / total_weight if total_weight else 0
    return [
        RequirementSpec(
            dimension=dimension,
            requirement=requirement,
            requirement_type=requirement_type,
            max_score=per_item,
        )
        for requirement in cleaned
    ]


def _score_requirement(
    spec: RequirementSpec,
    jd: JDProfile,
    candidate: CandidateProfile,
    facts: List[ExtractedFact],
) -> RequirementMatch:
    if spec.requirement_type == "years_required":
        status, confidence, evidence, reason = _score_years_requirement(spec, jd, candidate, facts)
    elif spec.requirement_type == "seniority":
        status, confidence, evidence, reason = _score_seniority_requirement(spec, jd, candidate, facts)
    elif spec.requirement_type == "seniority_unknown":
        status, confidence, evidence, reason = ("相关匹配", 0.8, [], "JD 未明确年限/级别，默认给中等置信分")
    elif spec.requirement_type == "responsibility":
        status, confidence, evidence, reason = _score_responsibility_requirement(spec.requirement, candidate, facts)
    elif spec.requirement_type == "responsibility_unspecified":
        status, confidence, evidence, reason = ("相关匹配", 0.7, [], "JD 未明确职责，默认给中等置信分")
    elif spec.requirement_type == "project_presence":
        status, confidence, evidence, reason = _score_project_presence(candidate, facts)
    elif spec.requirement_type == "project_ownership":
        status, confidence, evidence, reason = _score_project_ownership(candidate, facts)
    elif spec.requirement_type == "project_metric":
        status, confidence, evidence, reason = _score_project_metric(candidate, facts)
    elif spec.requirement_type == "industry_unspecified":
        status, confidence, evidence, reason = ("直接匹配", 0.8, [], "JD 未限定行业背景")
    elif spec.requirement_type == "education_signal":
        status, confidence, evidence, reason = _score_education_signal(candidate, facts)
    else:
        status, confidence, evidence, reason = _score_text_requirement(spec.requirement, candidate, facts)

    contribution = round(spec.max_score * STATUS_FACTORS[status] * confidence, 1)
    return RequirementMatch(
        dimension=spec.dimension,
        requirement=spec.requirement,
        requirement_type=spec.requirement_type,
        status=status,
        max_score=round(spec.max_score, 1),
        contribution=contribution,
        confidence=round(confidence, 2),
        reason=reason,
        evidence=evidence[:2],
    )


def _score_text_requirement(
    requirement: str,
    candidate: CandidateProfile,
    facts: List[ExtractedFact],
) -> Tuple[str, float, List[EvidenceSnippet], str]:
    matched_facts = _matching_facts(requirement, facts)
    evidence = [_fact_to_evidence(fact) for fact in matched_facts[:2]]
    if matched_facts:
        best = matched_facts[0]
        confidence = min(1.0, max(0.55, best.confidence))
        if best.section in PROJECT_SECTIONS:
            confidence = min(1.0, max(0.92, confidence))
            return "强匹配", confidence, evidence, "在项目或经历中找到直接证据"
        if best.section in DIRECT_SECTIONS:
            return "直接匹配", confidence, evidence, "在结构化简历字段中找到直接证据"
        return "相关匹配", confidence, evidence, "找到相关证据，但来源上下文较弱"

    profile_text = _candidate_text(candidate)
    if requirement.lower() in profile_text.lower():
        return "弱匹配", 0.6, [], "简历文本中出现相关表述，但缺少可定位证据"
    related = _related_facts(requirement, facts)
    if related:
        return (
            "相关匹配",
            min(0.78, max(0.6, related[0].confidence)),
            [_fact_to_evidence(fact) for fact in related[:2]],
            "找到同一业务/技术簇的相关证据",
        )
    return "未匹配", 0.0, [], "简历未明确覆盖该要求"


def _score_responsibility_requirement(
    requirement: str,
    candidate: CandidateProfile,
    facts: List[ExtractedFact],
) -> Tuple[str, float, List[EvidenceSnippet], str]:
    skill_terms = re.findall(r"[A-Za-z][A-Za-z0-9+#.]*", requirement)
    if not skill_terms:
        return _score_text_requirement(requirement, candidate, facts)
    matched = []
    for fact in facts:
        text = f"{fact.value} {fact.evidence}".lower()
        hits = sum(1 for term in skill_terms if term.lower() in text)
        if hits >= max(2, round(len(skill_terms) * 0.5)):
            matched.append(fact)
    matched = sorted(matched, key=lambda item: (_section_rank(item.section), item.confidence), reverse=True)
    if matched:
        best = matched[0]
        status = "强匹配" if best.section in PROJECT_SECTIONS else "直接匹配"
        confidence = 0.92 if best.section in PROJECT_SECTIONS else 0.82
        return (
            status,
            confidence,
            [_fact_to_evidence(fact) for fact in matched[:2]],
            "职责句中的核心技术/业务关键词在项目或经历中被覆盖",
        )
    return _score_text_requirement(requirement, candidate, facts)


def _score_years_requirement(
    spec: RequirementSpec,
    jd: JDProfile,
    candidate: CandidateProfile,
    facts: List[ExtractedFact],
) -> Tuple[str, float, List[EvidenceSnippet], str]:
    candidate_years = _candidate_years(candidate)
    evidence = [
        _fact_to_evidence(fact)
        for fact in facts
        if re.search(r"\d{1,2}\s*(?:年|\+)", fact.evidence)
    ][:2]
    if not candidate_years:
        return "未匹配", 0.0, evidence, "简历未明确工作年限"
    if candidate_years >= jd.years_required:
        return "强匹配", 0.92, evidence, f"候选人约 {candidate_years} 年，满足 {spec.requirement}"
    if candidate_years >= max(1, jd.years_required * 0.7):
        return "相关匹配", 0.75, evidence, f"候选人约 {candidate_years} 年，略低于岗位要求"
    return "弱匹配", 0.65, evidence, f"候选人约 {candidate_years} 年，明显低于岗位要求"


def _score_seniority_requirement(
    spec: RequirementSpec,
    jd: JDProfile,
    candidate: CandidateProfile,
    facts: List[ExtractedFact],
) -> Tuple[str, float, List[EvidenceSnippet], str]:
    status, confidence, evidence, reason = _score_text_requirement(spec.requirement, candidate, facts)
    if status != "未匹配":
        return status, confidence, evidence, reason
    candidate_years = _candidate_years(candidate)
    if spec.requirement in {"专家", "资深", "高级", "负责人", "主管"} and candidate_years >= max(5, jd.years_required):
        year_evidence = [
            _fact_to_evidence(fact)
            for fact in facts
            if re.search(r"\d{1,2}\s*(?:年|\+)", fact.evidence)
        ][:2]
        return "相关匹配", 0.82, year_evidence, f"{candidate_years} 年经验可作为 {spec.requirement} 级别的间接证据"
    if spec.requirement == "中级" and candidate_years >= 3:
        return "相关匹配", 0.78, [], "年限可作为中级级别的间接证据"
    return status, confidence, evidence, reason


def _score_project_presence(
    candidate: CandidateProfile,
    facts: List[ExtractedFact],
) -> Tuple[str, float, List[EvidenceSnippet], str]:
    project_facts = [fact for fact in facts if fact.section in PROJECT_SECTIONS or fact.fact_type == "project"]
    evidence = [_fact_to_evidence(fact) for fact in project_facts[:2]]
    if project_facts:
        return "强匹配", 0.9, evidence, "简历有可定位的项目/经历证据"
    if candidate.projects:
        return "直接匹配", 0.75, [], "结构化档案中存在项目经历"
    return "未匹配", 0.0, [], "缺少可深挖的项目经历"


def _score_project_ownership(
    candidate: CandidateProfile,
    facts: List[ExtractedFact],
) -> Tuple[str, float, List[EvidenceSnippet], str]:
    ownership_terms = ("主导", "负责", "owner", "Owner", "负责人", "搭建", "构建")
    matched = [fact for fact in facts if any(term in fact.evidence for term in ownership_terms)]
    evidence = [_fact_to_evidence(fact) for fact in matched[:2]]
    if matched:
        return "直接匹配", 0.84, evidence, "有个人职责或主导动作证据"
    if candidate.highlights:
        return "相关匹配", 0.72, [], "候选人亮点中包含职责表述"
    return "弱匹配", 0.55, [], "个人贡献边界需要面试确认"


def _score_project_metric(
    candidate: CandidateProfile,
    facts: List[ExtractedFact],
) -> Tuple[str, float, List[EvidenceSnippet], str]:
    metric_facts = [fact for fact in facts if fact.fact_type == "metric"]
    evidence = [_fact_to_evidence(fact) for fact in metric_facts[:2]]
    if metric_facts:
        return "直接匹配", 0.88, evidence, "项目结果有量化指标"
    metric_re = re.compile(r"(提升|降低|增长|QPS|DAU|%|\d+\s*(?:人|万|%|倍))")
    if any(metric_re.search(item) for item in candidate.projects + candidate.highlights):
        return "相关匹配", 0.72, [], "结构化档案中有量化描述"
    return "弱匹配", 0.55, [], "项目结果指标和业务影响未量化"


def _score_education_signal(
    candidate: CandidateProfile,
    facts: List[ExtractedFact],
) -> Tuple[str, float, List[EvidenceSnippet], str]:
    if not candidate.education and not candidate.certifications:
        return "直接匹配", 1.0, [], "JD 未限定教育/证书，不作为主要扣分项"
    education_facts = [fact for fact in facts if fact.section in {"education", "certifications"}]
    evidence = [_fact_to_evidence(fact) for fact in education_facts[:2]]
    if candidate.education or candidate.certifications:
        return "直接匹配", 0.82, evidence, "候选人提供了教育或证书信息"
    return "相关匹配", 0.5, [], "JD 未限定教育/证书，简历也未突出该项"


def _matching_facts(requirement: str, facts: List[ExtractedFact]) -> List[ExtractedFact]:
    terms = _meaningful_terms(requirement)
    matched = []
    for fact in facts:
        text = f"{fact.value} {fact.normalized_value or ''} {fact.evidence}".lower()
        exact = requirement.lower() in text
        term_hits = sum(1 for term in terms if term.lower() in text)
        if exact or (terms and term_hits / len(terms) >= 0.5) or (not terms and term_hits):
            matched.append(fact)
    return sorted(matched, key=lambda item: (_section_rank(item.section), item.confidence), reverse=True)


def _meaningful_terms(text: str) -> List[str]:
    terms = re.findall(r"[A-Za-z][A-Za-z0-9+#.]*", text)
    chinese_chunks = re.findall(r"[\u4e00-\u9fa5]{2,}", text)
    for degree in ("博士", "硕士", "本科", "专科", "MBA"):
        if degree in text:
            terms.append(degree)
    for chunk in chinese_chunks:
        if chunk not in STOP_TERMS:
            terms.append(chunk)
    return unique_preserve_order(terms)


def _build_fact_index(
    candidate: CandidateProfile,
    extraction_facts: Optional[Iterable[ExtractedFact]],
) -> List[ExtractedFact]:
    facts = list(extraction_facts or [])
    pseudo_facts = []
    for skill in candidate.skills:
        pseudo_facts.append(_pseudo_fact("skill", skill, skill, "skills", 0.8))
    for project in candidate.projects:
        pseudo_facts.append(_pseudo_fact("project", project, project, "projects", 0.84))
    for work in candidate.work_experiences:
        pseudo_facts.append(_pseudo_fact("experience", work, work, "experience", 0.82))
    for education in candidate.education:
        pseudo_facts.append(_pseudo_fact("education", education, education, "education", 0.68))
    for certification in candidate.certifications:
        pseudo_facts.append(_pseudo_fact("certification", certification, certification, "certifications", 0.68))
    for highlight in candidate.highlights:
        pseudo_facts.append(_pseudo_fact("highlight", highlight, highlight, "summary", 0.62))
    return _dedupe_facts(facts + pseudo_facts)


def _pseudo_fact(fact_type: str, value: str, evidence: str, section: str, confidence: float) -> ExtractedFact:
    return ExtractedFact(
        fact_type=fact_type,
        value=value,
        evidence=evidence,
        section=section,
        confidence=confidence,
        extractor="profile_summary",
    )


def _dedupe_facts(facts: List[ExtractedFact]) -> List[ExtractedFact]:
    seen = set()
    result = []
    for fact in facts:
        key = (fact.fact_type, fact.value.lower(), fact.evidence.lower(), fact.section)
        if key in seen:
            continue
        seen.add(key)
        result.append(fact)
    return result


def _fact_to_evidence(fact: ExtractedFact) -> EvidenceSnippet:
    return EvidenceSnippet(
        source=f"{_section_label(fact.section)}证据",
        text=fact.evidence[:240],
        section=fact.section,
        line_start=fact.line_start,
        line_end=fact.line_end,
        fact_type=fact.fact_type,
    )


def _related_facts(requirement: str, facts: List[ExtractedFact]) -> List[ExtractedFact]:
    related_terms = RELATED_TERMS.get(requirement.lower(), ())
    if not related_terms:
        return []
    matched = []
    for fact in facts:
        text = f"{fact.value} {fact.evidence}".lower()
        if any(term.lower() in text for term in related_terms):
            matched.append(fact)
    return sorted(matched, key=lambda item: (_section_rank(item.section), item.confidence), reverse=True)


def _dimension_explanations(requirement_matches: List[RequirementMatch]) -> List[DimensionExplanation]:
    explanations = []
    for dimension, max_score in DIMENSION_MAX_SCORES.items():
        matches = [item for item in requirement_matches if item.dimension == dimension]
        score = min(max_score, sum(item.contribution for item in matches))
        strong_count = sum(1 for item in matches if item.status in {"强匹配", "直接匹配"})
        missing_count = sum(1 for item in matches if item.status == "未匹配")
        if missing_count:
            summary = f"{strong_count}/{len(matches)} 项有明确证据，{missing_count} 项未覆盖"
        else:
            summary = f"{strong_count}/{len(matches)} 项有明确证据"
        explanations.append(
            DimensionExplanation(
                dimension=dimension,
                score=round(score, 1),
                max_score=max_score,
                summary=summary,
            )
        )
    return explanations


def _risk_deduction(
    jd: JDProfile,
    candidate: CandidateProfile,
    requirement_matches: List[RequirementMatch],
) -> Tuple[int, List[str]]:
    deduction = 0
    reasons = []
    skill_matches = [
        item for item in requirement_matches if item.requirement_type == "required_skill"
    ]
    missing_skills = [item.requirement for item in skill_matches if item.status == "未匹配"]
    if skill_matches and len(missing_skills) / len(skill_matches) >= 0.5:
        deduction += 6
        reasons.append("核心技能缺口超过一半，需要谨慎推进")
    if any(item.requirement_type == "years_required" and item.status in {"未匹配", "弱匹配"} for item in requirement_matches):
        deduction += 3
        reasons.append("经验年限证据不足或低于岗位要求")
    if not candidate.projects:
        deduction += 3
        reasons.append("缺少项目证据支撑岗位匹配")
    if candidate.risk_points:
        deduction += min(4, len(candidate.risk_points) * 2)
        reasons.extend(candidate.risk_points[:2])
    return min(12, deduction), reasons


def _apply_score_caps(total: int, jd: JDProfile, requirement_matches: List[RequirementMatch]) -> int:
    required_skill_matches = [
        item for item in requirement_matches if item.requirement_type == "required_skill"
    ]
    if required_skill_matches:
        missing = [item for item in required_skill_matches if item.status == "未匹配"]
        if len(missing) / len(required_skill_matches) >= 0.5:
            total = min(total, 69)
    hard_unknown = [
        item
        for item in requirement_matches
        if item.requirement_type == "hard_requirement" and item.status in {"未匹配", "弱匹配"}
    ]
    if jd.hard_requirements and hard_unknown:
        total = min(total, 69)
    return total


def _match_reasons(requirement_matches: List[RequirementMatch]) -> List[str]:
    top_matches = [
        item
        for item in requirement_matches
        if item.status in {"强匹配", "直接匹配"} and item.contribution > 0
    ]
    top_matches = sorted(top_matches, key=lambda item: item.contribution, reverse=True)[:3]
    if not top_matches:
        return ["简历中存在少量可复用经历，但与岗位核心要求关联有限"]
    return [
        f"{item.dimension}：{item.requirement} 为{item.status}（贡献 {item.contribution:g}/{item.max_score:g}）"
        for item in top_matches
    ]


def _gap_reasons(requirement_matches: List[RequirementMatch], risk_reasons: List[str]) -> List[str]:
    weak_or_missing = [
        item
        for item in requirement_matches
        if item.status in {"未匹配", "弱匹配"} and item.requirement_type != "industry_unspecified"
    ][:4]
    reasons = [f"{item.dimension}待确认：{item.requirement}（{item.reason}）" for item in weak_or_missing]
    reasons.extend(risk_reasons)
    return unique_preserve_order(reasons) or ["暂未发现影响推进的明确缺口，建议面试中验证项目深度"]


def _evidence_snippets(evidence_texts: Iterable[str]) -> List[EvidenceSnippet]:
    snippets = [
        EvidenceSnippet(source=f"片段 {index + 1}", text=text[:240])
        for index, text in enumerate(evidence_texts)
        if text.strip()
    ][:5]
    if snippets:
        return snippets
    return [EvidenceSnippet(source="简历摘要", text="未检索到高置信证据片段，使用结构化简历进行评分")]


def _dimension_score(dimension_explanations: List[DimensionExplanation], dimension: str) -> float:
    for explanation in dimension_explanations:
        if explanation.dimension == dimension:
            return explanation.score
    return 0.0


def _candidate_years(candidate: CandidateProfile) -> int:
    text = " ".join(candidate.work_experiences + candidate.projects + candidate.highlights)
    years = [int(value) for value in re.findall(r"(\d{1,2})\s*(?:年|\+)", text)]
    return max(years) if years else 0


def _candidate_text(candidate: CandidateProfile) -> str:
    return " ".join(
        candidate.skills
        + candidate.projects
        + candidate.work_experiences
        + candidate.education
        + candidate.certifications
        + candidate.highlights
    )


def _section_rank(section: str) -> int:
    if section in PROJECT_SECTIONS:
        return 5
    if section == "skills":
        return 4
    if section in {"education", "certifications"}:
        return 3
    return 1


def _section_label(section: str) -> str:
    labels = {
        "projects": "项目",
        "experience": "经历",
        "skills": "技能",
        "education": "教育",
        "certifications": "证书",
        "summary": "摘要",
        "basic": "基本信息",
    }
    return labels.get(section, "简历")
