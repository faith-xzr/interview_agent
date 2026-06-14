from datetime import datetime
import hashlib
from typing import List, Tuple
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
from app.privacy import mask_pii, restore_pii_in_data
from app.question_generation import generate_interview_questions
from app.schemas import CandidateProfile, CandidateReport, ExtractedFact, JDProfile, RunMetadata, RunReport
from app.scoring import score_candidate, score_candidate_with_llm
from app.skills import SkillRepository, select_skills_for_jd
from app.storage import RunStorage
from app.vector_store import VectorStore

QUESTION_MATERIAL_MIN_SCORE = 40
PROMPT_VERSIONS = {
    "jd_extraction": "jd_requirements@2026-06-13",
    "resume_extraction": "resume_profile@2026-06-13",
    "rubric_generation": "rubric_generation@2026-06-14",
    "requirement_matching": "requirement_matching@2026-06-14",
}
SCORING_POLICY_VERSION = "backend_score_policy@v1"


class RecruitingPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = RunStorage(settings.database_path)
        self.vector_store = VectorStore(settings.vector_dir, enable_chroma=settings.enable_chroma)
        self.llm = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
        self.skill_repository = SkillRepository(settings.skills_dir)

    def run(self, jd_text: str, resumes: List[Tuple[str, str]]) -> RunReport:
        run_id = uuid4().hex
        warnings: List[str] = []
        audit_events = []
        tool_recorder = ToolRecorder(run_id)
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
            jd_profile, jd_extraction_facts = self._extract_jd(jd_text, warnings)
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

        self.vector_store.add_document(run_id, "jd", "JD", jd_text)
        for index, (source_name, resume_text) in enumerate(resumes):
            candidate_id = f"candidate-{index + 1}"
            with tool_recorder.call(
                "extract_resume",
                "extract_resumes",
                candidate_id=candidate_id,
                input_summary=source_name,
                metadata={"llm_available": self.llm.available},
            ) as tool_call:
                profile, extraction_facts = self._extract_candidate(resume_text, source_name, warnings)
                tool_call.set_output_summary(f"{profile.name}; facts={len(extraction_facts)}")
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
                    self._record_scoring_fallbacks(
                        audit_events,
                        scoring_failures,
                        run_id=run_id,
                        candidate_id=candidate_id,
                    )
                    match = score_candidate(jd_profile, profile, evidence_texts, extraction_facts)
                tool_call.set_output_summary(f"score={match.total_score}; decision={match.decision}")
            complete_step(
                agent_state,
                "score_candidates",
                current_step_id="generate_interview_materials",
                tool_call_ids=[tool_call.call_id],
            )
            if match.total_score >= QUESTION_MATERIAL_MIN_SCORE:
                question_resume_text = mask_pii(resume_text, candidate_name=profile.name).text
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
                    )
                    match.followup_questions = generate_followups(profile, match, jd=jd_profile)
                    tool_call.set_output_summary(
                        f"questions={len(match.interview_questions)}; followups={len(match.followup_questions)}"
                    )
                complete_step(
                    agent_state,
                    "generate_interview_materials",
                    current_step_id="run_interview_session",
                    tool_call_ids=[tool_call.call_id],
                )
            candidates.append(
                CandidateReport(
                    candidate_id=candidate_id,
                    source_name=source_name,
                    profile=profile,
                    match_report=match,
                    resume_text_hash=_sha256_text(resume_text),
                    extraction_facts=extraction_facts,
                )
            )

        candidates.sort(key=lambda item: item.match_report.total_score, reverse=True)
        complete_state(agent_state)
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
            tool_calls=tool_recorder.records,
        )
        self.storage.save_run(report)
        return report

    def get_run(self, run_id: str) -> RunReport:
        return self.storage.get_run(run_id)

    def _extract_jd(self, text: str, warnings: List[str]) -> Tuple[JDProfile, List[ExtractedFact]]:
        if self.llm.available:
            llm_result = extract_jd_with_llm(self.llm, text)
            if llm_result is not None:
                profile, facts = llm_result
                if facts:
                    return profile, facts
                warnings.append("JD 的 LLM 抽取未返回可用事实，已回退本地规则结果。")
            else:
                warnings.append("JD 的 LLM 抽取失败，已回退本地规则结果。")
        return self._extract_jd_with_rules(text)

    def _extract_jd_with_rules(self, text: str) -> Tuple[JDProfile, List[ExtractedFact]]:
        profile = extract_jd_profile(text)
        facts = extract_jd_facts(text, profile)
        return profile, facts

    def _extract_candidate(
        self, text: str, source_name: str, warnings: List[str]
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
                return _merge_candidate_profile(profile, initial_profile), extraction_facts
            warnings.append(f"{source_name} 的 LLM 简历抽取失败，已使用本地规则结果。")
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
            )


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


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _summarize_text(text: str, max_length: int = 120) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3] + "..."
