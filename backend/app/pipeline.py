from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import uuid4

from app.agent.planner import (
    build_recruiting_agent_plan,
    complete_state,
    complete_step,
    create_agent_state,
)
from app.agent.tools import ToolRecorder
from app.audit import record_audit_event
from app.config import Settings
from app.extraction.jd_extractor import extract_jd_facts
from app.extraction.llm_jd_extractor import extract_jd_with_llm
from app.extraction.llm_resume_extractor import extract_resume_with_llm
from app.extraction.resume_extractor import extract_resume_profile
from app.fallback_ai import extract_jd_profile
from app.followups import generate_followups
from app.llm_client import LLMClient
from app.llm_timeouts import LLM_JSON_TIMEOUT_SECONDS
from app.policies import QUESTION_MATERIAL_MIN_SCORE
from app.privacy import mask_pii, restore_pii_in_data
from app.question_generation import generate_interview_questions
from app.schemas import CandidateProfile, CandidateReport, CandidateSourceFile, ExtractedFact, JDProfile, RunMetadata, RunReport
from app.scoring import score_candidate, score_candidate_with_llm, score_resume_quality
from app.skills import SkillRepository, select_skills_for_jd
from app.storage import RunStorage
from app.vector_store import VectorStore

PROMPT_VERSIONS = {
    "jd_extraction": "jd_requirements@2026-06-13",
    "resume_extraction": "resume_profile@2026-06-13",
    "resume_quality": "resume_quality@2026-06-14",
    "rubric_generation": "rubric_generation@2026-06-14",
    "requirement_matching": "requirement_matching@2026-06-14",
    "question_generation": "interview_questions@2026-06-07",
}
SCORING_POLICY_VERSION = "backend_score_policy@v1"


@dataclass(frozen=True)
class ResumeSource:
    source_name: str
    text: str
    file_content: Optional[bytes] = None
    content_type: Optional[str] = None


class RecruitingPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = RunStorage(settings.database_path)
        self.vector_store = VectorStore(settings.vector_dir, enable_chroma=settings.enable_chroma)
        self.llm = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
        self.skill_repository = SkillRepository(settings.skills_dir)

    def run(
        self,
        jd_text: str,
        resumes: List[ResumeSource],
        initial_warnings: Optional[List[str]] = None,
        existing_run: Optional[RunReport] = None,
    ) -> RunReport:
        run_id = existing_run.run_id if existing_run is not None else uuid4().hex
        request_warnings = list(initial_warnings or [])
        tool_recorder = ToolRecorder(run_id)

        if existing_run is None:
            warnings: List[str] = request_warnings
            audit_events: List[dict] = []
            metadata = RunMetadata(
                jd_text_hash=_sha256_text(jd_text),
                llm_model=self.settings.llm_model,
                prompt_versions=PROMPT_VERSIONS,
                scoring_policy_version=SCORING_POLICY_VERSION,
            )
            with tool_recorder.call(
                "extract_jd",
                "extract_jd",
                input_summary=_summarize_text(jd_text),
                metadata={"llm_available": self.llm.available},
            ) as tool_call:
                jd_diagnostics: dict[str, object] = {}
                jd_profile, jd_extraction_facts = self._extract_jd(
                    jd_text,
                    warnings,
                    diagnostics=jd_diagnostics,
                )
                tool_call.metadata.update(jd_diagnostics)
                if jd_diagnostics.get("extraction_source") == "rule_fallback":
                    self._record_llm_fallback(
                        audit_events,
                        event="extraction.jd_llm_fallback",
                        stage="jd_extraction",
                        fallback_strategy="local_rule_extraction",
                        diagnostics=jd_diagnostics,
                        run_id=run_id,
                    )
                tool_call.set_output_summary(
                    f"{jd_profile.job_title}; facts={len(jd_extraction_facts)}"
                )
            selected_skills = select_skills_for_jd(jd_profile, self.skill_repository)
            agent_plan = build_recruiting_agent_plan(jd_profile, selected_skills)
            agent_state = create_agent_state(agent_plan)
            complete_step(
                agent_state,
                "extract_jd",
                current_step_id="extract_resumes",
                tool_call_ids=[tool_call.call_id],
            )
            query_text = " ".join(
                jd_profile.required_skills + jd_profile.responsibilities + [jd_profile.job_title]
            )
            candidates: List[CandidateReport] = []
            base_tool_calls: List[object] = []
            start_candidate_index = 1
            self.vector_store.add_document(run_id, "jd", "JD", jd_text)
        else:
            warnings = list(existing_run.warnings)
            warnings.extend(request_warnings)
            metadata = existing_run.metadata.model_copy(deep=True)
            metadata.jd_text_hash = _sha256_text(jd_text)
            metadata.llm_model = self.settings.llm_model
            metadata.prompt_versions = PROMPT_VERSIONS
            metadata.scoring_policy_version = SCORING_POLICY_VERSION
            audit_events = list(existing_run.audit_events)

            jd_profile = existing_run.jd_profile
            jd_extraction_facts = list(existing_run.jd_extraction_facts)
            query_text = " ".join(
                jd_profile.required_skills + jd_profile.responsibilities + [jd_profile.job_title]
            )
            selected_skills = select_skills_for_jd(jd_profile, self.skill_repository)
            agent_plan = existing_run.agent_plan
            if agent_plan is None:
                agent_plan = build_recruiting_agent_plan(jd_profile, selected_skills)
            agent_state = existing_run.agent_state
            if agent_state is None:
                agent_state = create_agent_state(agent_plan)
                complete_state(agent_state)
            candidates = list(existing_run.candidates)
            base_tool_calls = list(existing_run.tool_calls)
            start_candidate_index = _next_candidate_index(candidates)

        new_candidates: List[CandidateReport] = []
        for index, raw_resume in enumerate(resumes):
            resume = _coerce_resume_source(raw_resume)
            source_name = resume.source_name
            resume_text = resume.text
            candidate_id = f"candidate-{start_candidate_index + index}"
            with tool_recorder.call(
                "extract_resume",
                "extract_resumes",
                candidate_id=candidate_id,
                input_summary=source_name,
                metadata={"llm_available": self.llm.available},
            ) as tool_call:
                extraction_diagnostics: dict[str, object] = {}
                profile, extraction_facts = self._extract_candidate(
                    resume_text,
                    source_name,
                    warnings,
                    diagnostics=extraction_diagnostics,
                )
                tool_call.metadata.update(extraction_diagnostics)
                if extraction_diagnostics.get("extraction_source") == "rule_fallback":
                    self._record_llm_fallback(
                        audit_events,
                        event="extraction.resume_llm_fallback",
                        stage="resume_extraction",
                        fallback_strategy="local_rule_extraction",
                        diagnostics=extraction_diagnostics,
                        run_id=run_id,
                        candidate_id=candidate_id,
                    )
                tool_call.set_output_summary(f"{profile.name}; facts={len(extraction_facts)}")

            if existing_run is None:
                complete_step(
                    agent_state,
                    "extract_resumes",
                    current_step_id="retrieve_evidence",
                    tool_call_ids=[tool_call.call_id],
                )

            self.vector_store.add_document(run_id, candidate_id, source_name, resume_text)
            with tool_recorder.call(
                "retrieve_evidence",
                "retrieve_evidence",
                candidate_id=candidate_id,
                input_summary=_summarize_text(query_text or jd_text),
                metadata={"limit": 5},
            ) as tool_call:
                evidence_texts = self.vector_store.query(
                    run_id,
                    candidate_id,
                    query_text or jd_text,
                    limit=5,
                )
                tool_call.set_output_summary(f"snippets={len(evidence_texts)}")

            with tool_recorder.call(
                "score_resume_quality",
                "score_candidates",
                candidate_id=candidate_id,
                input_summary=f"{profile.name} 简历质量",
                metadata={"llm_available": self.llm.available},
            ) as tool_call:
                resume_quality_failures: List[dict] = []
                resume_quality_report = score_resume_quality(
                    self.llm,
                    resume_text,
                    profile,
                    extraction_facts,
                    failure_sink=resume_quality_failures,
                )
                if resume_quality_failures:
                    tool_call.metadata.update(
                        _stage_fallback_metadata(
                            resume_quality_failures,
                            source_key="resume_quality_source",
                        )
                    )
                    self._record_stage_fallbacks(
                        audit_events,
                        resume_quality_failures,
                        event_name="resume_quality.llm_fallback",
                        fallback_strategy="local_rule_resume_quality",
                        run_id=run_id,
                        candidate_id=candidate_id,
                    )
                elif self.llm.available:
                    tool_call.metadata.update(
                        {
                            "resume_quality_source": "llm",
                            "llm_timeout_seconds": LLM_JSON_TIMEOUT_SECONDS,
                        }
                    )
                tool_call.set_output_summary(
                    f"overall={resume_quality_report.overall_score}"
                )

            if existing_run is None:
                complete_step(
                    agent_state,
                    "retrieve_evidence",
                    current_step_id="score_candidates",
                    tool_call_ids=[tool_call.call_id],
                )

            scoring_failures = []
            with tool_recorder.call(
                "score_candidate",
                "score_candidates",
                candidate_id=candidate_id,
                input_summary=f"{jd_profile.job_title} vs {profile.name}",
                metadata={"llm_available": self.llm.available},
            ) as tool_call:
                match = score_candidate_with_llm(
                    self.llm,
                    jd_profile,
                    profile,
                    evidence_texts,
                    jd_extraction_facts,
                    extraction_facts,
                    failure_sink=scoring_failures,
                )
                if match is None:
                    tool_call.metadata.update(
                        _stage_fallback_metadata(scoring_failures, source_key="scoring_source")
                    )
                    self._record_scoring_fallbacks(
                        audit_events,
                        scoring_failures,
                        run_id=run_id,
                        candidate_id=candidate_id,
                    )
                    match = score_candidate(jd_profile, profile, evidence_texts, extraction_facts)
                else:
                    tool_call.metadata.update(
                        {
                            "scoring_source": "llm",
                            "llm_timeout_seconds": LLM_JSON_TIMEOUT_SECONDS,
                        }
                    )
                tool_call.set_output_summary(f"score={match.total_score}; decision={match.decision}")

            if existing_run is None:
                complete_step(
                    agent_state,
                    "score_candidates",
                    current_step_id="generate_interview_materials",
                    tool_call_ids=[tool_call.call_id],
                )

            if match.total_score >= QUESTION_MATERIAL_MIN_SCORE:
                question_resume_text = mask_pii(resume_text, candidate_name=profile.name).text
                question_diagnostics: dict[str, object] = {}
                with tool_recorder.call(
                    "generate_interview_questions",
                    "generate_interview_materials",
                    candidate_id=candidate_id,
                    input_summary=f"{profile.name}; score={match.total_score}",
                    metadata={
                        "question_budget": agent_plan.question_budget,
                        "skill_ids": agent_plan.selected_skill_ids,
                    },
                ) as tool_call:
                    match.interview_questions = generate_interview_questions(
                        jd_profile,
                        profile,
                        match,
                        llm=self.llm,
                        jd_text=jd_text,
                        resume_text=question_resume_text,
                        extraction_facts=extraction_facts,
                        diagnostics=question_diagnostics,
                    )
                    match.followup_questions = generate_followups(profile, match, jd=jd_profile)
                    tool_call.metadata.update(question_diagnostics)
                    if question_diagnostics.get("question_generation_source") == "rule_fallback":
                        self._record_question_generation_fallback(
                            audit_events,
                            question_diagnostics,
                            run_id=run_id,
                            candidate_id=candidate_id,
                        )
                    tool_call.set_output_summary(
                        f"questions={len(match.interview_questions)}; followups={len(match.followup_questions)}"
                    )

            if existing_run is None:
                complete_step(
                    agent_state,
                    "generate_interview_materials",
                    current_step_id="run_interview_session",
                    tool_call_ids=[tool_call.call_id],
                )

            new_candidates.append(
                CandidateReport(
                    candidate_id=candidate_id,
                    source_name=source_name,
                    source_file=self._store_candidate_source_file(run_id, candidate_id, resume),
                    profile=profile,
                    match_report=match,
                    resume_quality=resume_quality_report,
                    resume_text_hash=_sha256_text(resume_text),
                    extraction_facts=extraction_facts,
                )
            )

        if existing_run is None:
            complete_state(agent_state)

        candidates = [*candidates, *new_candidates]
        candidates.sort(key=lambda item: item.match_report.total_score, reverse=True)
        all_tool_calls = [*base_tool_calls, *tool_recorder.records]

        report = RunReport(
            run_id=run_id,
            created_at=datetime.utcnow(),
            jd_profile=jd_profile,
            jd_extraction_facts=jd_extraction_facts,
            candidates=candidates,
            warnings=warnings,
            metadata=metadata,
            audit_events=audit_events,
            agent_plan=agent_plan,
            agent_state=agent_state,
            tool_calls=all_tool_calls,
        )
        self.storage.save_run(report)
        return report

    def get_candidate_source_file_path(
        self, run_id: str, candidate_id: str, source_file: CandidateSourceFile
    ) -> Optional[Path]:
        file_path = self._candidate_source_file_path(run_id, candidate_id, source_file.filename)
        if not file_path.is_file():
            return None
        return file_path

    def get_latest_run_for_jd(self, jd_text: str) -> Optional[RunReport]:
        return self.storage.get_latest_run_by_jd_text_hash(_sha256_text(jd_text))

    def get_run(self, run_id: str) -> RunReport:
        return self.storage.get_run(run_id)

    def remove_candidate(self, run_id: str, candidate_id: str) -> Optional[RunReport]:
        report = self.storage.get_run(run_id)
        if report is None:
            return None
        remaining = [item for item in report.candidates if item.candidate_id != candidate_id]
        if len(remaining) == len(report.candidates):
            return report

        if not remaining:
            for session in self.storage.list_interview_sessions(run_id=run_id):
                if session.candidate_id == candidate_id:
                    self.storage.delete_interview_session(session.session_id)
            self.storage.delete_run(run_id)
            return None

        report.candidates = remaining
        report.created_at = datetime.utcnow()
        for session in self.storage.list_interview_sessions(run_id=run_id):
            if session.candidate_id == candidate_id:
                self.storage.delete_interview_session(session.session_id)
        self.storage.save_run(report)
        return report

    def remove_all_runs(self) -> None:
        self.storage.delete_all_interview_sessions()
        self.storage.delete_all_runs()

    def _store_candidate_source_file(
        self, run_id: str, candidate_id: str, resume: ResumeSource
    ) -> Optional[CandidateSourceFile]:
        if not resume.file_content:
            return None
        file_path = self._candidate_source_file_path(run_id, candidate_id, resume.source_name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(resume.file_content)
        return CandidateSourceFile(filename=resume.source_name, content_type=resume.content_type)

    def _candidate_source_file_path(self, run_id: str, candidate_id: str, filename: str) -> Path:
        safe_name = _safe_source_filename(filename)
        return Path(self.settings.data_dir) / "run_uploads" / run_id / candidate_id / safe_name

    def _extract_jd(
        self,
        text: str,
        warnings: List[str],
        *,
        diagnostics: Optional[dict[str, object]] = None,
    ) -> Tuple[JDProfile, List[ExtractedFact]]:
        if self.llm.available:
            llm_result = extract_jd_with_llm(self.llm, text)
            if llm_result is not None:
                profile, facts = llm_result
                if facts:
                    _record_llm_success(diagnostics, source="llm")
                    return profile, facts
                warnings.append("JD 的 LLM 抽取未返回可用事实，已回退本地规则结果。")
                _record_llm_fallback_diagnostics(diagnostics, self.llm, "llm_returned_no_facts")
            else:
                warnings.append("JD 的 LLM 抽取失败，已回退本地规则结果。")
                _record_llm_fallback_diagnostics(diagnostics, self.llm, "llm_returned_none")
        else:
            _record_llm_fallback_diagnostics(diagnostics, self.llm, "llm_unavailable")
        return self._extract_jd_with_rules(text)

    def _extract_jd_with_rules(self, text: str) -> Tuple[JDProfile, List[ExtractedFact]]:
        profile = extract_jd_profile(text)
        facts = extract_jd_facts(text, profile)
        return profile, facts

    def _extract_candidate(
        self,
        text: str,
        source_name: str,
        warnings: List[str],
        *,
        diagnostics: Optional[dict[str, object]] = None,
    ) -> Tuple[CandidateProfile, List[ExtractedFact]]:
        initial_result = extract_resume_profile(text, source_name)
        initial_profile = initial_result.profile
        if self.llm.available:
            masked = mask_pii(text, candidate_name=initial_profile.name)
            llm_result = extract_resume_with_llm(self.llm, masked.text, source_name)
            if llm_result is not None:
                processed_profile, processed_facts = llm_result
                restored_profile = restore_pii_in_data(processed_profile.model_dump(mode="json"), masked.replacements)
                restored_facts = restore_pii_in_data(
                    [fact.model_dump(mode="json") for fact in processed_facts],
                    masked.replacements,
                )
                profile = CandidateProfile.model_validate(restored_profile)
                extraction_facts = _merge_extraction_facts(
                    [ExtractedFact.model_validate(fact) for fact in restored_facts],
                    initial_result.facts,
                )
                _record_llm_success(diagnostics, source="llm_plus_rules")
                return _merge_candidate_profile(profile, initial_profile), extraction_facts
            warnings.append(f"{source_name} 的 LLM 简历抽取失败，已使用本地规则结果。")
            _record_llm_fallback_diagnostics(diagnostics, self.llm, "llm_returned_none")
        else:
            _record_llm_fallback_diagnostics(diagnostics, self.llm, "llm_unavailable")
        return initial_profile, initial_result.facts

    def _record_scoring_fallbacks(
        self,
        audit_events,
        failures: List[dict],
        *,
        run_id: str,
        candidate_id: str,
    ) -> None:
        if not self.llm.available:
            return
        if not failures:
            failures = [
                {
                    "stage": "requirement_matching",
                    "failure_code": "llm_scoring_unavailable",
                    "message": "LLM scoring returned no report without a detailed failure reason.",
                    "invalid_requirements": [],
                    "details": {"llm_timeout_seconds": LLM_JSON_TIMEOUT_SECONDS},
                }
            ]
        for failure in failures:
            stage = failure.get("stage", "requirement_matching")
            prompt_version = PROMPT_VERSIONS.get(stage)
            event_name = "scoring.rubric_invalid" if stage == "rubric_generation" else "scoring.llm_matching_invalid"
            record_audit_event(
                audit_events,
                event=event_name,
                stage=stage,
                failure_code=failure.get("failure_code", "unknown_scoring_failure"),
                message=failure.get("message", "LLM scoring failed."),
                fallback_strategy="local_rule_scorer",
                run_id=run_id,
                candidate_id=candidate_id,
                model=self.settings.llm_model,
                prompt_version=prompt_version,
                invalid_requirements=failure.get("invalid_requirements", []),
                details=failure.get("details", {}),
            )

    def _record_stage_fallbacks(
        self,
        audit_events,
        failures: List[dict],
        *,
        event_name: str,
        fallback_strategy: str,
        run_id: str,
        candidate_id: Optional[str] = None,
    ) -> None:
        if not self.llm.available:
            return
        for failure in failures:
            stage = failure.get("stage", "llm")
            record_audit_event(
                audit_events,
                event=event_name,
                stage=stage,
                failure_code=failure.get("failure_code", "unknown_llm_failure"),
                message=failure.get("message", "LLM stage failed."),
                fallback_strategy=fallback_strategy,
                run_id=run_id,
                candidate_id=candidate_id,
                model=self.settings.llm_model,
                prompt_version=PROMPT_VERSIONS.get(stage),
                invalid_requirements=failure.get("invalid_requirements", []),
                details=failure.get("details", {}),
            )

    def _record_llm_fallback(
        self,
        audit_events,
        *,
        event: str,
        stage: str,
        fallback_strategy: str,
        diagnostics: dict[str, object],
        run_id: str,
        candidate_id: Optional[str] = None,
    ) -> None:
        if not self.llm.available:
            return
        reason = str(diagnostics.get("fallback_reason") or "unknown_llm_failure")
        record_audit_event(
            audit_events,
            event=event,
            stage=stage,
            failure_code=reason,
            message=f"{stage} LLM request failed; local fallback was used.",
            fallback_strategy=fallback_strategy,
            run_id=run_id,
            candidate_id=candidate_id,
            model=self.settings.llm_model,
            prompt_version=PROMPT_VERSIONS.get(stage),
            details={
                "llm_timeout_seconds": diagnostics.get("llm_timeout_seconds"),
                "extraction_source": diagnostics.get("extraction_source"),
            },
        )

    def _record_question_generation_fallback(
        self,
        audit_events,
        diagnostics: dict[str, object],
        *,
        run_id: str,
        candidate_id: str,
    ) -> None:
        record_audit_event(
            audit_events,
            event="question_generation.llm_fallback",
            stage="question_generation",
            failure_code=str(diagnostics.get("fallback_reason") or "unknown_question_generation_failure"),
            message="LLM question generation failed; local rule questions were used.",
            fallback_strategy="local_rule_questions",
            run_id=run_id,
            candidate_id=candidate_id,
            model=self.settings.llm_model,
            prompt_version=PROMPT_VERSIONS["question_generation"],
            details={
                "llm_timeout_seconds": diagnostics.get("llm_timeout_seconds"),
                "question_generation_source": diagnostics.get("question_generation_source"),
            },
        )


def _record_llm_success(diagnostics: Optional[dict[str, object]], *, source: str) -> None:
    if diagnostics is None:
        return
    diagnostics["extraction_source"] = source
    diagnostics["llm_timeout_seconds"] = LLM_JSON_TIMEOUT_SECONDS
    diagnostics.pop("fallback_reason", None)


def _record_llm_fallback_diagnostics(
    diagnostics: Optional[dict[str, object]],
    llm: LLMClient,
    default_reason: str,
) -> None:
    if diagnostics is None:
        return
    reason = getattr(llm, "last_error", None) or default_reason
    diagnostics["extraction_source"] = "rule_fallback"
    diagnostics["fallback_reason"] = _compact_reason(str(reason))
    diagnostics["llm_timeout_seconds"] = LLM_JSON_TIMEOUT_SECONDS


def _stage_fallback_metadata(failures: List[dict], *, source_key: str) -> dict[str, object]:
    failure = failures[0] if failures else {}
    details = failure.get("details") if isinstance(failure.get("details"), dict) else {}
    metadata: dict[str, object] = {
        source_key: "rule_fallback",
        "fallback_stage": failure.get("stage", "requirement_matching"),
        "fallback_reason": failure.get("failure_code", "llm_scoring_unavailable"),
        "llm_timeout_seconds": details.get("llm_timeout_seconds", LLM_JSON_TIMEOUT_SECONDS),
    }
    invalid_requirements = failure.get("invalid_requirements")
    if invalid_requirements:
        metadata["invalid_requirements"] = invalid_requirements
    return metadata


def _compact_reason(reason: str) -> str:
    text = " ".join((reason or "unknown_llm_failure").split())
    if len(text) <= 240:
        return text
    return f"{text[:237]}..."


def _merge_candidate_profile(profile: CandidateProfile, fallback: CandidateProfile) -> CandidateProfile:
    if profile.name in {"候选人", "未知候选人", "简历候选人"} and fallback.name:
        profile.name = fallback.name
    if not profile.target_role:
        profile.target_role = fallback.target_role
    if not profile.contacts:
        profile.contacts = fallback.contacts
    if not profile.location:
        profile.location = fallback.location
    for field_name in (
        "education",
        "work_experiences",
        "projects",
        "skills",
        "certifications",
        "highlights",
        "risk_points",
        "ambiguous_points",
    ):
        if not getattr(profile, field_name):
            setattr(profile, field_name, getattr(fallback, field_name))
    return profile


def _merge_extraction_facts(
    primary: List[ExtractedFact], fallback: List[ExtractedFact]
) -> List[ExtractedFact]:
    seen = set()
    merged: List[ExtractedFact] = []
    for fact in [*primary, *fallback]:
        key = (fact.fact_type, fact.value.lower(), fact.evidence.lower(), fact.section)
        if key in seen:
            continue
        seen.add(key)
        merged.append(fact)
    return merged


def _next_candidate_index(candidates: List[CandidateReport]) -> int:
    max_index = 0
    for candidate in candidates:
        parts = candidate.candidate_id.split("-", 1)
        if len(parts) != 2 or parts[0] != "candidate":
            continue
        try:
            max_index = max(max_index, int(parts[1]))
        except ValueError:
            continue
    return max_index + 1


def _coerce_resume_source(resume) -> ResumeSource:
    if isinstance(resume, ResumeSource):
        return resume
    source_name, text = resume
    return ResumeSource(str(source_name), str(text))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_source_filename(filename: str) -> str:
    name = Path(filename or "resume").name.replace("\\", "_").strip()
    return name or "resume"


def _summarize_text(text: str, max_length: int = 120) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3] + "..."
