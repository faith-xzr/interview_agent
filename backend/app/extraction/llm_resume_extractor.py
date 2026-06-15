from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

from app.llm_timeouts import LLM_JSON_TIMEOUT_SECONDS
from app.schemas import CandidateProfile, ExtractedFact
from app.text_utils import unique_preserve_order

PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "extraction" / "resume_profile.md"
)
PROMPT_PLACEHOLDER = "{{RESUME_TEXT}}"
SYSTEM_PROMPT = (
    "你是招聘简历关键能力抽取助手，只输出 JSON。"
    "不要抽取基础联系方式；所有事实必须有简历原文 evidence 支撑。"
)
EXTRACTOR_TAG = "llm_resume"

_IMPORTANCE_TO_CONFIDENCE = {
    "high": 0.9,
    "medium": 0.82,
    "low": 0.72,
}

_SECTION_ALIASES = {
    "basic": "basic",
    "基本信息": "basic",
    "个人信息": "basic",
    "求职意向": "basic",
    "education": "education",
    "学历背景": "education",
    "教育背景": "education",
    "教育经历": "education",
    "experience": "experience",
    "work": "experience",
    "实习/工作经验": "experience",
    "实习经历": "experience",
    "工作经历": "experience",
    "工作经验": "experience",
    "projects": "projects",
    "project": "projects",
    "项目经验": "projects",
    "项目经历": "projects",
    "skills": "skills",
    "skill": "skills",
    "专业技能": "skills",
    "技能": "skills",
    "certifications": "certifications",
    "certification": "certifications",
    "证书资质": "certifications",
    "证书": "certifications",
    "summary": "summary",
    "自我评价": "summary",
    "个人优势": "summary",
}

_FACT_TYPE_ALIASES = {
    "education_summary": "education_summary",
    "学历背景": "education_summary",
    "education": "education_summary",
    "work_summary": "work_summary",
    "experience_summary": "work_summary",
    "实习/工作经验": "work_summary",
    "工作经历": "work_summary",
    "实习经历": "work_summary",
    "project": "project",
    "项目经验": "project",
    "项目经历": "project",
    "skill": "skill",
    "专业技能": "skill",
    "技能": "skill",
    "certification": "certification",
    "证书资质": "certification",
    "证书": "certification",
    "highlight": "highlight",
    "亮点": "highlight",
    "metric": "metric",
    "量化成果": "metric",
    "risk": "risk",
    "风险": "risk",
}

_GENERIC_NAMES = {"候选人", "未知候选人", "简历候选人", "candidate", "Candidate"}


def extract_resume_with_llm(
    llm,
    text: str,
    source_name: str = "简历",
) -> Optional[Tuple[CandidateProfile, List[ExtractedFact]]]:
    if not getattr(llm, "available", False):
        return None
    if not text or not text.strip():
        return None

    payload = llm.complete_json(
        SYSTEM_PROMPT,
        _build_user_prompt(text, source_name),
        timeout=LLM_JSON_TIMEOUT_SECONDS,
    )
    if not isinstance(payload, dict):
        return None

    raw_facts = payload.get("facts")
    if not isinstance(raw_facts, list):
        return None

    facts = _parse_facts(raw_facts, text)
    raw_profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    try:
        profile = CandidateProfile.model_validate(raw_profile)
    except Exception:
        return None
    profile = _filter_supported_profile(profile, facts, text)

    if not _has_profile_signal(profile) and not facts:
        return None
    return profile, facts


def _build_user_prompt(text: str, source_name: str) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.replace("{{SOURCE_NAME}}", source_name)
    if PROMPT_PLACEHOLDER in prompt:
        return prompt.replace(PROMPT_PLACEHOLDER, text)
    return f"{prompt}\n\n# 待抽取的简历原文\n\n{text}"


def _parse_facts(raw_facts: Iterable[Any], text: str) -> List[ExtractedFact]:
    normalized_text = _normalize(text)
    facts: List[ExtractedFact] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in raw_facts:
        if not isinstance(raw, dict):
            continue

        value = _clean_text(raw.get("summary") or raw.get("value"))
        if not _is_meaningful_value(value):
            continue

        evidence = _resolve_evidence(raw.get("evidence"), normalized_text)
        if not evidence:
            continue

        section = _normalize_section(raw.get("section"))
        fact_type = _normalize_fact_type(raw, section)
        if section == "basic" or fact_type in {"basic", "target_role", "location", "contact"}:
            continue

        key = (fact_type, value.lower(), evidence.lower())
        if key in seen:
            continue
        seen.add(key)

        line_start, line_end = _locate_evidence_lines(text, evidence)
        try:
            facts.append(
                ExtractedFact.model_validate(
                    {
                        "fact_type": fact_type,
                        "value": value,
                        "normalized_value": _clean_text(raw.get("category") or raw.get("label")) or None,
                        "evidence": evidence,
                        "section": section,
                        "line_start": line_start,
                        "line_end": line_end,
                        "confidence": _resolve_confidence(raw.get("importance") or raw.get("confidence")),
                        "extractor": EXTRACTOR_TAG,
                    }
                )
            )
        except Exception:
            continue
    return facts


def _resolve_evidence(raw_evidence: Any, normalized_text: str) -> str:
    candidates: List[str] = []
    if isinstance(raw_evidence, str):
        candidates.append(raw_evidence)
    elif isinstance(raw_evidence, list):
        for item in raw_evidence:
            if isinstance(item, str):
                candidates.append(item)
            elif isinstance(item, dict):
                value = item.get("text") or item.get("snippet") or item.get("evidence")
                if isinstance(value, str):
                    candidates.append(value)

    kept = []
    for candidate in candidates:
        snippet = candidate.strip()
        if not snippet:
            continue
        if _normalize(snippet) in normalized_text:
            kept.append(snippet)
    return "\n".join(unique_preserve_order(kept))


def _normalize_section(value: Any) -> str:
    cleaned = _clean_text(value)
    return _SECTION_ALIASES.get(cleaned, _SECTION_ALIASES.get(cleaned.lower(), "unknown"))


def _normalize_fact_type(raw: dict[str, Any], section: str) -> str:
    for key in ("category", "fact_type", "label"):
        cleaned = _clean_text(raw.get(key))
        if not cleaned:
            continue
        fact_type = _FACT_TYPE_ALIASES.get(cleaned, _FACT_TYPE_ALIASES.get(cleaned.lower()))
        if fact_type:
            return fact_type
    if section == "education":
        return "education_summary"
    if section == "experience":
        return "work_summary"
    if section == "projects":
        return "project"
    if section == "skills":
        return "skill"
    if section == "certifications":
        return "certification"
    return "highlight"


def _resolve_confidence(value: Any) -> float:
    if isinstance(value, str):
        return _IMPORTANCE_TO_CONFIDENCE.get(value.strip().lower(), 0.82)
    if isinstance(value, (int, float)):
        confidence = float(value)
        if 0.0 < confidence <= 1.0:
            return confidence
    return 0.82


def _filter_supported_profile(
    profile: CandidateProfile,
    facts: List[ExtractedFact],
    text: str,
) -> CandidateProfile:
    supported_values = _supported_values(facts)
    normalized_text = _normalize(text)
    filtered = profile.model_copy(deep=True)
    filtered.contacts = {}
    filtered.location = None

    for field_name in ("education", "work_experiences", "projects", "skills", "certifications", "highlights"):
        values = list(getattr(filtered, field_name))
        kept = [
            value
            for value in values
            if _is_supported_value(value, supported_values, normalized_text)
        ]
        if field_name == "education":
            kept = kept[:1]
        setattr(filtered, field_name, unique_preserve_order(kept))

    filtered.risk_points = unique_preserve_order(filtered.risk_points)[:5]
    filtered.ambiguous_points = unique_preserve_order(filtered.ambiguous_points)[:5]
    if filtered.target_role and not _is_supported_value(filtered.target_role, supported_values, normalized_text):
        filtered.target_role = None
    return filtered


def _supported_values(facts: Iterable[ExtractedFact]) -> List[str]:
    values = []
    for fact in facts:
        values.extend([fact.value, fact.evidence])
    return [_normalize(value) for value in values if value]


def _is_supported_value(value: str, supported_values: List[str], normalized_text: str) -> bool:
    normalized = _normalize(value)
    if not normalized:
        return False
    if normalized in normalized_text:
        return True
    return any(normalized in supported or supported in normalized for supported in supported_values)


def _has_profile_signal(profile: CandidateProfile) -> bool:
    return any(
        [
            profile.education,
            profile.work_experiences,
            profile.projects,
            profile.skills,
            profile.certifications,
            profile.highlights,
        ]
    )


def _locate_evidence_lines(text: str, evidence: str) -> tuple[Optional[int], Optional[int]]:
    evidence_lines = [_normalize(line) for line in evidence.splitlines() if line.strip()]
    if not evidence_lines:
        return None, None
    source_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    starts = []
    for index, line in enumerate(source_lines, start=1):
        normalized_line = _normalize(line)
        if not normalized_line:
            continue
        if any(part in normalized_line or normalized_line in part for part in evidence_lines):
            starts.append(index)
    if not starts:
        return None, None
    return min(starts), max(starts)


def _is_meaningful_value(value: str) -> bool:
    if len(value.strip()) < 2:
        return False
    return not bool(value.isupper() and "_" in value)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize(value: str) -> str:
    return "".join(str(value).lower().split())
