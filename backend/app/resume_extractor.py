import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.fallback_ai import extract_candidate_profile as extract_legacy_candidate_profile
from app.schemas import CandidateProfile, ExtractedFact
from app.text_utils import unique_preserve_order


@dataclass
class ResumeLine:
    line_number: int
    text: str


@dataclass
class ExperienceEntry:
    company: str
    title: str
    line_number: int
    responsibilities: List[ResumeLine] = field(default_factory=list)


@dataclass
class ResumeExtractionResult:
    profile: CandidateProfile
    facts: List[ExtractedFact]
    sections: Dict[str, List[ResumeLine]]


SECTION_HEADERS = {
    "基本信息": "basic",
    "个人信息": "basic",
    "求职意向": "basic",
    "教育经历": "education",
    "教育背景": "education",
    "工作经历": "experience",
    "工作经验": "experience",
    "职业经历": "experience",
    "项目经历": "projects",
    "项目经验": "projects",
    "专业技能": "skills",
    "技能": "skills",
    "技能清单": "skills",
    "证书": "certifications",
    "资格证书": "certifications",
    "自我评价": "summary",
}

METRIC_RE = re.compile(
    r"\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?"
    r"|\d+\+\s*(?:种|个|本|场|条|处|人|倍)?"
    r"|\d+(?:\.\d+)?\s*(?:万|%|个|本|场|条|种|处|人|倍)"
)
CONTACT_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
AI_TERMS = ["AI", "Prompt", "CoT", "BLEU", "ASR", "机器翻译", "大模型", "语料库", "微调", "MTPE"]
PROJECT_KEYWORDS = (
    "项目",
    "平台",
    "系统",
    "搭建",
    "构建",
    "开发",
    "评估",
    "Prompt",
    "RAG",
    "AI",
    "模型",
    "语料",
    "ASR",
    "BLEU",
    "MTPE",
)
HIGHLIGHT_KEYWORDS = ("负责", "主导", "搭建", "构建", "优化", "提升", "引入", "开发", "协调")


def extract_resume_profile(text: str, source_name: str = "简历") -> ResumeExtractionResult:
    sections = split_resume_sections(text)
    profile = extract_legacy_candidate_profile(text, source_name).model_copy(deep=True)
    facts: List[ExtractedFact] = []

    _apply_basic_section(profile, facts, sections.get("basic", []))
    _apply_education_section(profile, facts, sections.get("education", []))
    experience_entries = _apply_experience_section(profile, facts, sections.get("experience", []))
    _apply_project_section(profile, facts, sections.get("projects", []))
    _apply_skills_section(profile, facts, sections.get("skills", []))
    _apply_certification_section(profile, facts, sections.get("certifications", []))
    facts.extend(_extract_metric_facts(sections))
    facts.extend(_extract_ai_evidence_facts(sections))
    _apply_quality_notes(profile, experience_entries)

    profile.skills = unique_preserve_order(profile.skills)
    profile.projects = unique_preserve_order(profile.projects)
    profile.highlights = unique_preserve_order(profile.highlights)
    profile.ambiguous_points = unique_preserve_order(profile.ambiguous_points)
    return ResumeExtractionResult(profile=profile, facts=_dedupe_facts(facts), sections=sections)


def split_resume_sections(text: str) -> Dict[str, List[ResumeLine]]:
    sections: Dict[str, List[ResumeLine]] = {"basic": []}
    current = "basic"
    for line_number, raw_line in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        section = _match_section_header(stripped)
        if section:
            current = section
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(ResumeLine(line_number=line_number, text=stripped))
    return sections


def _match_section_header(text: str) -> Optional[str]:
    normalized = text.strip().strip(":：")
    return SECTION_HEADERS.get(normalized)


def _apply_basic_section(profile: CandidateProfile, facts: List[ExtractedFact], lines: List[ResumeLine]) -> None:
    if lines and _looks_like_name(lines[0].text):
        profile.name = lines[0].text
    for line in lines:
        target = _extract_labeled_value(line.text, ("求职意向", "应聘岗位", "目标岗位"))
        if target:
            profile.target_role = target
            facts.append(_fact("target_role", target, line, "basic", confidence=0.92))

        phone = _extract_labeled_value(line.text, ("电话", "手机", "联系方式"))
        if phone:
            profile.contacts["phone"] = phone
        email = CONTACT_EMAIL_RE.search(line.text)
        if email:
            profile.contacts["email"] = email.group(0)

        location = _extract_labeled_value(line.text, ("地址", "所在地", "现居地", "城市"))
        if location:
            profile.location = location
            facts.append(_fact("location", location, line, "basic", confidence=0.85))


def _apply_education_section(profile: CandidateProfile, facts: List[ExtractedFact], lines: List[ResumeLine]) -> None:
    if not lines:
        return
    profile.education = [line.text for line in lines]
    for line in lines:
        facts.append(_fact("education", line.text, line, "education", confidence=0.86))
        for degree in ("博士", "硕士", "本科", "专科", "MBA"):
            if degree in line.text:
                facts.append(_fact("degree", degree, line, "education", confidence=0.88))
                break


def _apply_experience_section(
    profile: CandidateProfile, facts: List[ExtractedFact], lines: List[ResumeLine]
) -> List[ExperienceEntry]:
    entries: List[ExperienceEntry] = []
    current: Optional[ExperienceEntry] = None
    loose_responsibilities: List[ResumeLine] = []

    for line in lines:
        bullet = _strip_bullet(line.text)
        if bullet != line.text:
            if current is not None:
                current.responsibilities.append(ResumeLine(line.line_number, bullet))
            else:
                loose_responsibilities.append(ResumeLine(line.line_number, bullet))
            continue

        parsed = _parse_experience_header(line.text)
        if parsed:
            company, title = parsed
            current = ExperienceEntry(company=company, title=title, line_number=line.line_number)
            entries.append(current)
            facts.append(_fact("experience_position", f"{company} | {title}", line, "experience", confidence=0.9))
            continue

        loose_responsibilities.append(line)

    if entries:
        profile.work_experiences = [_format_experience(entry) for entry in entries]
    elif loose_responsibilities:
        profile.work_experiences = [line.text for line in loose_responsibilities]

    responsibility_lines = loose_responsibilities[:]
    for entry in entries:
        responsibility_lines.extend(entry.responsibilities)
        for responsibility in entry.responsibilities:
            facts.append(_fact("responsibility", responsibility.text, responsibility, "experience", confidence=0.78))

    projects = [line.text for line in responsibility_lines if _looks_project_like(line.text)]
    highlights = [line.text for line in responsibility_lines if _looks_highlight_like(line.text)]
    if projects:
        profile.projects = unique_preserve_order(projects + profile.projects)
    if highlights:
        profile.highlights = unique_preserve_order(highlights + profile.highlights)
    return entries


def _apply_project_section(profile: CandidateProfile, facts: List[ExtractedFact], lines: List[ResumeLine]) -> None:
    if not lines:
        return
    projects = [_strip_bullet(line.text) for line in lines]
    profile.projects = unique_preserve_order(projects + profile.projects)
    for line, value in zip(lines, projects):
        facts.append(_fact("project", value, line, "projects", confidence=0.84))


def _apply_skills_section(profile: CandidateProfile, facts: List[ExtractedFact], lines: List[ResumeLine]) -> None:
    skills: List[str] = []
    for line in lines:
        for skill in _split_skills(line.text):
            skills.append(skill)
            facts.append(_fact("skill", skill, line, "skills", confidence=0.9))
    if skills:
        profile.skills = unique_preserve_order(profile.skills + skills)


def _apply_certification_section(profile: CandidateProfile, facts: List[ExtractedFact], lines: List[ResumeLine]) -> None:
    certifications = [_strip_bullet(line.text) for line in lines]
    if certifications:
        profile.certifications = unique_preserve_order(profile.certifications + certifications)
    for line, value in zip(lines, certifications):
        facts.append(_fact("certification", value, line, "certifications", confidence=0.82))


def _extract_metric_facts(sections: Dict[str, List[ResumeLine]]) -> List[ExtractedFact]:
    facts: List[ExtractedFact] = []
    for section, lines in sections.items():
        for line in lines:
            for match in METRIC_RE.finditer(line.text):
                facts.append(_fact("metric", match.group(0).strip(), line, section, confidence=0.88))
    return facts


def _extract_ai_evidence_facts(sections: Dict[str, List[ResumeLine]]) -> List[ExtractedFact]:
    facts: List[ExtractedFact] = []
    for section, lines in sections.items():
        for line in lines:
            hits = [term for term in AI_TERMS if term.lower() in line.text.lower()]
            if hits:
                facts.append(_fact("domain_evidence", ", ".join(hits), line, section, confidence=0.78))
    return facts


def _apply_quality_notes(profile: CandidateProfile, entries: List[ExperienceEntry]) -> None:
    notes = list(profile.ambiguous_points)
    if entries:
        combined = " ".join(_format_experience(entry) for entry in entries)
        if not re.search(r"20\d{2}|19\d{2}|至今|现在|今", combined):
            notes.append("关键工作经历的起止时间未说明")
    if profile.projects and not any(METRIC_RE.search(item) for item in profile.projects):
        notes.append("项目结果指标和业务影响未量化")
    if not profile.projects:
        notes.append("缺少可深挖的项目经历描述")
    profile.ambiguous_points = unique_preserve_order(notes)[:5]


def _extract_labeled_value(text: str, labels: tuple[str, ...]) -> Optional[str]:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*[:：]\s*([^|]+)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _looks_like_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fa5]{2,5}", text))


def _strip_bullet(text: str) -> str:
    return re.sub(r"^[•\-\*]\s*", "", text).strip(" 。")


def _parse_experience_header(text: str) -> Optional[tuple[str, str]]:
    if "|" not in text:
        return None
    company, title = [part.strip() for part in text.split("|", 1)]
    if not company or not title:
        return None
    return company, title


def _format_experience(entry: ExperienceEntry) -> str:
    details = [f"{entry.company} | {entry.title}"]
    details.extend(line.text for line in entry.responsibilities)
    return "\n".join(details)


def _looks_project_like(text: str) -> bool:
    return any(keyword.lower() in text.lower() for keyword in PROJECT_KEYWORDS)


def _looks_highlight_like(text: str) -> bool:
    return bool(METRIC_RE.search(text)) or any(keyword in text for keyword in HIGHLIGHT_KEYWORDS)


def _split_skills(text: str) -> List[str]:
    parts = re.split(r"\s*[|；;，,、]\s*", text)
    return [part.strip() for part in parts if part.strip()]


def _fact(
    fact_type: str,
    value: str,
    line: ResumeLine,
    section: str,
    confidence: float,
    extractor: str = "section_rules",
) -> ExtractedFact:
    return ExtractedFact(
        fact_type=fact_type,
        value=value,
        normalized_value=value.strip().lower(),
        evidence=line.text,
        section=section,
        line_start=line.line_number,
        line_end=line.line_number,
        confidence=confidence,
        extractor=extractor,
    )


def _dedupe_facts(facts: List[ExtractedFact]) -> List[ExtractedFact]:
    seen = set()
    result = []
    for fact in facts:
        key = (fact.fact_type, fact.value, fact.section, fact.line_start, fact.evidence)
        if key in seen:
            continue
        seen.add(key)
        result.append(fact)
    return result
