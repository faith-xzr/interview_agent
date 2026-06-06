from datetime import datetime
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        parts = [_coerce_text(item) for item in value.values()]
        return " ".join(part for part in parts if part)
    if isinstance(value, (list, tuple, set)):
        parts = [_coerce_text(item) for item in value]
        return " ".join(part for part in parts if part)
    return str(value).strip()


def _coerce_text_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        items = [_coerce_text(item) for item in value]
        return [item for item in items if item]
    text = _coerce_text(value)
    return [text] if text else []


def _coerce_delimited_text_list(value: Any) -> List[str]:
    items: List[str] = []
    for item in _coerce_text_list(value):
        for part in re.split(r"\s*[、,，;；|]\s*", item):
            text = part.strip().strip("。.")
            if text:
                items.append(text)
    return items


class JDProfile(BaseModel):
    job_title: str = "未命名岗位"
    responsibilities: List[str] = Field(default_factory=list)
    required_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    seniority: str = "未说明"
    years_required: int = 0
    industry_background: List[str] = Field(default_factory=list)
    hard_requirements: List[str] = Field(default_factory=list)

    @field_validator(
        "responsibilities",
        "industry_background",
        "hard_requirements",
        mode="before",
    )
    @classmethod
    def normalize_text_lists(cls, value: Any) -> List[str]:
        return _coerce_text_list(value)

    @field_validator("required_skills", "nice_to_have_skills", mode="before")
    @classmethod
    def normalize_skill_lists(cls, value: Any) -> List[str]:
        return _coerce_delimited_text_list(value)

    @field_validator("years_required", mode="before")
    @classmethod
    def normalize_years_required(cls, value: Any) -> int:
        if value is None or value == "":
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else 0


class CandidateProfile(BaseModel):
    name: str = "未知候选人"
    target_role: Optional[str] = None
    contacts: Dict[str, str] = Field(default_factory=dict)
    location: Optional[str] = None
    education: List[str] = Field(default_factory=list)
    work_experiences: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)
    risk_points: List[str] = Field(default_factory=list)
    ambiguous_points: List[str] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> str:
        return _coerce_text(value) or "未知候选人"

    @field_validator("contacts", mode="before")
    @classmethod
    def normalize_contacts(cls, value: Any) -> Dict[str, str]:
        if not isinstance(value, dict):
            return {}
        contacts: Dict[str, str] = {}
        for key, item in value.items():
            text = _coerce_text(item)
            if text:
                contacts[str(key)] = text
        return contacts

    @field_validator(
        "education",
        "work_experiences",
        "projects",
        "highlights",
        "risk_points",
        "ambiguous_points",
        mode="before",
    )
    @classmethod
    def normalize_text_lists(cls, value: Any) -> List[str]:
        return _coerce_text_list(value)

    @field_validator("skills", "certifications", mode="before")
    @classmethod
    def normalize_skill_lists(cls, value: Any) -> List[str]:
        return _coerce_delimited_text_list(value)


class ExtractedFact(BaseModel):
    fact_type: str
    value: str
    normalized_value: Optional[str] = None
    evidence: str
    section: str = "unknown"
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    confidence: float = 0.8
    extractor: str = "section_rules"


class ScoreBreakdown(BaseModel):
    skill_score: int = 0
    experience_score: int = 0
    project_score: int = 0
    industry_score: int = 0
    education_score: int = 0
    risk_deduction: int = 0


class EvidenceSnippet(BaseModel):
    source: str
    text: str
    section: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    fact_type: Optional[str] = None


class RequirementMatch(BaseModel):
    dimension: str
    requirement: str
    requirement_type: str = "jd_requirement"
    status: str
    max_score: float = 0
    contribution: float = 0
    confidence: float = 0
    reason: str
    evidence: List[EvidenceSnippet] = Field(default_factory=list)


class DimensionExplanation(BaseModel):
    dimension: str
    score: float = 0
    max_score: float = 0
    summary: str


class InterviewQuestion(BaseModel):
    question: str
    focus: str
    difficulty: str
    scoring_criteria: str
    evidence: Optional[str] = None


class FollowUpQuestion(BaseModel):
    question: str
    reason: str
    related_evidence: Optional[str] = None


class MatchReport(BaseModel):
    total_score: int
    decision: str
    dimension_scores: Dict[str, int]
    score_breakdown: ScoreBreakdown
    match_reasons: List[str]
    gap_reasons: List[str]
    evidence_snippets: List[EvidenceSnippet] = Field(default_factory=list)
    requirement_matches: List[RequirementMatch] = Field(default_factory=list)
    dimension_explanations: List[DimensionExplanation] = Field(default_factory=list)
    interview_questions: List[InterviewQuestion] = Field(default_factory=list)
    followup_questions: List[FollowUpQuestion] = Field(default_factory=list)

    @field_validator("total_score")
    @classmethod
    def clamp_score(cls, value: int) -> int:
        return max(0, min(100, value))


class CandidateReport(BaseModel):
    candidate_id: str
    source_name: str
    profile: CandidateProfile
    match_report: MatchReport
    parse_warnings: List[str] = Field(default_factory=list)
    extraction_facts: List[ExtractedFact] = Field(default_factory=list)


class RunReport(BaseModel):
    run_id: str
    created_at: datetime
    jd_profile: JDProfile
    jd_extraction_facts: List[ExtractedFact] = Field(default_factory=list)
    candidates: List[CandidateReport]
    warnings: List[str] = Field(default_factory=list)
