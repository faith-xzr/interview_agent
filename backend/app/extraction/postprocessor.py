from typing import Any, Iterable, List, Tuple, TypeVar

from pydantic import BaseModel, Field

from app.schemas import CandidateProfile, ExtractedFact, JDProfile
from app.text_utils import unique_preserve_order

ProfileT = TypeVar("ProfileT", CandidateProfile, JDProfile)


class ExtractionPostprocessPayload(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    facts: List[ExtractedFact] = Field(default_factory=list)


def postprocess_extraction(
    llm,
    text: str,
    profile: ProfileT,
    facts: List[ExtractedFact],
    warnings: List[str],
    label: str,
) -> Tuple[ProfileT, List[ExtractedFact]]:
    if not getattr(llm, "available", False):
        return profile, facts

    payload = llm.complete_json(
        "你是招聘结构化抽取后处理助手，只输出 JSON。所有 facts 必须来自原文 evidence，禁止编造。",
        _build_prompt(text, profile, facts),
    )
    if not payload:
        warnings.append(f"{label} 的 LLM 抽取后处理失败，已使用本地规则结果。")
        return profile, facts

    try:
        parsed = ExtractionPostprocessPayload.model_validate(payload)
        profile_type = type(profile)
        supported_facts = _filter_supported_facts(parsed.facts, text)
        proposed_profile = profile_type.model_validate(parsed.profile)
        merged_profile = _merge_profile(profile, proposed_profile, supported_facts)
        return merged_profile, _dedupe_facts([*facts, *supported_facts])
    except Exception:
        warnings.append(f"{label} 的 LLM 抽取后处理结果结构不合法，已使用本地规则结果。")
        return profile, facts


def _build_prompt(text: str, profile: BaseModel, facts: Iterable[ExtractedFact]) -> str:
    local_payload = {
        "profile": _profile_for_prompt(profile),
        "facts": [fact.model_dump(mode="json") for fact in _facts_for_prompt(facts, text)],
    }
    return (
        "请基于原文和本地规则抽取结果做后处理。可以合并重复事实、修正 fact_type/section、补充有 evidence 支撑的字段。"
        "返回 JSON: {\"profile\": {...}, \"facts\": [...]}。\n\n"
        f"原文:\n{text}\n\n"
        f"本地规则结果:\n{local_payload}"
    )


def _profile_for_prompt(profile: BaseModel) -> dict[str, Any]:
    data = profile.model_dump(mode="json")
    if isinstance(profile, CandidateProfile):
        data["name"] = "候选人"
        data["contacts"] = {}
    return data


def _facts_for_prompt(facts: Iterable[ExtractedFact], text: str) -> List[ExtractedFact]:
    normalized_text = _normalize_for_evidence(text)
    return [fact for fact in facts if _normalize_for_evidence(fact.evidence) in normalized_text]


def _filter_supported_facts(facts: Iterable[ExtractedFact], text: str) -> List[ExtractedFact]:
    supported = []
    normalized_text = _normalize_for_evidence(text)
    for fact in facts:
        if not fact.evidence.strip():
            continue
        if _normalize_for_evidence(fact.evidence) not in normalized_text:
            continue
        if fact.extractor == "section_rules":
            fact.extractor = "llm_postprocess"
        supported.append(fact)
    return supported


def _merge_profile(profile: ProfileT, proposed: ProfileT, supported_facts: List[ExtractedFact]) -> ProfileT:
    if isinstance(profile, CandidateProfile) and isinstance(proposed, CandidateProfile):
        return _merge_candidate_profile(profile, proposed, supported_facts)  # type: ignore[return-value]
    if isinstance(profile, JDProfile) and isinstance(proposed, JDProfile):
        return _merge_jd_profile(profile, proposed, supported_facts)  # type: ignore[return-value]
    return profile


def _merge_candidate_profile(
    profile: CandidateProfile, proposed: CandidateProfile, supported_facts: List[ExtractedFact]
) -> CandidateProfile:
    merged = profile.model_copy(deep=True)
    supported_values = _supported_values(supported_facts)
    for field_name in ("education", "work_experiences", "projects", "skills", "certifications", "highlights"):
        current = list(getattr(merged, field_name))
        additions = [value for value in getattr(proposed, field_name) if _is_supported_value(value, supported_values)]
        setattr(merged, field_name, unique_preserve_order(current + additions))
    for field_name in ("risk_points", "ambiguous_points"):
        current = list(getattr(merged, field_name))
        setattr(merged, field_name, unique_preserve_order(current + list(getattr(proposed, field_name)))[:8])
    if not merged.target_role and proposed.target_role:
        merged.target_role = proposed.target_role
    if not merged.location and proposed.location:
        merged.location = proposed.location
    return merged


def _merge_jd_profile(profile: JDProfile, proposed: JDProfile, supported_facts: List[ExtractedFact]) -> JDProfile:
    merged = profile.model_copy(deep=True)
    supported_values = _supported_values(supported_facts)
    for field_name in (
        "responsibilities",
        "required_skills",
        "nice_to_have_skills",
        "industry_background",
        "hard_requirements",
    ):
        current = list(getattr(merged, field_name))
        additions = [value for value in getattr(proposed, field_name) if _is_supported_value(value, supported_values)]
        setattr(merged, field_name, unique_preserve_order(current + additions))
    if merged.job_title == "未命名岗位" and proposed.job_title:
        merged.job_title = proposed.job_title
    if not merged.years_required and proposed.years_required:
        merged.years_required = proposed.years_required
    if merged.seniority == "未说明" and proposed.seniority:
        merged.seniority = proposed.seniority
    return merged


def _supported_values(facts: Iterable[ExtractedFact]) -> List[str]:
    values = []
    for fact in facts:
        values.extend([fact.value, fact.evidence])
    return [_normalize_for_evidence(value) for value in values if value]


def _is_supported_value(value: str, supported_values: List[str]) -> bool:
    normalized = _normalize_for_evidence(value)
    if not normalized:
        return False
    return any(normalized in supported or supported in normalized for supported in supported_values)


def _normalize_for_evidence(text: str) -> str:
    return "".join(str(text).lower().split())


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
