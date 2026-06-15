from datetime import datetime
import re
from enum import Enum
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


class ResumeQualityScoreDetail(BaseModel):
    project_score: int = 0
    skill_match_score: int = 0
    content_score: int = 0
    structure_score: int = 0
    expression_score: int = 0

    @field_validator(
        "project_score",
        "skill_match_score",
        "content_score",
        "structure_score",
        "expression_score",
        mode="before",
    )
    @classmethod
    def clamp_quality_score(cls, value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, (float, int, str)):
            text = str(value).strip()
            if text:
                try:
                    return max(0, min(100, int(round(float(text)))))
                except ValueError:
                    return 0
        return 0


class ResumeQualitySuggestion(BaseModel):
    category: str
    priority: str
    issue: str
    recommendation: str


class ResumeQualityReport(BaseModel):
    overall_score: int
    score_detail: ResumeQualityScoreDetail
    summary: str
    original_text: Optional[str] = None
    strengths: List[str] = Field(default_factory=list)
    suggestions: List[ResumeQualitySuggestion] = Field(default_factory=list)

    @field_validator("overall_score")
    @classmethod
    def clamp_overall_score(cls, value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, (float, int, str)):
            text = str(value).strip()
            if text:
                try:
                    return max(0, min(100, int(round(float(text)))))
                except ValueError:
                    return 0
        return 0


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


class AuditEvent(BaseModel):
    event: str
    stage: str
    failure_code: str
    message: str
    fallback_strategy: str
    run_id: Optional[str] = None
    candidate_id: Optional[str] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    invalid_requirements: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class AgentSkillCategory(BaseModel):
    key: str
    label: str
    priority: str = "normal"
    weight: float = 1.0
    ref: Optional[str] = None


class AgentSkill(BaseModel):
    id: str
    name: str
    description: str = ""
    keywords: List[str] = Field(default_factory=list)
    categories: List[AgentSkillCategory] = Field(default_factory=list)
    question_focuses: List[str] = Field(default_factory=list)
    rubric_focuses: List[str] = Field(default_factory=list)
    followup_style: str = ""
    body: str = ""


class SkillRouteResult(BaseModel):
    position_name: str
    skill_id: str
    skill_name: str
    route_result: str
    confidence: float = 0
    reason: str
    source: str = "keyword"

    @field_validator("confidence")
    @classmethod
    def clamp_route_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))


class AgentPlanStep(BaseModel):
    step_id: str
    title: str
    tool_name: str
    intent: str
    status: str = "pending"
    requires_evidence: bool = True


class AgentPlan(BaseModel):
    plan_id: str
    objective: str
    strategy: str = "code_driven_orchestration_with_llm_specialists"
    selected_skill_ids: List[str] = Field(default_factory=list)
    question_budget: int = 10
    followup_policy: str = "3-5 static followups plus dynamic per-answer followup when evidence is weak."
    evidence_requirements: List[str] = Field(default_factory=list)
    stop_conditions: List[str] = Field(default_factory=list)
    steps: List[AgentPlanStep] = Field(default_factory=list)


class AgentState(BaseModel):
    plan_id: str
    status: str = "planned"
    current_step_id: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    memory_refs: List[str] = Field(default_factory=list)
    tool_call_ids: List[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ToolCallRecord(BaseModel):
    call_id: str
    tool_name: str
    stage: str
    status: str = "success"
    run_id: Optional[str] = None
    candidate_id: Optional[str] = None
    input_summary: str = ""
    output_summary: str = ""
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RunMetadata(BaseModel):
    jd_text_hash: str = ""
    llm_model: str = ""
    prompt_versions: Dict[str, str] = Field(default_factory=dict)
    scoring_policy_version: str = "backend_score_policy@v1"
    rubric_version: str = "dynamic_jd_rubric@v1"


class DimensionExplanation(BaseModel):
    dimension: str
    score: float = 0
    max_score: float = 0
    summary: str


class InterviewQuestion(BaseModel):
    question: str
    focus: str
    scoring_criteria: str


class FollowUpQuestion(BaseModel):
    question: str
    reason: str
    related_evidence: Optional[str] = None


class InterviewAnswerFollowUpRequest(BaseModel):
    candidate_id: str
    question_index: int
    candidate_answer: str


class InterviewAnswerFollowUp(BaseModel):
    question_index: int
    original_question: str
    candidate_answer: str
    answer_summary: str
    clarity_score: int = 0
    depth_score: int = 0
    evidence_consistency: str = "weak"
    issues: List[str] = Field(default_factory=list)
    followup_needed: bool = True
    followup_question: str
    reason: str
    expected_signal: str
    source: str = "rules"

    @field_validator("clarity_score", "depth_score")
    @classmethod
    def clamp_answer_score(cls, value: int) -> int:
        return max(0, min(100, int(value)))


class InterviewTurnInputMetadata(BaseModel):
    source: str = "text"
    transcript: Optional[str] = None
    confidence: Optional[float] = None
    locale: Optional[str] = None
    finalized: bool = True
    raw_text: Optional[str] = None


class InterviewSessionQuestion(BaseModel):
    question: str
    focus: str = ""
    scoring_criteria: str = ""
    source: str = "planned"
    question_index: int = 0
    skill_id: Optional[str] = None
    stage: Optional[str] = None


class InterviewTurn(BaseModel):
    turn_index: int
    question: InterviewSessionQuestion
    answer: str
    answer_source: Optional[str] = None
    answer_metadata: Optional[InterviewTurnInputMetadata] = None
    diagnosis: InterviewAnswerFollowUp
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InterviewFinalReport(BaseModel):
    overall_score: int = 0
    clarity_score: int = 0
    depth_score: int = 0
    evidence_consistency: str = "weak"
    recommendation: str = "继续观察"
    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    summary: str = ""
    next_steps: List[str] = Field(default_factory=list)

    @field_validator("overall_score", "clarity_score", "depth_score")
    @classmethod
    def clamp_interview_score(cls, value: int) -> int:
        return max(0, min(100, int(value)))


class InterviewSession(BaseModel):
    session_id: str
    run_id: str
    candidate_id: str
    mode: str = "structured"
    direction: str = ""
    difficulty: str = ""
    interviewer_style: str = ""
    skill_id: Optional[str] = None
    skill_name: Optional[str] = None
    flow: List[str] = Field(default_factory=list)
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    current_question: Optional[InterviewSessionQuestion] = None
    turns: List[InterviewTurn] = Field(default_factory=list)
    final_report: Optional[InterviewFinalReport] = None


class InterviewStartRequest(BaseModel):
    candidate_id: str
    mode: str = "structured"
    skill_id: Optional[str] = None


class InterviewTurnRequest(BaseModel):
    candidate_answer: str
    answer_metadata: Optional[InterviewTurnInputMetadata] = None


class VoiceAsrSettings(BaseModel):
    model: str = "qwen3-asr-flash-realtime"
    sample_rate: int = 16000
    input_audio_format: str = "pcm"
    language: str = "zh"
    server_vad: bool = True
    silence_duration_ms: int = 400


class VoiceTtsSettings(BaseModel):
    model: str = "qwen3-tts-flash-realtime"
    voice: str = "Cherry"
    response_format: str = "pcm"
    sample_rate: int = 24000


class VoiceSettingsResponse(BaseModel):
    provider_id: str = "dashscope"
    api_key_configured: bool = False
    api_key_source: str = "none"
    asr: VoiceAsrSettings = Field(default_factory=VoiceAsrSettings)
    tts: VoiceTtsSettings = Field(default_factory=VoiceTtsSettings)


class VoiceSettingsUpdateRequest(BaseModel):
    asr: Optional[VoiceAsrSettings] = None
    tts: Optional[VoiceTtsSettings] = None


class VoiceInterviewCreateRequest(BaseModel):
    interview_session_id: str


class VoiceInterviewSession(BaseModel):
    voice_session_id: str
    interview_session_id: str
    status: str = "active"
    websocket_url: str
    created_at: datetime
    updated_at: datetime


class ModelProvider(BaseModel):
    id: str
    name: str
    model: str
    base_url: str
    api_key_configured: bool = False
    api_key_source: str = "none"
    is_default: bool = False


class ModelProviderSettingsResponse(BaseModel):
    default_provider_id: str
    providers: List[ModelProvider]


class ModelProviderDefaultRequest(BaseModel):
    provider_id: str


class ModelProviderApiKeyRequest(BaseModel):
    api_key: str


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


class CandidateSourceFile(BaseModel):
    filename: str
    content_type: Optional[str] = None


class CandidateReport(BaseModel):
    candidate_id: str
    source_name: str
    source_file: Optional[CandidateSourceFile] = None
    profile: CandidateProfile
    match_report: MatchReport
    resume_quality: Optional[ResumeQualityReport] = None
    resume_text_hash: Optional[str] = None
    parse_warnings: List[str] = Field(default_factory=list)
    extraction_facts: List[ExtractedFact] = Field(default_factory=list)


class RunReport(BaseModel):
    run_id: str
    created_at: datetime
    jd_profile: JDProfile
    jd_extraction_facts: List[ExtractedFact] = Field(default_factory=list)
    candidates: List[CandidateReport]
    warnings: List[str] = Field(default_factory=list)
    metadata: RunMetadata = Field(default_factory=RunMetadata)
    audit_events: List[AuditEvent] = Field(default_factory=list)
    agent_plan: Optional[AgentPlan] = None
    agent_state: Optional[AgentState] = None
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)


class ResumeAnalysisStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ResumeStorageInfo(BaseModel):
    file_key: str = ""
    file_url: str = ""
    resume_id: int


class ResumeFileSummary(BaseModel):
    id: int
    filename: str
    analyze_status: str


class ResumeUploadResponse(BaseModel):
    resume: Optional[ResumeFileSummary] = None
    analysis: Optional[ResumeQualityReport] = None
    storage: ResumeStorageInfo
    duplicate: bool = False


class ResumeListItem(BaseModel):
    id: int
    filename: str
    file_size: int
    uploaded_at: datetime
    access_count: int = 0
    latest_score: Optional[int] = None
    last_analyzed_at: Optional[datetime] = None
    analyze_status: str
    analyze_error: Optional[str] = None


class ResumeAnalysisHistoryItem(BaseModel):
    analysis_id: int
    created_at: datetime
    overall_score: int
    score_detail: ResumeQualityScoreDetail
    summary: str
    strengths: List[str] = Field(default_factory=list)
    suggestions: List[ResumeQualitySuggestion] = Field(default_factory=list)
    original_text: Optional[str] = None


class ResumeDetailResponse(BaseModel):
    id: int
    filename: str
    file_size: int
    content_type: Optional[str]
    uploaded_at: datetime
    access_count: int = 0
    analyze_status: str
    analyze_error: Optional[str] = None
    resume_text: str
    analyses: List[ResumeAnalysisHistoryItem] = Field(default_factory=list)
