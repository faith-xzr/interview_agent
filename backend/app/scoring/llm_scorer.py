import json
from pathlib import Path
from typing import Any, Iterable, List, Optional

from pydantic import BaseModel, Field

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


PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts" / "matching"
RUBRIC_PROMPT_PATH = PROMPT_DIR / "rubric_generation.md"
MATCHING_PROMPT_PATH = PROMPT_DIR / "requirement_matching.md"
SYSTEM_PROMPT = "你是招聘匹配评分 Rubric 设计助手。只输出 JSON，不要输出解释文本。"
MATCHING_SYSTEM_PROMPT = "你是招聘候选人匹配评估助手。只输出 JSON，不要输出解释文本。"
STATUS_VALUES = {"强匹配", "直接匹配", "相关匹配", "弱匹配", "未匹配"}
POSITIVE_STATUSES = {"强匹配", "直接匹配"}


class ScoringRubricItem(BaseModel):
    dimension: str
    requirement: str
    requirement_type: str = "jd_requirement"
    max_score: float = 0
    priority: str = "must_have"
    scoring_note: str = ""


class ScoringRubric(BaseModel):
    items: List[ScoringRubricItem] = Field(default_factory=list)


class EvidenceReference(BaseModel):
    index: int
    snippet: EvidenceSnippet


def generate_scoring_rubric(
    llm: Any,
    jd: JDProfile,
    jd_facts: Iterable[ExtractedFact],
) -> Optional[ScoringRubric]:
    if not getattr(llm, "available", False):
        return None

    facts = list(jd_facts)
    if not facts:
        return None

    try:
        payload = llm.complete_json(SYSTEM_PROMPT, _build_rubric_prompt(jd, facts))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    raw_items = payload.get("rubric")
    if not isinstance(raw_items, list):
        return None

    items = _parse_rubric_items(raw_items)
    if not items:
        return None
    return ScoringRubric(items=_normalize_scores(items))


def score_candidate_with_llm(
    llm: Any,
    jd: JDProfile,
    candidate: CandidateProfile,
    evidence_texts: Iterable[str],
    jd_facts: Iterable[ExtractedFact],
    extraction_facts: Iterable[ExtractedFact],
) -> Optional[MatchReport]:
    rubric = generate_scoring_rubric(llm, jd, jd_facts)
    if rubric is None or not rubric.items:
        return None

    evidence_items = _build_evidence_references(extraction_facts, evidence_texts)
    try:
        payload = llm.complete_json(
            MATCHING_SYSTEM_PROMPT,
            _build_matching_prompt(jd, candidate, rubric, evidence_items),
        )
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    matches = _parse_requirement_matches(payload.get("matches"), rubric, evidence_items)
    if matches is None:
        return None

    dimension_explanations = _dimension_explanations(matches)
    total_score = max(0, min(100, int(round(sum(item.contribution for item in matches)))))
    return MatchReport(
        total_score=total_score,
        decision="",
        dimension_scores={item.dimension: round(item.score) for item in dimension_explanations},
        score_breakdown=_score_breakdown(matches),
        match_reasons=_match_reasons(matches),
        gap_reasons=_gap_reasons(matches),
        evidence_snippets=[item.snippet for item in evidence_items[:5]]
        or [EvidenceSnippet(source="简历摘要", text="未检索到高置信证据片段，使用结构化简历进行评分")],
        requirement_matches=matches,
        dimension_explanations=dimension_explanations,
    )


def _build_rubric_prompt(jd: JDProfile, facts: List[ExtractedFact]) -> str:
    template = RUBRIC_PROMPT_PATH.read_text(encoding="utf-8")
    replacements = {
        "{{JD_PROFILE_JSON}}": json.dumps(jd.model_dump(mode="json"), ensure_ascii=False),
        "{{JD_FACTS_JSON}}": json.dumps(
            [fact.model_dump(mode="json") for fact in facts],
            ensure_ascii=False,
        ),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def _build_matching_prompt(
    jd: JDProfile,
    candidate: CandidateProfile,
    rubric: ScoringRubric,
    evidence_items: List[EvidenceReference],
) -> str:
    template = MATCHING_PROMPT_PATH.read_text(encoding="utf-8")
    replacements = {
        "{{JD_PROFILE_JSON}}": json.dumps(jd.model_dump(mode="json"), ensure_ascii=False),
        "{{RUBRIC_JSON}}": json.dumps(
            [item.model_dump(mode="json") for item in rubric.items],
            ensure_ascii=False,
        ),
        "{{CANDIDATE_PROFILE_JSON}}": json.dumps(candidate.model_dump(mode="json"), ensure_ascii=False),
        "{{EVIDENCE_JSON}}": json.dumps(
            [
                {
                    "index": item.index,
                    **item.snippet.model_dump(mode="json"),
                }
                for item in evidence_items
            ],
            ensure_ascii=False,
        ),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def _parse_rubric_items(raw_items: Iterable[Any]) -> List[ScoringRubricItem]:
    items: List[ScoringRubricItem] = []
    seen = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        requirement = _clean_text(raw.get("requirement"))
        dimension = _clean_text(raw.get("dimension"))
        if not requirement or not dimension:
            continue
        key = (dimension.lower(), requirement.lower())
        if key in seen:
            continue
        seen.add(key)
        max_score = _coerce_score(raw.get("max_score"))
        if max_score <= 0:
            continue
        items.append(
            ScoringRubricItem(
                dimension=dimension,
                requirement=requirement,
                requirement_type=_clean_text(raw.get("requirement_type")) or "jd_requirement",
                max_score=max_score,
                priority=_clean_text(raw.get("priority")) or "must_have",
                scoring_note=_clean_text(raw.get("scoring_note")),
            )
        )
    return items


def _parse_requirement_matches(
    raw_matches: Any,
    rubric: ScoringRubric,
    evidence_items: List[EvidenceReference],
) -> Optional[List[RequirementMatch]]:
    if not isinstance(raw_matches, list):
        return None
    raw_by_requirement = {}
    for raw in raw_matches:
        if not isinstance(raw, dict):
            continue
        requirement = _clean_text(raw.get("requirement"))
        if requirement:
            raw_by_requirement[requirement] = raw

    matches: List[RequirementMatch] = []
    for item in rubric.items:
        raw = raw_by_requirement.get(item.requirement)
        if raw is None:
            return None
        status = _clean_text(raw.get("status"))
        if status not in STATUS_VALUES:
            return None
        confidence = _clamp(_coerce_score(raw.get("confidence")), 0.0, 1.0)
        contribution = _clamp(_coerce_score(raw.get("contribution")), 0.0, item.max_score)
        if status == "未匹配":
            confidence = 0.0
            contribution = 0.0
        evidence = _evidence_from_indexes(raw.get("evidence_indexes"), evidence_items)
        if status in POSITIVE_STATUSES and not evidence:
            return None
        matches.append(
            RequirementMatch(
                dimension=item.dimension,
                requirement=item.requirement,
                requirement_type=item.requirement_type,
                status=status,
                max_score=round(item.max_score, 1),
                contribution=round(contribution, 1),
                confidence=round(confidence, 2),
                reason=_clean_text(raw.get("reason")) or item.scoring_note or "LLM 未提供原因",
                evidence=evidence,
            )
        )
    return matches


def _build_evidence_references(
    extraction_facts: Iterable[ExtractedFact],
    evidence_texts: Iterable[str],
) -> List[EvidenceReference]:
    references: List[EvidenceReference] = []
    seen = set()
    for fact in extraction_facts:
        text = fact.evidence.strip()
        if not text:
            continue
        key = (text, fact.section, fact.line_start)
        if key in seen:
            continue
        seen.add(key)
        references.append(
            EvidenceReference(
                index=len(references),
                snippet=EvidenceSnippet(
                    source=f"{_section_label(fact.section)}证据",
                    text=text[:240],
                    section=fact.section,
                    line_start=fact.line_start,
                    line_end=fact.line_end,
                    fact_type=fact.fact_type,
                ),
            )
        )
    for text in evidence_texts:
        cleaned = text.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        references.append(
            EvidenceReference(
                index=len(references),
                snippet=EvidenceSnippet(source=f"片段 {len(references) + 1}", text=cleaned[:240]),
            )
        )
    return references


def _evidence_from_indexes(raw_indexes: Any, evidence_items: List[EvidenceReference]) -> List[EvidenceSnippet]:
    if not isinstance(raw_indexes, list):
        return []
    by_index = {item.index: item.snippet for item in evidence_items}
    snippets = []
    for raw_index in raw_indexes:
        if isinstance(raw_index, bool):
            continue
        if isinstance(raw_index, int):
            snippet = by_index.get(raw_index)
            if snippet is not None:
                snippets.append(snippet)
    return snippets[:2]


def _dimension_explanations(matches: List[RequirementMatch]) -> List[DimensionExplanation]:
    dimensions: List[str] = []
    for match in matches:
        if match.dimension not in dimensions:
            dimensions.append(match.dimension)

    explanations = []
    for dimension in dimensions:
        dimension_matches = [item for item in matches if item.dimension == dimension]
        score = sum(item.contribution for item in dimension_matches)
        max_score = sum(item.max_score for item in dimension_matches)
        strong_count = sum(1 for item in dimension_matches if item.status in POSITIVE_STATUSES)
        missing_count = sum(1 for item in dimension_matches if item.status == "未匹配")
        if missing_count:
            summary = f"{strong_count}/{len(dimension_matches)} 项有明确证据，{missing_count} 项未覆盖"
        else:
            summary = f"{strong_count}/{len(dimension_matches)} 项有明确证据"
        explanations.append(
            DimensionExplanation(
                dimension=dimension,
                score=round(score, 1),
                max_score=round(max_score, 1),
                summary=summary,
            )
        )
    return explanations


def _score_breakdown(matches: List[RequirementMatch]) -> ScoreBreakdown:
    def score_for(types: set[str]) -> int:
        return round(sum(item.contribution for item in matches if item.requirement_type in types))

    return ScoreBreakdown(
        skill_score=score_for({"core_skill", "nice_to_have"}),
        experience_score=score_for({"years", "seniority"}),
        project_score=score_for({"responsibility", "project_depth"}),
        industry_score=score_for({"industry"}),
        education_score=score_for({"hard_requirement"}),
        risk_deduction=0,
    )


def _match_reasons(matches: List[RequirementMatch]) -> List[str]:
    top_matches = [
        item for item in matches if item.status in POSITIVE_STATUSES and item.contribution > 0
    ]
    top_matches = sorted(top_matches, key=lambda item: item.contribution, reverse=True)[:3]
    if not top_matches:
        return ["简历中存在少量可复用经历，但与岗位核心要求关联有限"]
    return [
        f"{item.dimension}：{item.requirement} 为{item.status}（贡献 {item.contribution:g}/{item.max_score:g}）"
        for item in top_matches
    ]


def _gap_reasons(matches: List[RequirementMatch]) -> List[str]:
    weak_or_missing = [item for item in matches if item.status in {"未匹配", "弱匹配"}][:4]
    return [
        f"{item.dimension}待确认：{item.requirement}（{item.reason}）"
        for item in weak_or_missing
    ] or ["暂未发现影响推进的明确缺口，建议面试中验证项目深度"]


def _normalize_scores(items: List[ScoringRubricItem]) -> List[ScoringRubricItem]:
    total = sum(item.max_score for item in items)
    if total <= 0:
        return []

    normalized = []
    running_total = 0.0
    for item in items[:-1]:
        score = round(item.max_score * 100 / total, 1)
        running_total += score
        normalized.append(item.model_copy(update={"max_score": score}))

    last_score = round(100 - running_total, 1)
    normalized.append(items[-1].model_copy(update={"max_score": max(0.1, last_score)}))
    return normalized


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


def _coerce_score(value: Any) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    if isinstance(value, str):
        try:
            return max(0.0, float(value.strip()))
        except ValueError:
            return 0.0
    return 0.0


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
