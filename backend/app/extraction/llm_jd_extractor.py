from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

from app.schemas import ExtractedFact, JDProfile

PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "extraction" / "jd_requirements.md"
)
PROMPT_PLACEHOLDER = "{{JD_TEXT}}"
SYSTEM_PROMPT = (
    "你是招聘 JD 解读助手，端到端读 JD 后只输出 JSON。"
    "key_points 每条 summary 必须是独立可读的整句，"
    "evidence 必须来自原文，禁止编造。"
)
EXTRACTOR_TAG = "llm_end_to_end"

_KNOWN_CATEGORIES = {
    "skill",
    "nice_to_have_skill",
    "responsibility",
    "years",
    "seniority",
    "industry",
    "hard_requirement",
    "other",
}

_IMPORTANCE_TO_CONFIDENCE = {
    "high": 0.92,
    "medium": 0.82,
    "low": 0.7,
}

_HEADING_HINTS = (
    "核心职责",
    "岗位职责",
    "工作职责",
    "任职要求",
    "岗位要求",
    "任职资格",
    "技能要求",
    "加分项",
    "加分",
    "硬性",
    "我们希望你",
    "你将",
    "你需要",
    "职位描述",
    "岗位描述",
)


def extract_jd_with_llm(llm, text: str) -> Optional[Tuple[JDProfile, List[ExtractedFact]]]:
    if not getattr(llm, "available", False):
        return None
    if not text or not text.strip():
        return None

    payload = llm.complete_json(SYSTEM_PROMPT, _build_user_prompt(text))
    if not isinstance(payload, dict):
        return None

    raw_points = payload.get("key_points")
    if not isinstance(raw_points, list):
        return None

    facts = _parse_key_points(raw_points, text)
    if not facts:
        return None

    profile = _derive_profile(facts)
    return profile, facts


def _build_user_prompt(text: str) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    if PROMPT_PLACEHOLDER in template:
        return template.replace(PROMPT_PLACEHOLDER, text)
    return f"{template}\n\n# 待抽取的 JD 原文\n\n{text}"


def _parse_key_points(raw_points: Iterable[Any], text: str) -> List[ExtractedFact]:
    normalized_text = _normalize(text)
    facts: List[ExtractedFact] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_points:
        if not isinstance(raw, dict):
            continue

        summary = _clean_text(raw.get("summary"))
        if not _is_meaningful_summary(summary):
            continue

        evidence = _resolve_evidence(raw.get("evidence"), normalized_text)
        if not evidence:
            continue

        topic = _clean_text(raw.get("topic")) or "关键点"
        category = _normalize_category(raw.get("category"))
        confidence = _resolve_confidence(raw.get("importance"))

        key = (topic.lower(), summary.lower())
        if key in seen:
            continue
        seen.add(key)

        try:
            fact = ExtractedFact.model_validate(
                {
                    "fact_type": topic,
                    "value": summary,
                    "normalized_value": category or None,
                    "evidence": evidence,
                    "section": "jd",
                    "confidence": confidence,
                    "extractor": EXTRACTOR_TAG,
                }
            )
        except Exception:
            continue
        facts.append(fact)
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
                text_val = item.get("text") or item.get("snippet") or ""
                if isinstance(text_val, str):
                    candidates.append(text_val)

    kept: List[str] = []
    for snippet in candidates:
        snippet = snippet.strip()
        if not snippet:
            continue
        if _normalize(snippet) in normalized_text:
            kept.append(snippet)
    if not kept:
        return ""
    return "\n".join(kept)


def _is_meaningful_summary(value: str) -> bool:
    if not value:
        return False
    stripped = value.strip().rstrip("：:，,。.；;、")
    if len(stripped) < 4:
        return False
    if stripped in _HEADING_HINTS:
        return False
    for hint in _HEADING_HINTS:
        if stripped == hint or stripped == f"{hint}：" or stripped == f"{hint}:":
            return False
    return True


def _normalize_category(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = value.strip().lower()
    if cleaned in _KNOWN_CATEGORIES:
        return cleaned
    return ""


def _resolve_confidence(importance: Any) -> float:
    if isinstance(importance, str):
        return _IMPORTANCE_TO_CONFIDENCE.get(importance.strip().lower(), 0.8)
    if isinstance(importance, (int, float)):
        value = float(importance)
        if 0.0 < value <= 1.0:
            return value
    return 0.8


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize(value: str) -> str:
    return "".join(str(value).lower().split())


def _derive_profile(facts: List[ExtractedFact]) -> JDProfile:
    job_titles: List[str] = []
    responsibilities: List[str] = []
    required_skills: List[str] = []
    nice_to_have_skills: List[str] = []
    industries: List[str] = []
    hard_requirements: List[str] = []
    seniority = ""
    years_required = 0

    for fact in facts:
        category = (fact.normalized_value or "").strip().lower()
        value = fact.value.strip()
        topic = fact.fact_type.strip().lower()

        if category == "skill":
            required_skills.append(value)
        elif category == "nice_to_have_skill":
            nice_to_have_skills.append(value)
        elif category == "responsibility":
            responsibilities.append(value)
        elif category == "industry":
            industries.append(value)
        elif category == "hard_requirement":
            hard_requirements.append(value)
        elif category == "seniority":
            seniority = seniority or value
        elif category == "years":
            digits = _first_int(value) or _first_int(fact.evidence)
            if digits:
                years_required = max(years_required, digits)
        elif "岗位" in topic or "job" in topic:
            job_titles.append(value)

    profile_data = {
        "job_title": job_titles[0] if job_titles else "未命名岗位",
        "responsibilities": responsibilities,
        "required_skills": required_skills,
        "nice_to_have_skills": nice_to_have_skills,
        "seniority": seniority or "未说明",
        "years_required": years_required,
        "industry_background": industries,
        "hard_requirements": hard_requirements,
    }
    try:
        return JDProfile.model_validate(profile_data)
    except Exception:
        return JDProfile()


def _first_int(value: str) -> int:
    digits = ""
    for char in value:
        if char.isdigit():
            digits += char
        elif digits:
            break
    return int(digits) if digits else 0
